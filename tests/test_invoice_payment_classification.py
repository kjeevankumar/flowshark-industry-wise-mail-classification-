"""Comprehensive Test Suite for FlowShark Invoice, PO, and Payment Intelligence.

Verifies:
1. PO Received: multi-attribute evidence detection, metadata extraction, Accounts task creation, and NO automatic WON stage.
2. Invoice Request: customer requesting tax invoice against PO or agreed project (distinct from quotation).
3. Quotation Disambiguation: price enquiry / quote request is classified as new_enquiry / new_leads, NOT invoice_request.
4. Invoice Update: GSTIN correction, billing address change, revised invoice request.
5. Payment Remittance: UTR/wire transfer detection, CommercialEvent recording, and NO automatic WON stage.
6. Payment Follow-up: customer asking about payment receipt status or confirming expected payment date.
7. Payment Dispute: billing discrepancy / duplicate charge detection, high-priority Accounts task creation.
8. Non-Business Billing: automated SaaS receipt (Google/AWS) excluded from commercial pipelines into System & Alerts.
9. Inbound Direction Guard: incoming emails are NEVER classified as invoice_issued.
10. Inbox API and Dashboard Commercial Sub-filter counts.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.models.classification_model import Classification
from app.models.commercial_event_model import CommercialEvent
from app.models.contact_model import Contact
from app.models.email_model import Email
from app.models.lead_model import Lead
from app.models.mailbox_model import Mailbox
from app.models.task_model import Task
from app.services.hybrid_classifier import HybridClassifier
from app.services.rule_classifier import (
    RuleBasedClassifier,
    extract_invoice_metadata,
    extract_payment_metadata,
    extract_po_metadata,
)
from app.routes.dashboard_routes import get_dashboard_summary
from app.routes.email_inbox_routes import list_emails
from app.config import Settings


def test_purchase_order_detection_and_task_creation(test_db):
    """Test 1: PO Received with PO#, line items, amounts -> Accounts task created, opportunity NOT set to Won."""
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    # 1. First establish an active negotiation lead
    email_nego = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="7001",
        uid_validity=1,
        message_id="<nego-7001@acmecorp.com>",
        gmail_thread_id="thread_acme_po_01",
        sender="David Miller <david@acmecorp.com>",
        subject="Commercial Proposal Review - DevOps Automation",
        body_text="We received your proposal for $35,000. We would like to finalize commercial terms.",
        received_at=datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc),
    )
    db.add(email_nego)
    db.commit()
    cls_nego = classifier.classify_email(email_nego)
    lead = db.query(Lead).filter(Lead.id == cls_nego.lead_id).first()
    assert lead is not None
    assert lead.status == "negotiation"

    # 2. Inbound PO email referencing negotiation thread
    email_po = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="7002",
        uid_validity=1,
        message_id="<po-7002@acmecorp.com>",
        gmail_thread_id="thread_acme_po_01",
        in_reply_to="<nego-7001@acmecorp.com>",
        sender="David Miller <david@acmecorp.com>",
        subject="Purchase Order PO-2026-8812 - DevOps Automation Implementation",
        body_text=(
            "Hi Team,\n\n"
            "We have approved the quote and are issuing the formal purchase order.\n"
            "Purchase Order Number: PO-2026-8812\n"
            "Approved Total Amount: $35,000 USD\n"
            "Payment Terms: Net 30 days\n"
            "Scope: Enterprise DevOps Automation & Cloud Migration Phase 1\n"
            "Attached is our official signed PO document.\n\n"
            "Please acknowledge receipt and prepare the tax invoice.\n\n"
            "Best regards,\nDavid Miller\nVP Procurement, Acme Corp"
        ),
        has_attachments=True,
        attachment_count=1,
        received_at=datetime(2026, 11, 16, 11, 0, tzinfo=timezone.utc),
    )
    db.add(email_po)
    db.commit()

    cls_po = classifier.classify_email(email_po)

    # Classification assertions
    assert cls_po.pipeline_category == "purchase_orders"
    assert cls_po.intent == "purchase_order"
    assert cls_po.commercial_intent == "purchase_order"

    # CRITICAL: Opportunity must NOT be automatically marked Won solely because PO arrived!
    db.refresh(lead)
    assert lead.status != "won"

    # Metadata extraction assertions
    po_meta = extract_po_metadata(email_po.body_text, email_po.subject)
    assert "8812" in po_meta.get("po_number", "")
    assert po_meta.get("amount") == 35000.0
    assert "net 30" in po_meta.get("payment_terms", "").lower()

    # CommercialEvent record assertion
    comm_event = db.query(CommercialEvent).filter(CommercialEvent.email_id == email_po.id).first()
    assert comm_event is not None
    assert comm_event.event_type == "po_received"
    assert "8812" in (comm_event.reference_number or "")
    assert comm_event.amount == 35000.0

    # Task creation assertion: Task created specifically for Accounts team
    tasks = db.query(Task).filter(Task.email_id == email_po.id).all()
    assert len(tasks) > 0
    accounts_task = next((t for t in tasks if t.assigned_to == "Accounts"), None)
    assert accounts_task is not None
    assert "tax invoice" in accounts_task.title.lower() or "accounts" in accounts_task.title.lower()


