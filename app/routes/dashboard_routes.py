"""FastAPI route for FlowShark Lead Intelligence Dashboard summary statistics.

All metrics, category counters, and recent activity are strictly scoped to the active mailbox.
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.security import mask_email
from app.db.session import get_db
from app.models.classification_model import Classification, ClassificationHistory
from app.models.email_model import Email
from app.schemas.dashboard_schema import DashboardSummaryResponse, IndustryAnalyticsResponse
from app.services.industry_taxonomy import PRIMARY_INDUSTRIES
from app.services.mailbox_service import MailboxService

logger = logging.getLogger("gmail_fastapi.dashboard")

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="Get High-Level Dashboard Statistics (Active Mailbox Only)",
    description="Returns aggregate counts of synced emails, classified leads, and intent distributions for active mailbox.",
)
@router.get(
    "/stats",
    response_model=DashboardSummaryResponse,
    include_in_schema=False,
)
def get_dashboard_summary(
    business_only: bool = True,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DashboardSummaryResponse:
    if settings is None or not isinstance(settings, Settings):
        settings = get_settings()

    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    if not active_mb:
        return DashboardSummaryResponse(
            active_mailbox_id=None,
            active_mailbox_email=None,
            active_mailbox_masked="No Account",
            total_synced=0,
            total_classified=0,
            new_leads_count=0,
            negotiations_count=0,
            follow_ups_count=0,
            clarifications_count=0,
            existing_leads_count=0,
            purchase_orders_count=0,
            invoices_count=0,
            invoice_billing_count=0,
            invoice_requests_count=0,
            invoice_updates_count=0,
            payments_count=0,
            payment_remittances_count=0,
            payment_followups_count=0,
            payment_disputes_count=0,
            needs_review_count=0,
            human_corrected_count=0,
            is_llm_active=settings.is_llm_configured,
            active_llm_provider=settings.LLM_PROVIDER if settings.is_llm_configured else "fallback (rules + heuristics)",
            recent_activity=[],
        )

    mid = active_mb.id

    # Base queries scoped strictly to active mailbox
    email_q = db.query(Email).filter(Email.mailbox_id == mid)
    class_q = db.query(Classification).filter(Classification.mailbox_id == mid)

    total_synced = email_q.count()
    total_classified = class_q.count()

    # Scoped Category Counts - strictly business relevant for lead pipelines
    biz_class_q = class_q.filter(Classification.is_business_relevant != False)  # noqa: E712
    non_business_count = class_q.filter(Classification.is_business_relevant == False).count()  # noqa: E712

    new_leads_count = biz_class_q.filter(
        (Classification.pipeline_category == "new_leads")
        | (Classification.intent == "new_enquiry")
    ).count()
    negotiations_count = biz_class_q.filter(
        (Classification.pipeline_category == "negotiations")
        | (Classification.intent == "negotiation")
    ).count()
    follow_ups_count = biz_class_q.filter(
        (Classification.pipeline_category == "follow_ups")
        | (Classification.intent == "follow_up")
    ).count()
    clarifications_count = biz_class_q.filter(
        (Classification.pipeline_category == "clarifications")
        | (Classification.intent == "business_clarification")
    ).count()
    existing_leads_count = biz_class_q.filter(
        (Classification.pipeline_category == "existing_leads")
        | (Classification.intent == "existing_lead")
    ).count()
    purchase_orders_count = biz_class_q.filter(
        (Classification.pipeline_category == "purchase_orders")
        | (Classification.intent == "purchase_order")
    ).count()
    # Commercial Subcategory Counts
    invoice_requests_count = biz_class_q.filter(
        (Classification.pipeline_category == "invoice_request")
        | (Classification.intent == "invoice_request")
        | (Classification.commercial_intent == "invoice_request")
    ).count()
    invoice_updates_count = biz_class_q.filter(
        (Classification.pipeline_category == "invoice_update")
        | (Classification.intent == "invoice_update")
        | (Classification.commercial_intent == "invoice_update")
    ).count()
    legacy_invoices_count = biz_class_q.filter(
        (Classification.pipeline_category == "invoices")
        | (Classification.intent == "invoice")
    ).count()
    invoice_billing_count = invoice_requests_count + invoice_updates_count + legacy_invoices_count

    payment_remittances_count = biz_class_q.filter(
        (Classification.pipeline_category == "payment_remittance")
        | (Classification.intent == "payment_remittance")
        | (Classification.commercial_intent == "payment_remittance")
    ).count()
    payment_followups_count = biz_class_q.filter(
        (Classification.pipeline_category == "payment_follow_up")
        | (Classification.intent == "payment_follow_up")
        | (Classification.commercial_intent == "payment_follow_up")
    ).count()
    payment_disputes_count = biz_class_q.filter(
        (Classification.pipeline_category == "payment_dispute")
        | (Classification.intent == "payment_dispute")
        | (Classification.commercial_intent == "payment_dispute")
    ).count()
    payments_count = payment_remittances_count + payment_followups_count + payment_disputes_count

    invoices_count = invoice_billing_count
    needs_review_count = biz_class_q.filter(
        (Classification.pipeline_category == "needs_review")
        | (Classification.intent.in_(["other", "needs_review"]))
        | (Classification.requires_human_review == True)
    ).count()
    human_corrected_count = db.query(ClassificationHistory).filter(ClassificationHistory.mailbox_id == mid).count()

    # Recent 10 emails scoped strictly to active mailbox
    # Filter by business relevance if requested (default: True to prevent system alerts from polluting pipeline preview)
    recent_q = email_q
    if business_only:
        recent_q = recent_q.outerjoin(Email.classification).filter(
            (Classification.is_business_relevant != False)  # noqa: E712
            | (Classification.id.is_(None))
        )

    recent_emails = (
        recent_q.order_by(Email.received_at.desc().nullslast(), Email.id.desc())
        .limit(10)
        .all()
    )

    return DashboardSummaryResponse(
        active_mailbox_id=mid,
        active_mailbox_email=active_mb.email_address,
        active_mailbox_masked=mask_email(active_mb.email_address),
        total_synced=total_synced,
        total_classified=total_classified,
        new_leads_count=new_leads_count,
        negotiations_count=negotiations_count,
        follow_ups_count=follow_ups_count,
        clarifications_count=clarifications_count,
        existing_leads_count=existing_leads_count,
        purchase_orders_count=purchase_orders_count,
        invoices_count=invoices_count,
        invoice_billing_count=invoice_billing_count,
        invoice_requests_count=invoice_requests_count,
        invoice_updates_count=invoice_updates_count,
        payments_count=payments_count,
        payment_remittances_count=payment_remittances_count,
        payment_followups_count=payment_followups_count,
        payment_disputes_count=payment_disputes_count,
        needs_review_count=needs_review_count,
        non_business_count=non_business_count,
        human_corrected_count=human_corrected_count,
        is_llm_active=settings.is_llm_configured,
        active_llm_provider=settings.LLM_PROVIDER if settings.is_llm_configured else "fallback (rules + heuristics)",
        recent_activity=recent_emails,
    )


@router.get(
    "/analytics/industries",
    response_model=IndustryAnalyticsResponse,
    summary="Get Industry Analytics Scoped to Active Mailbox (Section 8D & 9)",
)
def get_industry_analytics(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IndustryAnalyticsResponse:
    """Return aggregated industry metrics scoped strictly to active mailbox."""
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    if not active_mb:
        return IndustryAnalyticsResponse(
            active_mailbox_id=None,
            total_classified=0,
            total_by_industry={},
            new_enquiries_by_industry={},
            existing_leads_by_industry={},
            follow_ups_by_industry={},
            lead_stages_by_industry={},
            industry_distribution=[],
            target_industry_distribution=[],
        )

    mid = active_mb.id
    class_q = db.query(Classification).filter(Classification.mailbox_id == mid)
    total_classified = class_q.count()

    all_records = class_q.all()

    total_by_ind: dict[str, int] = {}
    new_enq_by_ind: dict[str, int] = {}
    existing_leads_by_ind: dict[str, int] = {}
    follow_ups_by_ind: dict[str, int] = {}
    lead_stages_by_ind: dict[str, dict[str, int]] = {}
    target_by_ind: dict[str, int] = {}

    for rec in all_records:
        s_ind = rec.sender_industry or "Unknown"
        t_ind = rec.target_industry or "Unknown"
        intent = rec.intent or "other"
        stage = rec.lead_stage or "unknown"
        rel = rec.relationship or "unknown"

        # Tally primary (target domain)
        total_by_ind[t_ind] = total_by_ind.get(t_ind, 0) + 1
        target_by_ind[t_ind] = target_by_ind.get(t_ind, 0) + 1

        if intent == "new_enquiry":
            new_enq_by_ind[t_ind] = new_enq_by_ind.get(t_ind, 0) + 1
        if rel == "existing_lead":
            existing_leads_by_ind[t_ind] = existing_leads_by_ind.get(t_ind, 0) + 1
        if intent == "follow_up":
            follow_ups_by_ind[t_ind] = follow_ups_by_ind.get(t_ind, 0) + 1

        if t_ind not in lead_stages_by_ind:
            lead_stages_by_ind[t_ind] = {}
        lead_stages_by_ind[t_ind][stage] = lead_stages_by_ind[t_ind].get(stage, 0) + 1

    # Distribution percentages
    ind_distribution = []
    for ind, count in sorted(total_by_ind.items(), key=lambda x: x[1], reverse=True):
        pct = round((count / total_classified) * 100, 1) if total_classified > 0 else 0.0
        ind_distribution.append({
            "industry": ind,
            "count": count,
            "percentage": pct,
        })

    target_distribution = []
    for ind, count in sorted(target_by_ind.items(), key=lambda x: x[1], reverse=True):
        pct = round((count / total_classified) * 100, 1) if total_classified > 0 else 0.0
        target_distribution.append({
            "target_industry": ind,
            "count": count,
            "percentage": pct,
        })

    return IndustryAnalyticsResponse(
        active_mailbox_id=mid,
        total_classified=total_classified,
        total_by_industry=total_by_ind,
        new_enquiries_by_industry=new_enq_by_ind,
        existing_leads_by_industry=existing_leads_by_ind,
        follow_ups_by_industry=follow_ups_by_ind,
        lead_stages_by_industry=lead_stages_by_ind,
        industry_distribution=ind_distribution,
        target_industry_distribution=target_distribution,
    )
