"""Comprehensive Test Suite for FlowShark Production-Grade Intelligence Pipeline.

Validates:
1. Stable Email Identity and Zero Cross-Email / Cross-Opportunity Mixing (K Jeevan Kumar proposal vs Crestview remittance).
2. Customer Organization Industry vs Requested Solution Domain Separation (Apex Logistics Global).
3. Payment rail banking exclusion (Chase Commercial Banking wire remittance).
4. Strict Lead Pipeline vs Lifecycle Stage Preservation.
5. Multi-dimensional Explainable Priority & Qualification Scoring.
6. Task Generation & Follow-up ownership.
7. Opportunity and Task API routes.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.models.classification_model import Classification
from app.models.contact_model import Contact
from app.models.email_model import Email
from app.models.lead_model import Lead
from app.models.mailbox_model import Mailbox
from app.models.organization_model import Organization
from app.models.task_model import Task
from app.services.hybrid_classifier import HybridClassifier
from app.services.priority_service import PriorityScoringService
from app.services.explanation_service import generate_executive_explanation, generate_actionable_tasks


def test_independent_opportunity_separation(test_db):
    """Validate that K Jeevan Kumar's proposal and subsequent Crestview Capital payment remittance

    remain strictly separate opportunities without data contamination or stage corruption.
    """
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    # 1. Ingest Email 1: Commercial proposal and negotiation
    email_1 = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="5001",
        uid_validity=1,
        message_id="<proposal-1048@crestview.com>",
        gmail_thread_id="thread_crestview_001",
        sender="K Jeevan Kumar <kjeevankumar@crestview.com>",
        subject="Commercial Proposal & Scope Review - Cloud Infrastructure",
        body_text="Hi Team, We received your proposal for the cloud infrastructure deployment ($48,000). We are reviewing the terms with our executive board and would like to negotiate a 10% discount.",
        received_at=datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc),
    )
    db.add(email_1)
    db.commit()

    cls_1 = classifier.classify_email(email_1)
    assert cls_1.pipeline_category == "negotiations"
    assert cls_1.relationship in ["new_contact", "existing_lead"]
    assert cls_1.intent == "negotiation"
    assert cls_1.lead_stage == "negotiation"
    assert cls_1.lead_id is not None

    lead_1 = db.query(Lead).filter(Lead.id == cls_1.lead_id).first()
    assert lead_1.status == "negotiation"
    lead_1_id = lead_1.id

    # 2. Ingest Email 2: Separate Payment Remittance Advice for Invoice #INV-2026-1048
    email_2 = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="5002",
        uid_validity=1,
        message_id="<remittance-1048@crestview.com>",
        gmail_thread_id="thread_crestview_remittance_999",  # Independent thread
        sender="K Jeevan Kumar <kjeevankumar@crestview.com>",
        subject="Payment Remittance Advice - Invoice #INV-2026-1048",
        body_text="Please find attached payment remittance advice for Invoice #INV-2026-1048. The wire transfer has been processed via Chase Commercial Banking in the amount of $24,000.",
        received_at=datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc),
    )
    db.add(email_2)
    db.commit()

    cls_2 = classifier.classify_email(email_2)

    # Email 2 is classified into payment remittance pipeline
    assert cls_2.pipeline_category in ["payment_remittance", "invoices"]
    assert cls_2.intent in ["payment_remittance", "invoice"]
    assert cls_2.commercial_intent == "payment_remittance"

    # Remittance advice must NOT corrupt lead 1 stage to WON!
    db.refresh(lead_1)
    assert lead_1.status == "negotiation"

    # Email 2 is a remittance event and must not be attached to negotiation lead 1
    assert email_2.lead_id != lead_1_id


def test_customer_org_industry_vs_requested_solution(test_db):
    """Validate Apex Logistics Global scenario:

    Customer Organization Industry = 'Logistics & Transportation'
    Requested Solution Domain = 'IT & Software'
    """
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="5003",
        uid_validity=1,
        message_id="<marcus-vance-5003@apexlogisticsglobal.com>",
        gmail_thread_id="thread_apex_001",
        sender="Marcus Vance <marcus@apexlogisticsglobal.com>",
        subject="(No Subject)",
        body_text=(
            "Hi Team,\n\n"
            "I came across your services while researching enterprise DevOps automation "
            "and cloud infrastructure partners for our North American supply chain operations.\n\n"
            "We are currently evaluating service providers to migrate our legacy logistics tracking platform "
            "to AWS over the next quarter. Could you please share your standard service deck, case studies "
            "of similar migrations, and availability for a 30-minute discovery call next Tuesday or Wednesday?\n\n"
            "Best regards,\nMarcus Vance\nHead of Infrastructure & Cloud Engineering\nApex Logistics Global"
        ),
        received_at=datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)

    assert cls.is_business_relevant is True
    assert cls.pipeline_category == "new_leads"
    assert cls.intent == "new_enquiry"
    assert cls.lead_stage in ["new", "qualified"]

    # Customer organization industry vs solution domain separation
    assert cls.customer_org_industry == "Logistics & Transportation"
    assert cls.requested_solution_domain == "IT & Software"
    assert cls.sender_industry == "Logistics & Transportation"
    assert cls.target_industry == "IT & Software"

    # Verified synthesized title for (No Subject)
    lead = db.query(Lead).filter(Lead.id == email.lead_id).first()
    assert lead is not None
    assert lead.title != "(No Subject)"
    assert "Logistics" in lead.title or "Apex" in lead.title or "IT & Software" in lead.title


def test_chase_payment_rail_exclusion(test_db):
    """Ensure mentioning Chase Commercial Banking in remittance does NOT falsely classify

    customer industry as 'Banking & Finance'.
    """
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="5004",
        uid_validity=1,
        message_id="<remit-rail-5004@apexlogisticsglobal.com>",
        gmail_thread_id="thread_rail_001",
        sender="Accounts <billing@apexlogisticsglobal.com>",
        subject="Wire Transfer Notification - Chase Commercial Banking",
        body_text="Wire transfer processed from Chase Commercial Banking account for Invoice #9012. Remittance advice attached.",
        received_at=datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)

    assert cls.pipeline_category in ["payment_remittance", "invoices"]
    assert cls.intent in ["payment_remittance", "invoice"]
    assert cls.commercial_intent == "payment_remittance"
    # SENDER IS LOGISTICS, NOT BANKING!
    assert cls.customer_org_industry != "Banking & Finance"


def test_priority_scoring_engine():
    """Validate PriorityScoringService outputs."""
    service = PriorityScoringService()

    # Enterprise discovery call
    res = service.evaluate(
        subject="(No Subject)",
        cleaned_body="Evaluating service providers to migrate our legacy logistics tracking platform to AWS over the next quarter. Availability for a 30-minute discovery call next Tuesday?",
        pipeline_category="new_leads",
        intent="new_enquiry",
        relationship="new_contact",
        is_business_relevant=True,
    )
    assert res.priority_level == "hot"
    assert res.action_urgency == "high"
    assert res.business_potential == "high"
    assert res.qualification_status == "qualified"

    # Non-business security alert
    res_alert = service.evaluate(
        subject="Security alert",
        cleaned_body="App password created for your account",
        is_business_relevant=False,
    )
    assert res_alert.priority_level == "low"
    assert res_alert.action_urgency == "low"
    assert res_alert.qualification_status == "disqualified"


def test_task_generation(test_db):
    """Validate automated task generation on business emails."""
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="5005",
        uid_validity=1,
        message_id="<task-test-5005@apex.com>",
        gmail_thread_id="thread_task_001",
        sender="Marcus <marcus@apexlogisticsglobal.com>",
        subject="Cloud Migration Inquiry",
        body_text="Could you please share your standard service deck, case studies of similar migrations, and availability for a 30-minute discovery call next Tuesday?",
        received_at=datetime(2026, 11, 17, 14, 0, tzinfo=timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)

    # Check tasks created in DB
    tasks = db.query(Task).filter(Task.email_id == email.id).all()
    assert len(tasks) > 0
    task_titles = [t.title for t in tasks]
    assert any("discovery call" in t.lower() or "service deck" in t.lower() for t in task_titles)
    assert all(t.status == "pending" for t in tasks)


def test_lifecycle_preservation_on_followup(test_db):
    """Validate that routine follow-ups preserve the existing lead's qualified/negotiation stage."""
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    # 1. Lead at negotiation
    contact = Contact(
        mailbox_id=mb.id,
        email_address="client@enterprise.com",
        name="Enterprise Client",
        relationship_type="existing_lead",
        current_lead_stage="negotiation",
    )
    db.add(contact)
    db.flush()

    lead = Lead(
        mailbox_id=mb.id,
        contact_id=contact.id,
        title="Enterprise CRM System",
        status="negotiation",
        source="email",
    )
    db.add(lead)
    db.commit()

    # 2. Inbound routine follow-up
    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="5006",
        uid_validity=1,
        message_id="<followup-5006@enterprise.com>",
        gmail_thread_id="thread_crm_001",
        sender="client@enterprise.com",
        subject="Re: Enterprise CRM System - status update",
        body_text="Hi team, following up to see if there is any update on the revised proposal?",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email)
    db.commit()

    cls = classifier.classify_email(email)
    assert cls.pipeline_category == "follow_ups"
    assert cls.intent == "follow_up"
    # Stage must remain negotiation (not reset to unknown or qualified)
    assert cls.lead_stage == "negotiation"


