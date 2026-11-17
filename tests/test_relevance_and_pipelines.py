"""Automated test suite for Business Email Relevance Detection and Lead Pipelines.

Covers:
1. Google Security Alerts & 2-Step Verification notifications (classified as non-business).
2. Google account setup & transaction alerts (non-business).
3. Newsletters & marketing communications (non-business).
4. Genuine new business enquiries -> 'new_leads' pipeline.
5. Pricing negotiations -> 'negotiations' pipeline.
6. Progress follow-ups -> 'follow_ups' pipeline.
7. Business clarifications -> 'clarifications' pipeline.
8. Purchase Orders -> 'purchase_orders' pipeline.
9. Invoices -> 'invoices' pipeline.
10. Non-business emails never create Contact or Lead entities.
11. Mailbox scoped removal (complete deletion without affecting other mailboxes).
12. Manual correction preservation during reclassification.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.classification_model import Classification, ClassificationHistory
from app.models.contact_model import Contact
from app.models.conversation_model import Conversation
from app.models.email_model import Email
from app.models.lead_model import Lead
from app.models.mailbox_model import Mailbox
from app.models.sync_model import SyncState
from app.services.hybrid_classifier import HybridClassifier
from app.services.mailbox_service import MailboxService
from app.services.pipeline_service import PipelineClassifier
from app.services.relevance_detector import BusinessRelevanceDetector


@pytest.fixture
def test_db():
    """Isolated in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    mb = Mailbox(
        email_address="agency@flowshark.com",
        is_active=True,
    )
    session.add(mb)
    session.commit()
    session.refresh(mb)

    try:
        yield session, mb
    finally:
        session.close()


class TestBusinessEmailRelevanceDetector:
    """Direct unit tests for the 11-category Business Relevance Detection layer."""

    def setup_method(self):
        self.detector = BusinessRelevanceDetector()

    def test_google_security_alert(self):
        res = self.detector.evaluate(
            sender="Google <no-reply@accounts.google.com>",
            subject="Security alert for your linked Google Account",
            body_text="A new sign-in was detected on your Windows device. Review activity now.",
        )
        assert res.is_business_relevant is False
        assert res.relevance_category == "account_security_notification"
        assert res.confidence >= 0.90
        assert any("google.com" in e.lower() or "security" in e.lower() for e in res.evidence)

    def test_google_2fa_notification(self):
        res = self.detector.evaluate(
            sender="Google <no-reply@accounts.google.com>",
            subject="2-Step Verification notification",
            body_text="Your Google verification code is 482910. Do not share this code with anyone.",
        )
        assert res.is_business_relevant is False
        assert res.relevance_category == "account_security_notification"

    def test_google_account_setup(self):
        res = self.detector.evaluate(
            sender="The Google Team <google-noreply@google.com>",
            subject="Finish setting up your new Google Account",
            body_text="Welcome to your new Google Account. Learn how to get the most out of Gmail and Chrome.",
        )
        assert res.is_business_relevant is False
        assert res.relevance_category in ("account_security_notification", "system_notification", "automated_notification")

    def test_bank_transaction_alert(self):
        res = self.detector.evaluate(
            sender="alerts@hdfcbank.net",
            subject="UPI/IMPS/MB Transaction Alert: Rs. 4,500 debited",
            body_text="Your account has been debited for Rs 4,500.00 at Swiggy. Available balance is Rs 34,200.",
        )
        assert res.is_business_relevant is False
        assert res.relevance_category == "automated_notification"

    def test_newsletter_marketing(self):
        res = self.detector.evaluate(
            sender="newsletter@techbrew.io",
            subject="🔴 Career Brew (🎓☕) - 16th Nov - 49 jobs in AI and FinTech",
            body_text="Here is your weekly roundup of tech jobs. Click here to unsubscribe.",
        )
        assert res.is_business_relevant is False
        assert res.relevance_category == "newsletter_marketing"

    def test_genuine_business_inquiry(self):
        res = self.detector.evaluate(
            sender="sarah.connor@cyberdyne.com",
            subject="Website Development Enquiry – New Business Portal",
            body_text="Hello FlowShark team, We would like to develop a custom B2B web application for our enterprise. Could you share your pricing and timeline?",
        )
        assert res.is_business_relevant is True
        assert res.relevance_category == "business_enquiry"
        assert res.confidence >= 0.85

    def test_negotiation_email(self):
        res = self.detector.evaluate(
            sender="procurement@acme.org",
            subject="Quotation Review - Discount Request",
            body_text="We received your proposal for $25,000. Can we negotiate a 15% discount if we sign an annual retainer agreement?",
        )
        assert res.is_business_relevant is True
        assert res.relevance_category in ("purchase_commercial", "business_conversation", "business_enquiry")

    def test_follow_up_email(self):
        res = self.detector.evaluate(
            sender="marcus@globalgym.com",
            subject="i need a update",
            body_text="hello what is my website progress? looking forward to launch next week.",
        )
        assert res.is_business_relevant is True
        assert res.relevance_category in ("business_conversation", "business_enquiry")