def test_invoice_request_classification(test_db):
    """Test 2: Invoice Request -> Customer asks for tax invoice against project/PO -> NOT quotation, NOT invoice update."""
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="7003",
        uid_validity=1,
        message_id="<inv-req-7003@summittech.com>",
        gmail_thread_id="thread_summit_01",
        sender="Finance Team <ap@summittech.com>",
        subject="Request for Tax Invoice against PO-4921 - Cloud Deployment",
        body_text=(
            "Hello,\n\n"
            "The initial deployment milestone for the cloud infrastructure has been completed successfully.\n"
            "Could you please share the tax invoice against PO-4921 in the amount of $18,500?\n"
            "Kindly include our PO number on the invoice so our accounts payable team can process it.\n\n"
            "Thanks,\nAccounts Payable, Summit Technologies"
        ),
        received_at=datetime(2026, 11, 16, 14, 0, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)

    assert cls.pipeline_category == "invoice_request"
    assert cls.intent == "invoice_request"
    assert cls.commercial_intent == "invoice_request"

    # Commercial event
    comm_event = db.query(CommercialEvent).filter(CommercialEvent.email_id == email.id).first()
    assert comm_event is not None
    assert comm_event.event_type == "invoice_requested"

    # Task created for Accounts
    tasks = db.query(Task).filter(Task.email_id == email.id).all()
    assert any(t.assigned_to == "Accounts" for t in tasks)


def test_quotation_request_disambiguation(test_db):
    """Test 3: Quotation request (price enquiry) is classified as new_enquiry / new_leads, NOT invoice_request."""
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="7004",
        uid_validity=1,
        message_id="<quote-req-7004@newprospect.com>",
        gmail_thread_id="thread_quote_01",
        sender="Sarah Jenkins <sarah@newprospect.com>",
        subject="Request for Quotation - E-commerce Mobile App Development",
        body_text=(
            "Hi FlowShark Team,\n\n"
            "We are looking for a development partner to build our mobile shopping app.\n"
            "Could you please share your quotation and pricing estimate for a 3-month project?\n"
            "What would be the cost to build a React Native cross-platform application?\n\n"
            "Looking forward to your quotation.\n\n"
            "Best,\nSarah Jenkins"
        ),
        received_at=datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)

    # Must be new_leads, NOT invoice_request!
    assert cls.pipeline_category == "new_leads"
    assert cls.intent == "new_enquiry"
    assert cls.commercial_intent == "quotation"
    assert cls.pipeline_category != "invoice_request"


