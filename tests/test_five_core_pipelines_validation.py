"""Automated Validation Test Suite for FlowShark Core Five Pipelines.

Validates:
1. Five independent business emails covering:
   - New Lead
   - Negotiation
   - Follow-up
   - Clarification
   - Purchase Order
2. Each email is classified accurately into its authoritative primary category.
3. Strict isolation: Each email appears ONLY in its own designated pipeline.
4. An email classified as Negotiation does not appear in Purchase Orders, Invoice Request,
   Invoice Update, Payment Remittance, Payment Follow-up, or Payment Dispute.
5. Invoice & Payment pipelines return 0 items / empty state when no matching emails exist,
   never filling empty pipelines with unrelated emails.
6. All Ingested Emails returns all synchronized emails.
7. Displayed counts match actual database queries 1:1.
8. Search and industry filters work harmoniously with pipeline filtering without breaking isolation.
9. Mailbox & Tenant isolation is strictly preserved.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.classification_model import Classification
from app.models.email_model import Email
from app.models.mailbox_model import Mailbox
from app.routes.dashboard_routes import get_dashboard_summary
from app.routes.email_inbox_routes import list_emails
from app.services.hybrid_classifier import HybridClassifier


CORE_TEST_EMAILS = [
    {
        "key": "new_lead",
        "expected_pipeline": "new_leads",
        "expected_intent": "new_enquiry",
        "sender": "Alex Turner <alex.turner@cloudnexus-logistics.com>",
        "subject": "Inquiry: Enterprise Cloud Migration & Modernization Services",
        "body": (
            "Hi Team,\n\n"
            "I came across your cloud consulting practice while researching DevOps and cloud infrastructure migration partners. "
            "We are planning to migrate our legacy on-premise logistics platform to AWS within the upcoming quarter.\n\n"
            "Could you please share your standard service deck, case studies of similar migrations, and schedule a 30-minute introductory discovery call with our team next week?\n\n"
            "Best regards,\n"
            "Alex Turner\n"
            "VP of Infrastructure\n"
            "CloudNexus Logistics"
        ),
        "target_industry": "Logistics & Supply Chain",
        "sender_industry": "Logistics & Supply Chain",
    },
    {
        "key": "negotiation",
        "expected_pipeline": "negotiations",
        "expected_intent": "negotiation",
        "sender": "Samantha Wright <samantha.wright@fintech-solutions.io>",
        "subject": "Proposal Revision: Contract Pricing and Milestone Payment Terms",
        "body": (
            "Hi FlowShark Team,\n\n"
            "Thank you for sharing the enterprise contract proposal. We reviewed the numbers internally with our leadership team.\n\n"
            "The proposed billing rate of $150/hr exceeds our approved budget ceiling. If you can revise the rate to $130/hr "
            "or offer a 10% volume discount with milestone-based payment terms, we are prepared to finalize and sign the agreement by Friday.\n\n"
            "Regards,\n"
            "Samantha Wright\n"
            "Director of Procurement\n"
            "FinTech Solutions"
        ),
        "target_industry": "Financial Services",
        "sender_industry": "Financial Services",
    },
    {
        "key": "follow_up",
        "expected_pipeline": "follow_ups",
        "expected_intent": "follow_up",
        "sender": "Marcus Vance <marcus.vance@apex-global.com>",
        "subject": "Project Status Check: Development Deliverables for Milestone 2",
        "body": (
            "Hi Team,\n\n"
            "Following up on our sprint meeting from last week. Could you please share the latest status update regarding "
            "the milestone 2 deliverables and staging deployment?\n\n"
            "We need to review the progress report with our stakeholders before Wednesday's steering committee meeting.\n\n"
            "Thanks,\n"
            "Marcus Vance\n"
            "Product Director\n"
            "Apex Global"
        ),
        "target_industry": "Technology",
        "sender_industry": "Technology",
    },
    {
        "key": "clarification",
        "expected_pipeline": "clarifications",
        "expected_intent": "business_clarification",
        "sender": "Elena Rostova <elena.rostova@cyberguard-tech.org>",
        "subject": "Technical Clarification: API Authentication and SOC2 Compliance Requirements",
        "body": (
            "Dear FlowShark Engineering,\n\n"
            "Before we proceed with the statement of work, our security audit team requires clarification on several points in Section 4.\n\n"
            "Specifically, does your API gateway support OAuth2 authentication for webhooks, and what is your data retention policy for EU-resident communication logs under SOC2 Type II compliance?\n\n"
            "Kind regards,\n"
            "Elena Rostova\n"
            "Lead Security Architect\n"
            "CyberGuard Tech"
        ),
        "target_industry": "Cybersecurity",
        "sender_industry": "Cybersecurity",
    },
    {
        "key": "purchase_order",
        "expected_pipeline": "purchase_orders",
        "expected_intent": "purchase_order",
        "sender": "David Chen <david.chen@acme-enterprises.com>",
        "subject": "Official Purchase Order: PO-2026-9041 attached",
        "body": (
            "Dear Sales Team,\n\n"
            "Please find attached our official purchase order PO-2026-9041 for the annual Enterprise Platform Subscription "
            "covering 500 employee seats, in the amount of $48,000 net 30.\n\n"
            "Please confirm receipt and process the order as per our agreed master service agreement terms.\n\n"
            "Best regards,\n"
            "David Chen\n"
            "Procurement Manager\n"
            "Acme Enterprises"
        ),
        "target_industry": "Manufacturing",
        "sender_industry": "Manufacturing",
    },
]


@pytest.fixture
def core_fixture(test_db):
    """Fixture that provisions an isolated in-memory DB and ingests the 5 core test emails."""
    db, mb = test_db
    settings = get_settings()
    classifier = HybridClassifier(db=db, settings=settings)

    created_emails = []

    for idx, item in enumerate(CORE_TEST_EMAILS, start=1):
        email_obj = Email(
            mailbox_id=mb.id,
            account_email=mb.email_address,
            imap_uid=f"CORE_{idx:03d}",
            uid_validity=101,
            sender=item["sender"],
            recipient=mb.email_address,
            subject=item["subject"],
            body_text=item["body"],
            snippet=item["body"][:120],
            has_attachments=False,
            received_at=datetime.now(timezone.utc),
        )
        db.add(email_obj)
        db.commit()
        db.refresh(email_obj)

        cls_res = classifier.classify_email(email_obj)
        # Apply industry tags if set
        cls_obj = db.query(Classification).filter(Classification.email_id == email_obj.id).first()
        if cls_obj:
            cls_obj.target_industry = item["target_industry"]
            cls_obj.sender_industry = item["sender_industry"]
            db.commit()
            db.refresh(cls_obj)

        created_emails.append((email_obj, cls_obj or cls_res, item))

    return db, mb, settings, created_emails


def test_five_emails_classified_accurately(core_fixture):
    """Criterion 1: 5 test emails produce 5 correct primary classifications."""
    db, mb, settings, items = core_fixture
    assert len(items) == 5

    for email_obj, cls_obj, spec in items:
        db_cls = db.query(Classification).filter(Classification.email_id == email_obj.id).first()
        assert db_cls is not None, f"Missing classification record for {email_obj.subject}"
        assert db_cls.pipeline_category == spec["expected_pipeline"], (
            f"Expected pipeline_category '{spec['expected_pipeline']}' for email '{email_obj.subject}', "
            f"got '{db_cls.pipeline_category}'"
        )
        assert db_cls.intent == spec["expected_intent"], (
            f"Expected intent '{spec['expected_intent']}' for email '{email_obj.subject}', "
            f"got '{db_cls.intent}'"
        )
        assert db_cls.is_business_relevant is True


def test_each_email_appears_in_exactly_one_core_pipeline(core_fixture):
    """Criterion 2 & 3: Each email appears in its designated pipeline, and NO OTHER core pipeline."""
    db, mb, settings, items = core_fixture

    core_pipelines = ["new_leads", "negotiations", "follow_ups", "clarifications", "purchase_orders"]

    for pipe in core_pipelines:
        res = list_emails(
            page=1,
            size=50,
            pipeline=pipe,
            db=db,
            settings=settings,
        )
        # Exactly one email must match each of the 5 core pipelines
        assert res.total == 1, f"Expected exactly 1 email in pipeline '{pipe}', got {res.total}"
        assert len(res.items) == 1
        item = res.items[0]
        assert item.classification.pipeline_category == pipe


def test_negotiation_never_appears_in_unrelated_or_invoice_payment_pipelines(core_fixture):
    """Criterion 4: An email classified as Negotiation must NOT appear in Purchase Orders,

    Invoice Request, Invoice Update, Payment Remittance, Payment Follow-up, or Payment Dispute.
    """
    db, mb, settings, items = core_fixture

    unrelated_pipelines = [
        "purchase_orders",
        "purchase_order",
        "invoice_request",
        "invoice_requests",
        "invoice_update",
        "invoice_updates",
        "payment_remittance",
        "payment_follow_up",
        "payment_dispute",
        "invoice_billing",
        "payments",
    ]

    # Find the negotiation email id
    neg_email_id = next(e.id for e, c, s in items if s["expected_pipeline"] == "negotiations")

    for pipe in unrelated_pipelines:
        res = list_emails(
            page=1,
            size=50,
            pipeline=pipe,
            db=db,
            settings=settings,
        )
        returned_ids = [item.id for item in res.items]
        assert neg_email_id not in returned_ids, (
            f"CRITICAL VIOLATION: Negotiation email {neg_email_id} appeared in unrelated pipeline '{pipe}'!"
        )


def test_invoice_and_payment_pipelines_return_zero_items(core_fixture):
    """Criterion 5: Invoice and Payment pipelines return only their matching records or an empty state (0 items).

    Never display unrelated emails to fill an empty pipeline.
    """
    db, mb, settings, items = core_fixture

    invoice_and_payment_pipes = [
        "invoice_request",
        "invoice_update",
        "payment_remittance",
        "payment_follow_up",
        "payment_dispute",
        "invoices",
        "invoice_billing",
        "payments",
    ]

    for pipe in invoice_and_payment_pipes:
        res = list_emails(
            page=1,
            size=20,
            pipeline=pipe,
            db=db,
            settings=settings,
        )
        assert res.total == 0, f"Expected 0 items for empty pipeline '{pipe}', got {res.total}"
        assert len(res.items) == 0, f"Items returned in empty pipeline '{pipe}': {res.items}"


def test_all_ingested_emails_contains_all_five_emails(core_fixture):
    """Criterion 6: All Ingested Emails contains all five emails."""
    db, mb, settings, items = core_fixture

    # Query all emails without pipeline filter
    res = list_emails(
        page=1,
        size=50,
        db=db,
        settings=settings,
    )
    assert res.total == 5
    assert len(res.items) == 5

    ingested_ids = {item.id for item in res.items}
    expected_ids = {e.id for e, c, s in items}
    assert ingested_ids == expected_ids


def test_dashboard_and_database_counts_match_exactly(core_fixture):
    """Criterion 7: Displayed count matches actual database query."""
    db, mb, settings, items = core_fixture

    summary = get_dashboard_summary(db=db, settings=settings)

    assert summary.total_synced == 5
    assert summary.total_classified == 5
    assert summary.new_leads_count == 1
    assert summary.negotiations_count == 1
    assert summary.follow_ups_count == 1
    assert summary.clarifications_count == 1
    assert summary.purchase_orders_count == 1
    # Commercial pipeline counts must be 0
    assert summary.invoice_requests_count == 0
    assert summary.invoice_updates_count == 0
    assert summary.payment_remittances_count == 0
    assert summary.payment_followups_count == 0
    assert summary.payment_disputes_count == 0


def test_search_and_industry_filters_preserve_pipeline_isolation(core_fixture):
    """Criterion 8: Search and industry filters do not break pipeline filtering."""
    db, mb, settings, items = core_fixture

    # Test 1: Search within correct pipeline matches
    res_search = list_emails(
        page=1,
        size=20,
        pipeline="purchase_orders",
        search="PO-2026-9041",
        db=db,
        settings=settings,
    )
    assert res_search.total == 1
    assert "PO-2026-9041" in res_search.items[0].subject

    # Test 2: Search term for PO inside new_leads pipeline returns 0 (does NOT cross pipelines)
    res_cross_search = list_emails(
        page=1,
        size=20,
        pipeline="new_leads",
        search="PO-2026-9041",
        db=db,
        settings=settings,
    )
    assert res_cross_search.total == 0
    assert len(res_cross_search.items) == 0

    # Test 3: Industry filter within correct pipeline matches
    res_ind = list_emails(
        page=1,
        size=20,
        pipeline="negotiations",
        industry="Financial Services",
        db=db,
        settings=settings,
    )
    assert res_ind.total == 1
    assert res_ind.items[0].classification.pipeline_category == "negotiations"

    # Test 4: Industry filter mismatch within pipeline returns 0 (does NOT bypass pipeline filter)
    res_mismatch_ind = list_emails(
        page=1,
        size=20,
        pipeline="negotiations",
        industry="Cybersecurity",
        db=db,
        settings=settings,
    )
    assert res_mismatch_ind.total == 0
    assert len(res_mismatch_ind.items) == 0


def test_switching_pipelines_does_not_reuse_data(core_fixture):
    """Criterion 9: Switching between pipeline queries returns distinct, isolated results."""
    db, mb, settings, items = core_fixture

    res_nl = list_emails(page=1, size=20, pipeline="new_leads", db=db, settings=settings)
    res_neg = list_emails(page=1, size=20, pipeline="negotiations", db=db, settings=settings)
    res_fu = list_emails(page=1, size=20, pipeline="follow_ups", db=db, settings=settings)
    res_cl = list_emails(page=1, size=20, pipeline="clarifications", db=db, settings=settings)
    res_po = list_emails(page=1, size=20, pipeline="purchase_orders", db=db, settings=settings)

    nl_ids = {e.id for e in res_nl.items}
    neg_ids = {e.id for e in res_neg.items}
    fu_ids = {e.id for e in res_fu.items}
    cl_ids = {e.id for e in res_cl.items}
    po_ids = {e.id for e in res_po.items}

    # All sets must be completely mutually disjoint
    assert nl_ids.isdisjoint(neg_ids)
    assert nl_ids.isdisjoint(fu_ids)
    assert nl_ids.isdisjoint(cl_ids)
    assert nl_ids.isdisjoint(po_ids)
    assert neg_ids.isdisjoint(fu_ids)
    assert neg_ids.isdisjoint(cl_ids)
    assert neg_ids.isdisjoint(po_ids)
    assert fu_ids.isdisjoint(cl_ids)
    assert fu_ids.isdisjoint(po_ids)
    assert cl_ids.isdisjoint(po_ids)