class TestPipelineClassifier:
    """Unit tests for strict 8-pipeline classification."""

    def setup_method(self):
        self.pipeline = PipelineClassifier()

    def test_non_business_gets_no_pipeline(self):
        res = self.pipeline.assign_pipeline(
            is_business_relevant=False,
            relevance_category="account_security_notification",
            relationship="not_applicable",
            intent="not_applicable",
            lead_stage="not_applicable",
            confidence=0.98,
        )
        assert res.pipeline_category is None

    def test_new_lead_pipeline(self):
        res = self.pipeline.assign_pipeline(
            is_business_relevant=True,
            relevance_category="business_enquiry",
            relationship="new_contact",
            intent="new_enquiry",
            lead_stage="new",
            confidence=0.92,
        )
        assert res.pipeline_category == "new_leads"

    def test_negotiation_pipeline(self):
        res = self.pipeline.assign_pipeline(
            is_business_relevant=True,
            relevance_category="business_conversation",
            relationship="existing_lead",
            intent="negotiation",
            lead_stage="negotiation",
            confidence=0.90,
        )
        assert res.pipeline_category == "negotiations"

    def test_follow_up_pipeline(self):
        res = self.pipeline.assign_pipeline(
            is_business_relevant=True,
            relevance_category="business_conversation",
            relationship="existing_lead",
            intent="follow_up",
            lead_stage="qualified",
            confidence=0.88,
        )
        assert res.pipeline_category == "follow_ups"

    def test_clarification_pipeline(self):
        res = self.pipeline.assign_pipeline(
            is_business_relevant=True,
            relevance_category="business_conversation",
            relationship="existing_lead",
            intent="business_clarification",
            lead_stage="qualified",
            confidence=0.85,
        )
        assert res.pipeline_category == "clarifications"

    def test_purchase_order_pipeline(self):
        res = self.pipeline.assign_pipeline(
            is_business_relevant=True,
            relevance_category="purchase_commercial",
            relationship="existing_lead",
            intent="purchase_order",
            lead_stage="won",
            confidence=0.95,
        )
        assert res.pipeline_category == "purchase_orders"

    def test_invoice_pipeline(self):
        res = self.pipeline.assign_pipeline(
            is_business_relevant=True,
            relevance_category="purchase_commercial",
            relationship="existing_lead",
            intent="invoice",
            lead_stage="won",
            confidence=0.92,
        )
        assert res.pipeline_category == "invoices"

    def test_needs_review_on_low_confidence(self):
        res = self.pipeline.assign_pipeline(
            is_business_relevant=True,
            relevance_category="business_conversation",
            relationship="unknown",
            intent="other",
            lead_stage="unknown",
            confidence=0.45,
        )
        assert res.pipeline_category == "needs_review"


