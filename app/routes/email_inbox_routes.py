"""FastAPI routes for database-backed email management and mailbox synchronization.

All queries and operations are strictly scoped to the active mailbox.
"""

import logging
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import false as sql_false
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.models.classification_model import Classification
from app.models.email_model import Email
from app.models.sync_model import SyncState
from app.schemas.dashboard_schema import (
    EmailRead,
    PaginatedEmailsResponse,
    SyncRequest,
    SyncStatusResponse,
)
from app.services.mailbox_service import MailboxService
from app.services.sync_service import EmailSyncService, SyncResult

logger = logging.getLogger("gmail_fastapi.inbox_routes")

router = APIRouter(prefix="/api/emails", tags=["Inbox Management"])


def _get_sync_status_data(db: Session, settings: Settings) -> SyncStatusResponse:
    """Internal helper to construct SyncStatusResponse scoped to active mailbox."""
    from app.services.background_sync import get_sync_worker
    worker = get_sync_worker(settings=settings)
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    if active_mb:
        account_email = active_mb.email_address
        active_id = active_mb.id
        state = db.query(SyncState).filter(SyncState.mailbox_id == active_id).first()
        total_in_db = db.query(Email).filter(Email.mailbox_id == active_id).count()
        conn_configured = True
    else:
        account_email = settings.GMAIL_ADDRESS or "unknown"
        active_id = None
        state = db.query(SyncState).filter(SyncState.account_email == account_email).first()
        total_in_db = db.query(Email).filter(Email.account_email == account_email).count()
        conn_configured = settings.is_configured

    if not conn_configured:
        conn_status = "unconfigured"
    elif worker._consecutive_errors > 0 or (state and state.status == "failed"):
        conn_status = "error"
    else:
        conn_status = "connected"

    w_status = worker.worker_status

    if not state:
        return SyncStatusResponse(
            active_mailbox_id=active_id,
            account_email=account_email,
            connection_status=conn_status,
            worker_status=w_status,
            status="idle",
            last_successful_sync=None,
            last_synced_at=None,
            last_processed_uid=None,
            highest_synced_uid=None,
            uid_validity=1,
            total_emails_stored=total_in_db,
            total_synced_in_db=total_in_db,
            inbox_total=0,
            new_emails_last_sync=0,
            new_emails_retrieved_latest_sync=0,
            latest_sync_error=None,
            error_message=None,
            sync_interval_seconds=settings.SYNC_INTERVAL_SECONDS,
            is_worker_running=worker.is_running,
        )

    return SyncStatusResponse(
        active_mailbox_id=active_id,
        account_email=state.account_email,
        connection_status=conn_status,
        worker_status=w_status,
        status=state.status,
        last_successful_sync=state.last_synced_at,
        last_synced_at=state.last_synced_at,
        last_processed_uid=state.highest_synced_uid or state.last_synced_uid,
        highest_synced_uid=state.highest_synced_uid,
        uid_validity=state.uid_validity,
        total_emails_stored=total_in_db,
        total_synced_in_db=total_in_db,
        inbox_total=state.inbox_total,
        new_emails_last_sync=state.new_emails_last_sync,
        new_emails_retrieved_latest_sync=state.new_emails_last_sync,
        latest_sync_error=state.error_message,
        error_message=state.error_message,
        sync_interval_seconds=settings.SYNC_INTERVAL_SECONDS,
        is_worker_running=worker.is_running,
    )