def test_invoice_update_classification(test_db):
    """Test 4: Invoice Update -> Customer requests GST/tax ID correction, billing address change, or revised invoice."""
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="7005",
        uid_validity=1,
        message_id="<inv-update-7005@globalcorp.com>",
        gmail_thread_id="thread_update_01",
        sender="Billing Ops <billing@globalcorp.com>",
        subject="Correction Required on Invoice #INV-2026-9021 - GST Number Update",
        body_text=(
            "Hi Accounts Team,\n\n"
            "We reviewed invoice #INV-2026-9021 dated November 14.\n"
            "Please update the GST number on the invoice to 29ABCDE1234F1Z5.\n"
            "Also, our billing address should be updated to: 100 Enterprise Way, Suite 400.\n"
            "Kindly reissue the revised invoice with these corrections.\n\n"
            "Regards,\nGlobal Logistics Corp"
        ),
        received_at=datetime(2026, 11, 17, 9, 30, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)

    assert cls.pipeline_category == "invoice_update"
    assert cls.intent == "invoice_update"
    assert cls.commercial_intent == "invoice_update"

    inv_meta = extract_invoice_metadata(email.body_text, email.subject)
    assert inv_meta.get("gst_number") == "29ABCDE1234F1Z5"
    assert "9021" in inv_meta.get("invoice_number", "")

    comm_event = db.query(CommercialEvent).filter(CommercialEvent.email_id == email.id).first()
    assert comm_event is not None
    assert comm_event.event_type == "invoice_update_requested"


def test_payment_remittance_classification_and_not_won(test_db):
    """Test 5: Payment Remittance -> UTR number, wire transfer -> NOT verified confirmation, opportunity NOT set to Won."""
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    # Existing active lead
    lead = Lead(
        mailbox_id=mb.id,
        contact_id=1,
        title="AWS Cloud Architecture Engagement",
        status="negotiation",
        priority="hot",
    )
    db.add(lead)
    db.commit()

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="7006",
        uid_validity=1,
        message_id="<remit-7006@crestview.com>",
        gmail_thread_id="thread_crestview_remit",
        sender="Finance <accounts@crestview.com>",
        subject="Payment Remittance Advice - Wire Transfer UTR# HDFC0001928374",
        body_text=(
            "Dear Finance Team,\n\n"
            "We have processed payment of $22,400 via wire transfer for Invoice #INV-1092.\n"
            "Bank Reference / UTR Number: HDFC0001928374\n"
            "Transaction Date: November 17, 2026\n"
            "Remittance advice attached.\n\n"
            "Please verify credit into your bank account.\n\n"
            "Regards,\nCrestview Capital Finance"
        ),
        has_attachments=True,
        attachment_count=1,
        received_at=datetime(2026, 11, 17, 11, 0, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)

    assert cls.pipeline_category in ["payment_remittance", "invoices"]
    assert cls.intent in ["payment_remittance", "invoice"]
    assert cls.commercial_intent == "payment_remittance"

    # CRITICAL: Remittance advice must NOT automatically mark lead status WON!
    db.refresh(lead)
    assert lead.status != "won"

    pay_meta = extract_payment_metadata(email.body_text, email.subject)
    assert pay_meta.get("utr_number") == "HDFC0001928374"
    assert pay_meta.get("amount") == 22400.0

    comm_event = db.query(CommercialEvent).filter(CommercialEvent.email_id == email.id).first()
    assert comm_event is not None
    assert comm_event.event_type == "payment_remittance_received"
    assert comm_event.reference_number == "HDFC0001928374"


def test_payment_follow_up_classification(test_db):
    """Test 6: Payment Follow-up -> Customer asking about pending payment status or expected payment date."""
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="7007",
        uid_validity=1,
        message_id="<pay-followup-7007@apexlogistics.com>",
        gmail_thread_id="thread_apex_pay_01",
        sender="Marcus Vance <marcus@apexlogistics.com>",
        subject="Status of pending payment - Invoice #8841",
        body_text=(
            "Hi Team,\n\n"
            "Could you please confirm if you received the payment sent yesterday for invoice #8841?\n"
            "Our treasury confirmed the wire transfer was released, please let us know the status.\n\n"
            "Best,\nMarcus"
        ),
        received_at=datetime(2026, 11, 17, 14, 0, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)

    assert cls.pipeline_category in ["payment_follow_up", "follow_ups"]
    assert cls.commercial_intent == "payment_follow_up"

    comm_event = db.query(CommercialEvent).filter(CommercialEvent.email_id == email.id).first()
    assert comm_event is not None