class TestHybridClassificationAndCRMIntegration:
    """Integration tests verifying database persistence and CRM side-effects."""

    def test_google_alert_does_not_create_crm_lead(self, test_db):
        session, mb = test_db
        email = Email(
            mailbox_id=mb.id,
            account_email=mb.email_address,
            imap_uid="901",
            uid_validity=1,
            sender="no-reply@accounts.google.com",
            subject="Security alert: New sign-in on Windows",
            body_text="Your account was accessed from a new device.",
        )
        session.add(email)
        session.commit()

        classifier = HybridClassifier(db=session)
        cls = classifier.classify_email(email)

        assert cls.is_business_relevant is False
        assert cls.pipeline_category is None
        assert cls.relationship in ("not_applicable", "unknown")
        assert cls.intent in ("not_applicable", "other")
        assert cls.lead_stage in ("not_applicable", "unknown")
        assert cls.sender_industry == "Not Applicable"
        assert cls.target_industry == "Not Applicable"

        # Verify no CRM Contact or Lead was created
        assert session.query(Contact).count() == 0
        assert session.query(Lead).count() == 0

    def test_genuine_enquiry_creates_crm_lead_and_pipeline(self, test_db):
        session, mb = test_db
        email = Email(
            mailbox_id=mb.id,
            account_email=mb.email_address,
            imap_uid="902",
            uid_validity=1,
            sender="dr.smith@apexclinic.com",
            subject="Medical Records System RFP",
            body_text="Dear Team, We need a quotation for a hospital medical record management web app.",
        )
        session.add(email)
        session.commit()

        classifier = HybridClassifier(db=session)
        cls = classifier.classify_email(email)

        assert cls.is_business_relevant is True
        assert cls.pipeline_category == "new_leads"
        assert cls.relationship == "new_contact"
        assert cls.intent == "new_enquiry"
        assert cls.sender_industry == "Healthcare"

        # Verify Contact and Lead were created
        contact = session.query(Contact).filter(Contact.email_address == "dr.smith@apexclinic.com").first()
        assert contact is not None
        assert contact.relationship_type in ("new_contact", "existing_lead")
        assert session.query(Lead).count() == 1

    def test_manual_correction_preserved(self, test_db):
        session, mb = test_db
        email = Email(
            mailbox_id=mb.id,
            account_email=mb.email_address,
            imap_uid="903",
            uid_validity=1,
            sender="partner@retailco.com",
            subject="Quick question",
            body_text="Can we discuss the proposal?",
        )
        session.add(email)
        session.commit()

        classifier = HybridClassifier(db=session)
        cls = classifier.classify_email(email)

        # Apply human manual correction
        cls.relationship = "existing_lead"
        cls.intent = "negotiation"
        cls.lead_stage = "negotiation"
        cls.pipeline_category = "negotiations"
        cls.classification_method = "manual_correction"
        session.commit()

        # Re-run classifier
        cls_after = classifier.classify_email(email, audit_reclassification=True)
        assert cls_after.classification_method == "manual_correction"
        assert cls_after.relationship == "existing_lead"
        assert cls_after.intent == "negotiation"


class TestMailboxSafeRemoval:
    """Test complete removal of a specific mailbox without impacting others."""

    def test_remove_mailbox_complete_isolation(self, test_db):
        session, mb1 = test_db

        # Create secondary mailbox
        mb2 = Mailbox(
            email_address="g1digitalizing@gmail.com",
            is_active=False,
        )
        session.add(mb2)
        session.commit()

        # Seed data for MB1
        e1 = Email(mailbox_id=mb1.id, account_email=mb1.email_address, imap_uid="10", uid_validity=1, sender="c1@biz.com", subject="Mb1 lead")
        session.add(e1)
        session.commit()
        cls1 = Classification(mailbox_id=mb1.id, email_id=e1.id, relationship="new_contact", intent="new_enquiry", lead_stage="new", confidence=0.9, classification_method="auto", requires_human_review=False)
        session.add(cls1)

        # Seed data for MB2
        e2 = Email(mailbox_id=mb2.id, account_email=mb2.email_address, imap_uid="20", uid_validity=1, sender="c2@biz.com", subject="Mb2 alert")
        session.add(e2)
        session.commit()
        cls2 = Classification(mailbox_id=mb2.id, email_id=e2.id, relationship="not_applicable", intent="not_applicable", lead_stage="not_applicable", confidence=0.95, classification_method="auto", requires_human_review=False)
        session.add(cls2)
        session.commit()

        # Delete MB2
        service = MailboxService(db=session)
        res = service.remove_mailbox("g1digitalizing@gmail.com")

        assert res["status"] == "success"
        assert res["removed_email"] == "g1digitalizing@gmail.com"

        # Verify MB2 is completely gone
        assert session.query(Mailbox).filter(Mailbox.email_address == "g1digitalizing@gmail.com").first() is None
        assert session.query(Email).filter(Email.mailbox_id == mb2.id).count() == 0
        assert session.query(Classification).filter(Classification.mailbox_id == mb2.id).count() == 0

        # Verify MB1 is completely preserved
        assert session.query(Mailbox).filter(Mailbox.id == mb1.id).first() is not None
        assert session.query(Email).filter(Email.mailbox_id == mb1.id).count() == 1
        assert session.query(Classification).filter(Classification.mailbox_id == mb1.id).count() == 1
