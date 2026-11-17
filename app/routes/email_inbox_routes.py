"""FastAPI routes for database-backed email management and mailbox synchronization.

All queries and operations are strictly scoped to the active mailbox.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    category: Optional[str] = Query(
        None,
        description=(
            "FlowShark dashboard category filter: "
            "'new_leads', 'negotiations', 'follow_ups', 'business_clarifications', "
            "'existing_leads', 'purchase_orders', 'invoices', 'needs_review'"
        ),
    ),
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
    category_val = category if isinstance(category, str) else None
    intent_val = intent if isinstance(intent, str) else None
    relationship_val = relationship if isinstance(relationship, str) else None
    lead_stage_val = lead_stage if isinstance(lead_stage, str) else None
    industry_val = industry if isinstance(industry, str) else None
    sender_ind_val = sender_industry if isinstance(sender_industry, str) else None
    target_ind_val = target_industry if isinstance(target_industry, str) else None

    # Search filter (scoped to active mailbox)
    if search_val and search_val.strip():
        term = f"%{search_val.strip()}%"
        query = query.filter((Email.subject.ilike(term)) | (Email.sender.ilike(term)))

    # Direct filters
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

    # Category aggregate filters
    if category_val:
        cat = category_val.lower().strip()
        if cat == "new_leads":
            query = query.filter(
                Classification.relationship == "new_contact",
                Classification.intent == "new_enquiry",
            )
        elif cat == "negotiations":
            query = query.filter(Classification.intent == "negotiation")
        elif cat == "follow_ups":
            query = query.filter(Classification.intent == "follow_up")
        elif cat == "business_clarifications":
            query = query.filter(Classification.intent == "business_clarification")
        elif cat == "existing_leads":
            query = query.filter(Classification.relationship == "existing_lead")
        elif cat == "purchase_orders":
            query = query.filter(Classification.intent == "purchase_order")
        elif cat == "invoices":
            query = query.filter(Classification.intent == "invoice")
        elif cat == "needs_review":
            query = query.filter(Classification.requires_human_review == True)  # noqa: E712

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