def test_payment_dispute_classification(test_db):
    """Test 7: Payment Dispute -> Customer challenges invoice amount, duplicate billing, or taxes -> High priority task."""
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="7008",
        uid_validity=1,
        message_id="<dispute-7008@horizonhealth.com>",
        gmail_thread_id="thread_dispute_01",
        sender="Audit Dept <audit@horizonhealth.com>",
        subject="Billing Discrepancy & Dispute on Invoice #INV-5510",
        body_text=(
            "Dear Accounts,\n\n"
            "We are disputing the charge of $6,500 on invoice #INV-5510.\n"
            "We noticed a duplicate billing for server maintenance hours that were already paid last month.\n"
            "Additionally, the tax calculation is incorrect for our non-profit entity.\n"
            "We are withholding payment until this billing discrepancy is resolved.\n\n"
            "Sincerely,\nHorizon Healthcare Audit Team"
        ),
        received_at=datetime(2026, 11, 17, 16, 0, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)

    assert cls.pipeline_category == "payment_dispute"
    assert cls.intent == "payment_dispute"
    assert cls.commercial_intent == "payment_dispute"

    comm_event = db.query(CommercialEvent).filter(CommercialEvent.email_id == email.id).first()
    assert comm_event is not None
    assert comm_event.event_type == "payment_dispute_raised"

    # High priority task for Accounts
    tasks = db.query(Task).filter(Task.email_id == email.id).all()
    accounts_task = next((t for t in tasks if t.assigned_to == "Accounts"), None)
    assert accounts_task is not None
    assert accounts_task.priority == "high"


def test_inbound_never_classified_as_invoice_issued(test_db):
    """Test 8: Inbound email mentioning 'invoice issued' must NEVER be classified as invoice_issued."""
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="7009",
        uid_validity=1,
        message_id="<inbound-issue-7009@vendor.com>",
        gmail_thread_id="thread_issue_01",
        sender="Vendor Notifications <billing@vendor.com>",
        subject="Notification: Invoice Issued for your review",
        body_text="An invoice has been issued for your recent purchase. Invoice #INV-7721.",
        received_at=datetime(2026, 11, 17, 17, 0, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)

    # Inbound email must NEVER be commercial_intent='invoice_issued'
    assert cls.commercial_intent != "invoice_issued"


def test_non_business_billing_stays_in_system_alerts(test_db):
    """Test 9: Non-business automated billing receipt from Google/AWS stays in System & Alerts."""
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="7010",
        uid_validity=1,
        message_id="<aws-bill-7010@amazon.com>",
        gmail_thread_id="thread_aws_bill_01",
        sender="AWS Payments <no-reply-aws@amazon.com>",
        subject="Amazon Web Services Invoice Available [Account: 1234567890]",
        body_text="Your Amazon Web Services invoice for October 2026 is now available. Total amount charged: $142.10.",
        received_at=datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)

    assert cls.is_business_relevant is False
    assert cls.pipeline_category is None


def test_inbox_and_dashboard_commercial_filters(test_db):
    """Test 10: Verify API category filters and dashboard subcategory counts."""
    db, mb = test_db
    settings = Settings()

    # Query dashboard summary directly via route handler
    summary = get_dashboard_summary(business_only=True, db=db, settings=settings)
    assert hasattr(summary, "invoice_requests_count")
    assert hasattr(summary, "invoice_updates_count")
    assert hasattr(summary, "payment_remittances_count")
    assert hasattr(summary, "payment_followups_count")
    assert hasattr(summary, "payment_disputes_count")
    assert hasattr(summary, "payments_count")
    assert hasattr(summary, "invoice_billing_count")

    # Query inbox listing with category filter
    po_res = list_emails(category="purchase_orders", db=db, settings=settings)
    assert isinstance(po_res.items, list)

    inv_req_res = list_emails(category="invoice_request", db=db, settings=settings)
    assert isinstance(inv_req_res.items, list)

    pay_remit_res = list_emails(category="payment_remittance", db=db, settings=settings)
    assert isinstance(pay_remit_res.items, list)
