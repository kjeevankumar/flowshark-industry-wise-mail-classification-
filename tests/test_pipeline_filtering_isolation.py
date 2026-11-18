"""Comprehensive automated tests for FlowShark pipeline classification, authoritative category assignment,
strict backend pipeline filtering, data isolation, and global pipeline invariants.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.classification_model import Classification
from app.models.email_model import Email
from app.models.mailbox_model import Mailbox
from app.routes.classification_routes import correct_classification
from app.routes.dashboard_routes import get_dashboard_summary
from app.routes.email_inbox_routes import list_emails
from app.routes.email_routes import switch_mailbox
from app.schemas.dashboard_schema import ClassificationCorrectionRequest, SwitchMailboxRequest
from app.services.hybrid_classifier import HybridClassifier


@pytest.fixture
def isolation_env(test_db):
    """Set up test environment with a primary mailbox and configured settings."""
    db, mb = test_db
    settings = get_settings()
    return db, mb, settings


# =============================================================================
# PHASE 5: Classification Validation (10 Benchmark Real-World Examples)
# =============================================================================

def test_phase5_case1_purchase_order(isolation_env):
    """Case 1: 'Please confirm our order against PO-2026-104.' -> Purchase Order."""
    db, mb, _ = isolation_env
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="8001",
        uid_validity=1,
        message_id="<case1-po@acme.com>",
        sender="Acme Procurement <procurement@acme.com>",
        subject="Order Confirmation - Phase 1 Implementation",
        body_text="Please confirm our order against PO-2026-104.",
        received_at=datetime(2026, 11, 18, 9, 0, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)
    assert cls.is_business_relevant is True
    assert cls.pipeline_category == "purchase_orders"
    assert cls.intent == "purchase_order"


def test_phase5_case2_invoice_request(isolation_env):
    """Case 2: 'Please share the invoice against our approved purchase order.' -> Invoice Request."""
    db, mb, _ = isolation_env
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="8002",
        uid_validity=1,
        message_id="<case2-inv-req@client.com>",
        sender="Finance Department <finance@client.com>",
        subject="Request for Tax Invoice",
        body_text="Please share the invoice against our approved purchase order.",
        received_at=datetime(2026, 11, 18, 9, 5, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)
    assert cls.is_business_relevant is True
    assert cls.pipeline_category == "invoice_request"
    assert cls.intent == "invoice_request"


def test_phase5_case3_invoice_update(isolation_env):
    """Case 3: 'The GST number on invoice INV-1048 is incorrect.' -> Invoice Update."""
    db, mb, _ = isolation_env
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="8003",
        uid_validity=1,
        message_id="<case3-inv-upd@client.com>",
        sender="Accounts Payable <ap@client.com>",
        subject="Invoice INV-1048 Correction Required",
        body_text="The GST number on invoice INV-1048 is incorrect. Kindly update our GSTIN to 29ABCDE1234F1Z5 and share the revised invoice.",
        received_at=datetime(2026, 11, 18, 9, 10, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)
    assert cls.is_business_relevant is True
    assert cls.pipeline_category == "invoice_update"
    assert cls.intent == "invoice_update"


def test_phase5_case4_payment_remittance(isolation_env):
    """Case 4: 'We transferred ₹75,000. UTR: AXIS123456.' -> Payment Remittance."""
    db, mb, _ = isolation_env
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="8004",
        uid_validity=1,
        message_id="<case4-remittance@client.com>",
        sender="Accounts Team <accounts@client.com>",
        subject="Payment Advice for Invoice INV-1042",
        body_text="We transferred ₹75,000. UTR: AXIS123456. Please acknowledge receipt.",
        received_at=datetime(2026, 11, 18, 9, 15, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)
    assert cls.is_business_relevant is True
    assert cls.pipeline_category == "payment_remittance"
    assert cls.intent == "payment_remittance"


def test_phase5_case5_payment_follow_up(isolation_env):
    """Case 5: 'Please let us know when our pending payment will be processed.' -> Payment Follow-up."""
    db, mb, _ = isolation_env
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="8005",
        uid_validity=1,
        message_id="<case5-followup@vendor.com>",
        sender="Billing Manager <billing@vendor.com>",
        subject="Status of Pending Payment",
        body_text="Please let us know when our pending payment will be processed.",
        received_at=datetime(2026, 11, 18, 9, 20, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)
    assert cls.is_business_relevant is True
    assert cls.pipeline_category == "payment_follow_up"
    assert cls.intent == "payment_follow_up"


def test_phase5_case6_payment_dispute(isolation_env):
    """Case 6: 'The invoice amount does not match our agreed quotation.' -> Payment Dispute."""
    db, mb, _ = isolation_env
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="8006",
        uid_validity=1,
        message_id="<case6-dispute@client.com>",
        sender="Operations Director <ops@client.com>",
        subject="Discrepancy in Invoice Amount",
        body_text="The invoice amount does not match our agreed quotation. We agreed on $5,000 but the invoice shows $6,500.",
        received_at=datetime(2026, 11, 18, 9, 25, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)
    assert cls.is_business_relevant is True
    assert cls.pipeline_category == "payment_dispute"
    assert cls.intent == "payment_dispute"


def test_phase5_case7_clarification(isolation_env):
    """Case 7: 'Please clarify whether the website includes an admin dashboard.' -> Clarification."""
    db, mb, _ = isolation_env
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="8007",
        uid_validity=1,
        message_id="<case7-clarify@prospect.com>",
        sender="Technical Lead <tech@prospect.com>",
        subject="Scope Clarification - Admin Features",
        body_text="Please clarify whether the website includes an admin dashboard.",
        received_at=datetime(2026, 11, 18, 9, 30, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)
    assert cls.is_business_relevant is True
    assert cls.pipeline_category == "clarifications"
    assert cls.intent == "business_clarification"


def test_phase5_case8_negotiation(isolation_env):
    """Case 8: 'We would like a 15% discount on the proposed price.' -> Negotiation."""
    db, mb, _ = isolation_env
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="8008",
        uid_validity=1,
        message_id="<case8-nego@client.com>",
        sender="Procurement Lead <buyer@client.com>",
        subject="Commercial Terms Review",
        body_text="We would like a 15% discount on the proposed price.",
        received_at=datetime(2026, 11, 18, 9, 35, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)
    assert cls.is_business_relevant is True
    assert cls.pipeline_category == "negotiations"
    assert cls.intent == "negotiation"


def test_phase5_case9_new_lead(isolation_env):
    """Case 9: 'Could you share your pricing for a new website?' -> New Lead."""
    db, mb, _ = isolation_env
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="8009",
        uid_validity=1,
        message_id="<case9-new@startup.com>",
        sender="Founder <founder@startup.com>",
        subject="Web Development Enquiry",
        body_text="Could you share your pricing for a new website?",
        received_at=datetime(2026, 11, 18, 9, 40, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)
    assert cls.is_business_relevant is True
    assert cls.pipeline_category == "new_leads"
    assert cls.intent == "new_enquiry"


def test_phase5_case10_follow_up(isolation_env):
    """Case 10: 'The project development is progressing well. Please share the latest status.' -> Follow-up."""
    db, mb, _ = isolation_env
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="8010",
        uid_validity=1,
        message_id="<case10-status@partner.com>",
        sender="Project Sponsor <sponsor@partner.com>",
        subject="Project Status Update",
        body_text="The project development is progressing well. Please share the latest status.",
        received_at=datetime(2026, 11, 18, 9, 45, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)
    assert cls.is_business_relevant is True
    assert cls.pipeline_category == "follow_ups"
    assert cls.intent == "follow_up"


# =============================================================================
# PHASE 6: Strict Backend Pipeline Filtering & Data Isolation Tests
# =============================================================================

def test_strict_pipeline_filtering_isolation(isolation_env):
    """Verify that every pipeline returns ONLY its authoritative emails, and unrelated emails are excluded."""
    db, mb, settings = isolation_env
    classifier = HybridClassifier(db=db)

    # Insert 1 email for each of the 10 core categories
    emails_def = [
        ("po", "purchase_orders", "Please confirm our order against PO-2026-104.", "Order PO-104"),
        ("inv_req", "invoice_request", "Please share the invoice against our approved purchase order.", "Invoice Request"),
        ("inv_upd", "invoice_update", "The GST number on invoice INV-1048 is incorrect.", "Invoice Update"),
        ("remit", "payment_remittance", "We transferred ₹75,000. UTR: AXIS123456.", "Remittance Advice"),
        ("pay_fu", "payment_follow_up", "Please let us know when our pending payment will be processed.", "Payment Status"),
        ("pay_disp", "payment_dispute", "The invoice amount does not match our agreed quotation.", "Payment Dispute"),
        ("clarify", "clarifications", "Please clarify whether the website includes an admin dashboard.", "Clarification"),
        ("nego", "negotiations", "We would like a 15% discount on the proposed price.", "Negotiation"),
        ("lead", "new_leads", "Could you share your pricing for a new website?", "New Lead"),
        ("fu", "follow_ups", "The project development is progressing well. Please share the latest status.", "Follow up"),
    ]

    for uid, expected_cat, body, subj in emails_def:
        em = Email(
            mailbox_id=mb.id,
            account_email=mb.email_address,
            imap_uid=f"iso_{uid}",
            uid_validity=1,
            message_id=f"<iso_{uid}@test.com>",
            sender=f"Sender {uid} <sender_{uid}@test.com>",
            subject=subj,
            body_text=body,
            received_at=datetime.now(timezone.utc),
        )
        db.add(em)
        db.commit()
        cls = classifier.classify_email(em)
        assert cls.pipeline_category == expected_cat

    # Test each pipeline filter individually via backend endpoint function
    pipelines_to_test = [
        ("purchase_order", "purchase_orders", 1),
        ("invoice_request", "invoice_request", 1),
        ("invoice_update", "invoice_update", 1),
        ("payment_remittance", "payment_remittance", 1),
        ("payment_follow_up", "payment_follow_up", 1),
        ("payment_dispute", "payment_dispute", 1),
        ("clarification", "clarifications", 1),
        ("negotiation", "negotiations", 1),
        ("new_lead", "new_leads", 1),
        ("follow_up", "follow_ups", 1),
    ]

    for query_param, expected_category, expected_count in pipelines_to_test:
        # Test pipeline parameter
        resp_p = list_emails(db=db, settings=settings, pipeline=query_param)
        assert resp_p.total == expected_count, f"Expected {expected_count} for pipeline={query_param}, got {resp_p.total}"
        for item in resp_p.items:
            # GLOBAL INVARIANT: Authoritative primary category must equal pipeline category!
            assert item.classification.pipeline_category == expected_category

        # Test category parameter
        resp_c = list_emails(db=db, settings=settings, category=query_param)
        assert resp_c.total == expected_count, f"Expected {expected_count} for category={query_param}, got {resp_c.total}"
        for item in resp_c.items:
            assert item.classification.pipeline_category == expected_category


def test_empty_pipeline_returns_zero_emails(isolation_env):
    """Verify that requesting an empty pipeline returns total=0 and items=[], never all emails."""
    db, mb, settings = isolation_env

    # Insert only a single New Lead email
    em = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="single_lead",
        uid_validity=1,
        message_id="<single_lead@test.com>",
        sender="Alice <alice@test.com>",
        subject="Need a quotation for software development",
        body_text="Hi, please send a quotation for building our software.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(em)
    db.commit()
    HybridClassifier(db=db).classify_email(em)

    # Empty categories
    for empty_pipe in ["payment_dispute", "invoice_update", "purchase_order", "payment_follow_up"]:
        resp = list_emails(db=db, settings=settings, pipeline=empty_pipe)
        assert resp.total == 0, f"Expected 0 for empty pipeline {empty_pipe}, got {resp.total}"
        assert len(resp.items) == 0


def test_invalid_pipeline_returns_zero_emails_never_all(isolation_env):
    """CRITICAL REQUIREMENT: An invalid or unrecognized pipeline filter MUST return 0 emails, NEVER all emails!"""
    db, mb, settings = isolation_env

    # Insert an email
    em = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="some_email",
        uid_validity=1,
        message_id="<some_email@test.com>",
        sender="Bob <bob@test.com>",
        subject="Project consultation",
        body_text="Looking for a consultant.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(em)
    db.commit()
    HybridClassifier(db=db).classify_email(em)

    # Request invalid pipeline filters
    for bad_filter in ["non_existent_category", "invalid_pipe_123", "random_string", "undefined", "null"]:
        resp = list_emails(db=db, settings=settings, pipeline=bad_filter)
        assert resp.total == 0, f"Expected 0 for invalid filter '{bad_filter}', but got {resp.total}"
        assert len(resp.items) == 0

        # Also via category parameter
        resp_cat = list_emails(db=db, settings=settings, category=bad_filter)
        assert resp_cat.total == 0
        assert len(resp_cat.items) == 0


def test_all_ingested_emails_returns_all_without_pipeline_filter(isolation_env):
    """Verify that 'All Ingested Emails' (no pipeline filter) returns all emails in the active mailbox."""
    db, mb, settings = isolation_env
    classifier = HybridClassifier(db=db)

    # Insert 3 diverse emails
    for i, subj in enumerate(["PO Confirmation", "Invoice Dispute", "General Inquiry"]):
        em = Email(
            mailbox_id=mb.id,
            account_email=mb.email_address,
            imap_uid=f"all_{i}",
            uid_validity=1,
            message_id=f"<all_{i}@test.com>",
            sender=f"Client {i} <client{i}@test.com>",
            subject=subj,
            body_text=f"Body text for message {i}",
            received_at=datetime.now(timezone.utc),
        )
        db.add(em)
        db.commit()
        classifier.classify_email(em)

    # Call list_emails with no pipeline filter
    resp = list_emails(db=db, settings=settings)
    assert resp.total == 3
    assert len(resp.items) == 3


def test_reclassification_moves_email_across_pipelines(isolation_env):
    """Verify that manual reclassification moves an email from its old pipeline to its new pipeline."""
    db, mb, settings = isolation_env
    classifier = HybridClassifier(db=db)

    # Insert an email initially classified as new_leads
    em = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="reclass_01",
        uid_validity=1,
        message_id="<reclass@test.com>",
        sender="Prospect <prospect@test.com>",
        subject="Pricing inquiry for cloud solution",
        body_text="Could you please share your pricing?",
        received_at=datetime.now(timezone.utc),
    )
    db.add(em)
    db.commit()
    cls = classifier.classify_email(em)
    assert cls.pipeline_category == "new_leads"

    # Verify present in new_leads, absent in negotiations
    resp_nl1 = list_emails(db=db, settings=settings, pipeline="new_lead")
    assert resp_nl1.total == 1
    resp_nego1 = list_emails(db=db, settings=settings, pipeline="negotiation")
    assert resp_nego1.total == 0

    # User reclassifies to negotiations via manual correction
    corr_payload = ClassificationCorrectionRequest(
        pipeline_category="negotiations",
        intent="negotiation",
        lead_stage="negotiation",
        notes="User corrected from new_lead to negotiation",
    )
    corrected = correct_classification(classification_id=cls.id, correction=corr_payload, db=db)
    assert corrected.pipeline_category == "negotiations"

    # Verify email has DISAPPEARED from new_leads
    resp_nl2 = list_emails(db=db, settings=settings, pipeline="new_lead")
    assert resp_nl2.total == 0

    # Verify email has APPEARED in negotiations
    resp_nego2 = list_emails(db=db, settings=settings, pipeline="negotiation")
    assert resp_nego2.total == 1
    assert resp_nego2.items[0].id == em.id
    assert resp_nego2.items[0].classification.pipeline_category == "negotiations"


def test_mailbox_isolation_prevents_cross_mailbox_leakage(isolation_env):
    """Verify that pipeline queries strictly scope to the active mailbox and never leak across mailboxes."""
    db, mb1, settings = isolation_env
    classifier = HybridClassifier(db=db)

    # Create a secondary mailbox
    mb2 = Mailbox(
        tenant_id=mb1.tenant_id,
        email_address="secondary@company.com",
        is_active=False,
    )
    db.add(mb2)
    db.commit()

    # Add a PO email to Mailbox 1
    em1 = Email(
        mailbox_id=mb1.id,
        account_email=mb1.email_address,
        imap_uid="mb1_po",
        uid_validity=1,
        message_id="<mb1_po@test.com>",
        sender="Buyer 1 <buyer1@test.com>",
        subject="Order Confirmation PO-1",
        body_text="Please confirm our order against PO-2026-101.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(em1)

    # Add a PO email to Mailbox 2
    em2 = Email(
        mailbox_id=mb2.id,
        account_email=mb2.email_address,
        imap_uid="mb2_po",
        uid_validity=1,
        message_id="<mb2_po@test.com>",
        sender="Buyer 2 <buyer2@test.com>",
        subject="Order Confirmation PO-2",
        body_text="Please confirm our order against PO-2026-102.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(em2)
    db.commit()

    classifier.classify_email(em1)
    classifier.classify_email(em2)

    # Mailbox 1 is active -> querying purchase_order must return ONLY Mailbox 1's email
    resp1 = list_emails(db=db, settings=settings, pipeline="purchase_order")
    assert resp1.total == 1
    assert resp1.items[0].id == em1.id

    # Switch active mailbox to Mailbox 2
    from app.services.mailbox_service import MailboxService
    MailboxService(db=db, settings=settings).switch_active_mailbox(mb2.id)

    # Querying purchase_order must now return ONLY Mailbox 2's email
    resp2 = list_emails(db=db, settings=settings, pipeline="purchase_order")
    assert resp2.total == 1
    assert resp2.items[0].id == em2.id


def test_dashboard_counts_match_pipeline_query_results_exactly(isolation_env):
    """Verify that Dashboard summary counters match the exact number of emails returned by pipeline queries."""
    db, mb, settings = isolation_env
    classifier = HybridClassifier(db=db)

    # Insert 2 POs, 1 Invoice Request, 1 Remittance, 1 Dispute
    emails_data = [
        ("po1", "purchase_orders", "Please confirm our order against PO-2026-901.", "PO 901"),
        ("po2", "purchase_orders", "Please confirm our order against PO-2026-902.", "PO 902"),
        ("inv1", "invoice_request", "Please share the invoice against our approved purchase order.", "Invoice Req"),
        ("rem1", "payment_remittance", "We transferred ₹75,000. UTR: AXIS999999.", "Remittance"),
        ("disp1", "payment_dispute", "The invoice amount does not match our agreed quotation.", "Dispute"),
    ]

    for uid, _, body, subj in emails_data:
        em = Email(
            mailbox_id=mb.id,
            account_email=mb.email_address,
            imap_uid=f"cnt_{uid}",
            uid_validity=1,
            message_id=f"<cnt_{uid}@test.com>",
            sender=f"Client <client_{uid}@test.com>",
            subject=subj,
            body_text=body,
            received_at=datetime.now(timezone.utc),
        )
        db.add(em)
        db.commit()
        classifier.classify_email(em)

    # Fetch dashboard summary
    summary = get_dashboard_summary(db=db, settings=settings)

    # Verify counts match exact query totals
    assert summary.purchase_orders_count == 2
    po_query = list_emails(db=db, settings=settings, pipeline="purchase_order")
    assert po_query.total == summary.purchase_orders_count

    assert summary.invoice_requests_count == 1
    inv_req_query = list_emails(db=db, settings=settings, pipeline="invoice_request")
    assert inv_req_query.total == summary.invoice_requests_count

    assert summary.payment_remittances_count == 1
    rem_query = list_emails(db=db, settings=settings, pipeline="payment_remittance")
    assert rem_query.total == summary.payment_remittances_count

    assert summary.payment_disputes_count == 1
    disp_query = list_emails(db=db, settings=settings, pipeline="payment_dispute")
    assert disp_query.total == summary.payment_disputes_count