def normalize_pipeline_category(val: Optional[str]) -> Optional[Tuple[str, List[str], Optional[bool]]]:
    """
    Normalizes a pipeline filter parameter into a canonical category and the exact
    list of pipeline_category values to match in the database.

    Returns:
        (canonical_name, [matching_db_categories], is_business_relevant)
        or ("UNRECOGNIZED", [], None) if an unknown filter string was passed.
    """
    if not val or not isinstance(val, str) or not val.strip():
        return None
    raw = val.lower().strip().replace(" ", "_").replace("-", "_")

    if raw in ("new_leads", "new_lead", "new_enquiry"):
        return ("new_leads", ["new_leads"], True)
    if raw in ("existing_leads", "existing_lead"):
        return ("existing_leads", ["existing_leads"], True)
    if raw in ("negotiations", "negotiation"):
        return ("negotiations", ["negotiations"], True)
    if raw in ("follow_ups", "follow_up", "followup", "followups"):
        return ("follow_ups", ["follow_ups"], True)
    if raw in ("clarifications", "clarification", "business_clarifications", "business_clarification"):
        return ("clarifications", ["clarifications"], True)
    if raw in ("purchase_orders", "purchase_order", "po"):
        return ("purchase_orders", ["purchase_orders"], True)
    if raw in ("invoice_request", "invoice_requests"):
        return ("invoice_request", ["invoice_request"], True)
    if raw in ("invoice_update", "invoice_updates"):
        return ("invoice_update", ["invoice_update"], True)
    if raw in ("payment_remittance", "payment_remittances", "remittance", "remittances", "remittance_advice"):
        return ("payment_remittance", ["payment_remittance"], True)
    if raw in ("payment_follow_up", "payment_follow_ups", "payment_followup", "payment_followups"):
        return ("payment_follow_up", ["payment_follow_up"], True)
    if raw in ("payment_dispute", "payment_disputes", "dispute", "disputes"):
        return ("payment_dispute", ["payment_dispute"], True)
    if raw in ("needs_review", "review"):
        return ("needs_review", ["needs_review"], True)
    if raw in ("system_notifications", "system_notification", "non_business", "automated_notifications", "automated_notification"):
        return ("system_notifications", [], False)
    # Composite commercial parent views
    if raw in ("invoice_billing", "invoices", "invoice"):
        return ("invoice_billing", ["invoice_request", "invoice_update", "invoices"], True)
    if raw in ("payments", "payment"):
        return ("payments", ["payment_remittance", "payment_follow_up", "payment_dispute", "payments"], True)

    return ("UNRECOGNIZED", [], None)


