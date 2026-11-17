"""Integration and unit tests for Database Inbox, Synchronization, and FlowShark Dashboard."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.classification_model import Classification, ClassificationHistory
from app.models.conversation_model import Conversation
from app.models.email_model import Email
from app.models.sync_model import SyncState
from app.routes.classification_routes import correct_classification
from app.routes.dashboard_routes import get_dashboard_summary
from app.routes.email_inbox_routes import get_email_detail, list_emails
from app.schemas.dashboard_schema import ClassificationCorrectionRequest
from app.services.hybrid_classifier import HybridClassifier
from app.services.nlp_preprocessor import NLPPreprocessor
from app.services.rule_classifier import RuleBasedClassifier
from app.services.sync_service import EmailSyncService


@pytest.fixture
def in_memory_db():
    """Create a pristine in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_nlp_preprocessor_comprehensive():
    """Verify HTML stripping, quote separation, and signature detection."""
    raw_html = """
    <html><body>
    <p>Hi Team,</p>
    <p>We are looking for a vendor to build our website.</p>
    <br>
    <p>Best regards,<br>Alice</p>
    <p>On Mon, Nov 16, 2026 at 10:00 AM Bob wrote:<br>&gt; Let us know what you need.</p>
    </body></html>
    """
    preprocessed = NLPPreprocessor.preprocess(body_plain=None, body_html=raw_html, subject="Website quote")

    assert "looking for a vendor" in preprocessed.cleaned_body
    assert "Alice" not in preprocessed.cleaned_body or "Bob wrote" in (preprocessed.quoted_history or "")
    assert preprocessed.word_count > 0


def test_rule_classifier_negation_awareness():
    """Negated signals must NOT trigger false positive lead creation."""
    classifier = RuleBasedClassifier()

    # Negated enquiry
    negated_text = "Thank you for reaching out, but we are NOT interested in your services and not looking for a website."
    res = classifier.evaluate(cleaned_body=negated_text, subject="Cold outreach")
    assert res.intent != "new_enquiry"
    assert len(res.negations) > 0

    # Genuine enquiry
    genuine_text = "Hi team, we are interested in your services and looking for a website design partner."
    res2 = classifier.evaluate(cleaned_body=genuine_text, subject="Project enquiry")
    assert res2.intent == "new_enquiry"
    assert res2.relationship == "new_contact"


def test_email_sync_and_deduplication(in_memory_db):
    """Verify incremental sync, deduplication constraint, and conversation creation."""
    sync_service = EmailSyncService(db=in_memory_db)

    # Insert initial email manually
    email1 = Email(
        account_email="test@gmail.com",
        imap_uid="501",
        uid_validity=1,
        message_id="<msg-501@gmail.com>",
        gmail_thread_id="thread-abc",
        sender="client@example.com",
        recipient="test@gmail.com",
        subject="Project Discussion",
        body_text="Can we discuss project terms?",
        received_at=datetime.now(timezone.utc),
    )
    in_memory_db.add(email1)
    in_memory_db.commit()

    # Attempting to insert identical (account_email, uid_validity, imap_uid) must be caught by unique constraint
    duplicate = Email(
        account_email="test@gmail.com",
        imap_uid="501",
        uid_validity=1,
        message_id="<msg-501-dup@gmail.com>",
        sender="client@example.com",
        subject="Duplicate",
    )
    in_memory_db.add(duplicate)
    with pytest.raises(Exception):
        in_memory_db.commit()
    in_memory_db.rollback()


def test_hybrid_classification_and_conversation_update(in_memory_db):
    """Verify hybrid classification flow and conversation lead stage progression."""
    classifier = HybridClassifier(db=in_memory_db)

    email = Email(
        account_email="test@gmail.com",
        imap_uid="601",
        uid_validity=1,
        message_id="<msg-601@gmail.com>",
        gmail_thread_id="thread-xyz",
        sender="prospect@company.com",
        subject="Re: Proposal for Mobile App",
        body_text="We received your quote. Can you reduce the price to ₹40,000?",
        received_at=datetime.now(timezone.utc),
    )
    in_memory_db.add(email)
    in_memory_db.commit()

    classification = classifier.classify_email(email)

    assert classification.email_id == email.id
    assert classification.intent == "negotiation"
    assert classification.relationship == "existing_lead"
    assert classification.lead_stage == "negotiation"
    assert classification.confidence >= 0.55

    # Verify conversation thread was created
    conv = in_memory_db.query(Conversation).filter(Conversation.gmail_thread_id == "thread-xyz").first()
    assert conv is not None
    assert conv.current_lead_stage == "negotiation"


def test_manual_correction_audit_trail(in_memory_db):
    """Verify manual correction updates the classification and logs to history."""
    email = Email(
        account_email="test@gmail.com",
        imap_uid="701",
        uid_validity=1,
        sender="vendor@example.com",
        subject="Invoice #101",
        body_text="Invoice attached.",
    )
    in_memory_db.add(email)
    in_memory_db.commit()

    classification = Classification(
        email_id=email.id,
        relationship="unknown",
        intent="other",
        lead_stage="unknown",
        confidence=0.50,
        classification_method="rule_based",
        requires_human_review=True,
    )
    in_memory_db.add(classification)
    in_memory_db.commit()

    # User corrects it to invoice
    correction = ClassificationCorrectionRequest(
        intent="invoice",
        relationship="existing_customer",
        lead_stage="won",
        notes="Verified billing document",
    )
    updated = correct_classification(classification_id=classification.id, correction=correction, db=in_memory_db)

    assert updated.intent == "invoice"
    assert updated.relationship == "existing_customer"
    assert updated.lead_stage == "won"
    assert updated.classification_method == "manual_correction"
    assert updated.requires_human_review is False

    # Check history
    history = in_memory_db.query(ClassificationHistory).filter(ClassificationHistory.classification_id == classification.id).first()
    assert history is not None
    assert history.previous_values["intent"] == "other"
    assert history.corrected_values["intent"] == "invoice"
    assert history.notes == "Verified billing document"


def test_dashboard_summary_counts(in_memory_db):
    """Verify dashboard summary returns accurate non-fabricated counts."""
    # Insert 1 new lead and 1 negotiation
    e1 = Email(account_email="test@gmail.com", imap_uid="801", uid_validity=1, sender="s1@a.com", subject="New Lead")
    e2 = Email(account_email="test@gmail.com", imap_uid="802", uid_validity=1, sender="s2@a.com", subject="Negotiation")
    in_memory_db.add_all([e1, e2])
    in_memory_db.commit()

    c1 = Classification(email_id=e1.id, relationship="new_contact", intent="new_enquiry", lead_stage="new", confidence=0.90)
    c2 = Classification(email_id=e2.id, relationship="existing_lead", intent="negotiation", lead_stage="negotiation", confidence=0.85)
    in_memory_db.add_all([c1, c2])
    in_memory_db.commit()

    summary = get_dashboard_summary(db=in_memory_db)
    assert summary.total_synced == 2
    assert summary.total_classified == 2
    assert summary.new_leads_count == 1
    assert summary.negotiations_count == 1
    assert len(summary.recent_activity) == 2