def test_executive_explanation_structured_evidence():
    """Validate executive narrative, sentence-level structured evidence and actionable next tasks."""
    from app.services.explanation_service import extract_structured_evidence, extract_interpreted_key_signals

    text = (
        "We are currently evaluating service providers to migrate our legacy logistics tracking platform to AWS. "
        "Could you please share your standard service deck, case studies, and availability for a 30-minute discovery call next Tuesday?"
    )
    evidence = extract_structured_evidence(
        cleaned_body=text,
        subject="Cloud Migration Inquiry",
        pipeline_category="new_leads",
        intent="new_enquiry",
        sender_industry="Logistics & Transportation",
        target_industry="IT & Software",
    )
    assert len(evidence) >= 2
    categories = [e["category"] for e in evidence]
    assert "Vendor Evaluation" in categories or "Commercial Next Step" in categories

    signals = extract_interpreted_key_signals(
        cleaned_body=text,
        subject="Cloud Migration Inquiry",
        relationship="new_contact",
        intent="new_enquiry",
        pipeline_category="new_leads",
    )
    assert len(signals) >= 2
    assert any("Vendor" in s or "Migration" in s or "Discovery" in s for s in signals)


def test_opportunities_api_endpoints(test_db):
    """Validate opportunity listing and status updates via opportunity routes."""
    from app.config import Settings
    from app.routes.opportunity_routes import list_opportunities, update_opportunity, UpdateOpportunityRequest
    db, mb = test_db
    settings = Settings()

    contact = Contact(
        mailbox_id=mb.id,
        email_address="prospect@logistics.com",
        name="Logistics Prospect",
        relationship_type="new_contact",
        current_lead_stage="new",
    )
    db.add(contact)
    db.flush()

    lead = Lead(
        mailbox_id=mb.id,
        contact_id=contact.id,
        title="Fleet Telematics Migration",
        status="new",
        source="email",
        priority="hot",
        requested_solution_domain="IT & Software",
    )
    db.add(lead)
    db.commit()

    # List opportunities
    leads = list_opportunities(status_filter=None, priority_filter=None, search=None, db=db, settings=settings)
    assert len(leads) >= 1
    target = next(l for l in leads if l.id == lead.id)
    assert target.title == "Fleet Telematics Migration"
    assert target.priority == "hot"

    # Update opportunity
    updated = update_opportunity(
        lead_id=lead.id,
        payload=UpdateOpportunityRequest(status="qualified", estimated_value=65000.0, assigned_to="alex@flowshark.com"),
        db=db,
        settings=settings,
    )
    assert updated.status == "qualified"
    assert updated.estimated_value == 65000.0
    assert updated.assigned_to == "alex@flowshark.com"


def test_tasks_api_endpoints(test_db):
    """Validate task listing, creation, and status toggle via task routes."""
    from app.config import Settings
    from app.routes.task_routes import list_tasks, create_task, update_task, CreateTaskRequest, UpdateTaskRequest
    db, mb = test_db
    settings = Settings()

    # Create task
    task = create_task(
        payload=CreateTaskRequest(
            title="Schedule discovery call with Marcus Vance",
            priority="high",
            description="Confirm availability for Tuesday 30-min call.",
        ),
        db=db,
        settings=settings,
    )
    assert task.status == "pending"
    assert task.priority == "high"

    # List tasks
    all_tasks = list_tasks(status_filter=None, priority_filter=None, lead_id=None, email_id=None, db=db, settings=settings)
    assert any(t.id == task.id for t in all_tasks)

    # Complete task
    completed = update_task(
        task_id=task.id,
        payload=UpdateTaskRequest(status="completed"),
        db=db,
        settings=settings,
    )
    assert completed.status == "completed"
    assert completed.completed_at is not None