@router.get(
    "",
    response_model=PaginatedEmailsResponse,
    summary="List Synchronized Emails with Filters (Active Mailbox Only)",
    description="Retrieve paginated synchronized emails strictly scoped to the active mailbox.",
)
def list_emails(
    page: int = Query(default=1, ge=1, description="Page number (starts at 1)"),
    size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term matching subject or sender"),
    pipeline: Optional[str] = Query(None, description="Direct filter on pipeline category (e.g. purchase_order, invoice_request)"),
    category: Optional[str] = Query(
        None,
        description=(
            "FlowShark dashboard category filter: "
            "'new_leads', 'negotiations', 'follow_ups', 'business_clarifications', "
            "'existing_leads', 'purchase_orders', 'invoices', 'needs_review', 'system_notifications', 'non_business'"
        ),
    ),
    is_business_relevant: Optional[bool] = Query(None, description="Direct filter on business relevance"),
    pipeline_category: Optional[str] = Query(None, description="Direct filter on pipeline category"),
    relevance_category: Optional[str] = Query(None, description="Direct filter on relevance category"),
    intent: Optional[str] = Query(None, description="Direct filter on classification intent"),
    relationship: Optional[str] = Query(None, description="Direct filter on relationship"),
    lead_stage: Optional[str] = Query(None, description="Direct filter on lead stage"),
    industry: Optional[str] = Query(None, description="Filter matching sender or target industry"),
    sender_industry: Optional[str] = Query(None, description="Direct filter on sender industry"),
    target_industry: Optional[str] = Query(None, description="Direct filter on target industry"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PaginatedEmailsResponse:
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    if not active_mb and not settings.is_configured:
        return PaginatedEmailsResponse(items=[], total=0, page=1, size=size, pages=1)

    query = db.query(Email).outerjoin(Email.classification)

    # Strictly scope to active mailbox
    if active_mb:
        query = query.filter(Email.mailbox_id == active_mb.id)
    else:
        query = query.filter(Email.account_email == settings.GMAIL_ADDRESS)

    search_val = search if isinstance(search, str) else None
    intent_val = intent if isinstance(intent, str) else None
    relationship_val = relationship if isinstance(relationship, str) else None
    lead_stage_val = lead_stage if isinstance(lead_stage, str) else None
    industry_val = industry if isinstance(industry, str) else None
    sender_ind_val = sender_industry if isinstance(sender_industry, str) else None
    target_ind_val = target_industry if isinstance(target_industry, str) else None
    rel_cat_val = relevance_category if isinstance(relevance_category, str) else None

    # Search filter (scoped to active mailbox)
    if search_val and search_val.strip():
        term = f"%{search_val.strip()}%"
        query = query.filter((Email.subject.ilike(term)) | (Email.sender.ilike(term)))

    # Direct relevance filters
    biz_rel_val = is_business_relevant if isinstance(is_business_relevant, bool) else None
    if biz_rel_val is not None:
        query = query.filter(Classification.is_business_relevant == biz_rel_val)
    if rel_cat_val:
        query = query.filter(Classification.relevance_category == rel_cat_val)

    # Direct classification property filters
    if intent_val:
        query = query.filter(Classification.intent == intent_val)
    if relationship_val:
        query = query.filter(Classification.relationship == relationship_val)
    if lead_stage_val:
        query = query.filter(Classification.lead_stage == lead_stage_val)

    # Industry filters
    if industry_val and industry_val.strip():
        ind_term = industry_val.strip()
        query = query.filter(
            (Classification.target_industry.ilike(ind_term)) | (Classification.sender_industry.ilike(ind_term))
        )
    if sender_ind_val and sender_ind_val.strip():
        query = query.filter(Classification.sender_industry.ilike(sender_ind_val.strip()))
    if target_ind_val and target_ind_val.strip():
        query = query.filter(Classification.target_industry.ilike(target_ind_val.strip()))

    # Authoritative Primary Pipeline Filter (Phase 2 & Phase 3)
    # Consolidate 'pipeline', 'category', and 'pipeline_category' query parameters
    pipe_val = pipeline if isinstance(pipeline, str) else None
    pipe_cat_val = pipeline_category if isinstance(pipeline_category, str) else None
    cat_val = category if isinstance(category, str) else None
    effective_pipeline = pipe_val or pipe_cat_val or cat_val
    pipe_norm = normalize_pipeline_category(effective_pipeline)

    if pipe_norm is not None:
        canonical, db_categories, is_biz = pipe_norm
        if canonical == "UNRECOGNIZED":
            # CRITICAL REQUIREMENT: Never return all emails when an invalid or unrecognized filter is provided!
            query = query.filter(sql_false())
        elif canonical == "system_notifications" or is_biz is False:
            query = query.filter(Classification.is_business_relevant == False)  # noqa: E712
        else:
            # Strict Authoritative Pipeline Isolation:
            # An email appears in a pipeline ONLY when its authoritative Classification.pipeline_category matches.
            # If an unmigrated legacy record has pipeline_category as None, fall back to matching its primary intent.
            cat_filter = Classification.pipeline_category.in_(db_categories)
            if canonical == "new_leads":
                cat_filter = cat_filter | (Classification.pipeline_category.is_(None) & (Classification.intent == "new_enquiry"))
            elif canonical == "negotiations":
                cat_filter = cat_filter | (Classification.pipeline_category.is_(None) & (Classification.intent == "negotiation"))
            elif canonical == "follow_ups":
                cat_filter = cat_filter | (Classification.pipeline_category.is_(None) & (Classification.intent == "follow_up"))
            elif canonical == "clarifications":
                cat_filter = cat_filter | (Classification.pipeline_category.is_(None) & (Classification.intent == "business_clarification"))
            elif canonical == "existing_leads":
                cat_filter = cat_filter | (Classification.pipeline_category.is_(None) & (Classification.intent == "existing_lead"))
            elif canonical == "purchase_orders":
                cat_filter = cat_filter | (Classification.pipeline_category.is_(None) & (Classification.intent == "purchase_order"))

            query = query.filter(
                Classification.is_business_relevant != False,  # noqa: E712
                cat_filter,
            )

    page_num = page if isinstance(page, int) else 1
    size_num = size if isinstance(size, int) else 20
    total = query.count()
    offset = (page_num - 1) * size_num
    emails = query.order_by(Email.received_at.desc().nullslast(), Email.id.desc()).offset(offset).limit(size_num).all()
    pages = (total + size_num - 1) // size_num if total > 0 else 1

    return PaginatedEmailsResponse(
        active_mailbox_id=active_mb.id if active_mb else None,
        items=emails,
        total=total,
        page=page_num,
        size=size_num,
        pages=pages,
    )


@router.get(
    "/sync-status",
    response_model=SyncStatusResponse,
    summary="Get Mailbox Synchronization Status (Active Mailbox Only)",
)
def get_sync_status(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SyncStatusResponse:
    return _get_sync_status_data(db=db, settings=settings)


@router.post(
    "/sync",
    summary="Trigger Incremental Mailbox Synchronization for Active Mailbox",
    description="Synchronize a batch of recent emails from Gmail INBOX into the database without altering read status.",
)
async def trigger_sync(
    request: SyncRequest = SyncRequest(batch_size=50),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    if not active_mb and not settings.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active Gmail account is configured. Please connect a mailbox in Connection Settings.",
        )

    from app.services.background_sync import get_sync_worker
    worker = get_sync_worker(settings=settings)
    try:
        result: SyncResult = await worker.sync_now(batch_size=request.batch_size)
        return {
            "success": True,
            "new_emails_synced": result.new_emails_synced,
            "total_inbox_messages": result.total_inbox_messages,
            "total_synced_in_db": result.total_synced_in_db,
            "uid_validity": result.uid_validity,
            "duration_seconds": result.duration_seconds,
            "message": result.message,
        }
    except Exception as err:
        logger.error("Sync endpoint failed: %s", str(err))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Mailbox synchronization failed: {str(err)}",
        )


@router.get(
    "/threads/{thread_id}",
    response_model=List[EmailRead],
    summary="Get Conversation Thread Emails (Active Mailbox Only)",
    description="Retrieve all emails associated with a specific Gmail thread ID sorted chronologically in active mailbox.",
)
def get_thread_emails(
    thread_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> List[EmailRead]:
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    query = db.query(Email).filter(Email.gmail_thread_id == thread_id)
    if active_mb:
        query = query.filter(Email.mailbox_id == active_mb.id)
    elif settings.is_configured:
        query = query.filter(Email.account_email == settings.GMAIL_ADDRESS)

    emails = query.order_by(Email.received_at.asc(), Email.id.asc()).all()
    if not emails:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No emails found for thread ID '{thread_id}' in active mailbox.",
        )
    return emails


@router.get(
    "/{email_id}",
    response_model=EmailRead,
    summary="Get Email Detail by Database ID (Active Mailbox Only)",
)
def get_email_detail(
    email_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> EmailRead:
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    query = db.query(Email).filter(Email.id == email_id)
    if active_mb:
        query = query.filter(Email.mailbox_id == active_mb.id)
    elif settings.is_configured:
        query = query.filter(Email.account_email == settings.GMAIL_ADDRESS)

    email_record = query.first()
    if not email_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email with ID {email_id} not found in active mailbox.",
        )
    return email_record


@router.delete(
    "/{email_id}",
    summary="Delete an Email from FlowShark (Active Mailbox Only)",
    description="Deletes a specific email and its associated classification and history records from FlowShark's database without affecting the remote Gmail inbox.",
)
def delete_email(
    email_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    from app.models.classification_model import ClassificationHistory
    from app.models.lead_model import LeadActivityHistory
    from app.models.task_model import Task
    from app.models.task_model import Task

    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    query = db.query(Email).filter(Email.id == email_id)
    if active_mb:
        query = query.filter(Email.mailbox_id == active_mb.id)
    elif settings.is_configured:
        query = query.filter(Email.account_email == settings.GMAIL_ADDRESS)

    email_record = query.first()
    if not email_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email with ID {email_id} not found in active mailbox.",
        )

    # Clean up associated records
    from app.models.commercial_event_model import CommercialEvent
    db.query(CommercialEvent).filter(CommercialEvent.email_id == email_id).delete(synchronize_session=False)
    db.query(Task).filter(Task.email_id == email_id).delete(synchronize_session=False)
    db.query(ClassificationHistory).filter(ClassificationHistory.email_id == email_id).delete(synchronize_session=False)
    db.query(LeadActivityHistory).filter(LeadActivityHistory.email_id == email_id).delete(synchronize_session=False)
    db.query(Classification).filter(Classification.email_id == email_id).delete(synchronize_session=False)
    db.delete(email_record)
    db.commit()

    return {
        "success": True,
        "deleted_id": email_id,
        "message": f"Email {email_id} deleted successfully from FlowShark database.",
    }


@router.post(
    "/cleanup-non-business",
    summary="Purge / Clean Up Non-Business Notification Emails (Active Mailbox Only)",
    description="Removes all automated system notifications, security alerts, and newsletters from the active mailbox in FlowShark's database.",
)
def cleanup_non_business(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    from app.models.classification_model import ClassificationHistory
    from app.models.lead_model import LeadActivityHistory
    from app.models.task_model import Task

    # Find ALL non-business / security alert / system notification emails in the DB
    query = (
        db.query(Email.id)
        .outerjoin(Email.classification)
        .filter(
            (Classification.is_business_relevant == False)  # noqa: E712
            | (Classification.relevance_category.in_([
                "account_security_notification",
                "system_notification",
                "automated_notification",
                "newsletter_marketing",
                "spam_irrelevant",
            ]))
            | (Email.sender.ilike("%no-reply@accounts.google.com%"))
            | (Email.sender.ilike("%accounts.google.com%"))
            | (Email.sender.ilike("%google-noreply@google.com%"))
            | (Email.sender.ilike("%mailer-daemon@%"))
            | (Email.subject.ilike("%security alert%"))
            | (Email.subject.ilike("%2-step verification%"))
            | (Email.subject.ilike("%finish setting up your windows%"))
            | (Email.subject.ilike("%setting up your%"))
            | (Email.subject.ilike("%app password%"))
            | (Email.subject.ilike("%selfie video%"))
            | (Email.subject.ilike("%delivery status notification%"))
        )
    )

    target_email_ids = [row[0] for row in query.all()]
    if not target_email_ids:
        return {
            "success": True,
            "deleted_count": 0,
            "message": "No non-business emails found to purge.",
        }

    # Delete relational children
    from app.models.commercial_event_model import CommercialEvent
    db.query(CommercialEvent).filter(CommercialEvent.email_id.in_(target_email_ids)).delete(synchronize_session=False)
    db.query(Task).filter(Task.email_id.in_(target_email_ids)).delete(synchronize_session=False)
    db.query(ClassificationHistory).filter(ClassificationHistory.email_id.in_(target_email_ids)).delete(synchronize_session=False)
    db.query(LeadActivityHistory).filter(LeadActivityHistory.email_id.in_(target_email_ids)).delete(synchronize_session=False)
    db.query(Classification).filter(Classification.email_id.in_(target_email_ids)).delete(synchronize_session=False)
    deleted_cnt = db.query(Email).filter(Email.id.in_(target_email_ids)).delete(synchronize_session=False)
    db.commit()

    return {
        "success": True,
        "deleted_count": deleted_cnt,
        "message": f"Successfully removed {deleted_cnt} non-business notification emails from FlowShark.",
    }
