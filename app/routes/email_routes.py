"""FastAPI route handlers for Gmail integration endpoints.

Supports complete global mailbox switching, active mailbox scoping, and credential encryption.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.security import mask_email
from app.db.session import get_db
from app.models.email_model import Email
from app.models.mailbox_model import Mailbox
from app.schemas.dashboard_schema import (
    ConnectionDetailsResponse,
    MailboxRead,
    SwitchMailboxRequest,
    SyncStatusResponse,
    UpdateConnectionRequest,
)
from app.schemas.email_schema import (
    ConfigStatusResponse,
    ConnectionTestResponse,
    EmailDetail,
    ErrorResponse,
    HealthResponse,
    InboxResponse,
    SendEmailRequest,
    SendEmailResponse,
    SendTestEmailRequest,
)
from app.services.background_sync import get_sync_worker
from app.services.imap_service import (
    IMAPAuthenticationError,
    IMAPConfigurationError,
    IMAPConnectionError,
    IMAPMessageNotFoundError,
    IMAPService,
)
from app.services.mailbox_service import MailboxService
from app.services.smtp_service import (
    SMTPAuthenticationError,
    SMTPConfigurationError,
    SMTPConnectionError,
    SMTPSendError,
    SMTPService,
)

logger = logging.getLogger("gmail_fastapi.routes")

router = APIRouter(tags=["Email Integration"])


def _resolve_db(db: Optional[Session]) -> Optional[Session]:
    """Safely resolve Session instance if invoked directly without FastAPI DI."""
    if db is None or not hasattr(db, "query"):
        return None
    return db


def _resolve_settings(settings: Optional[Settings]) -> Settings:
    """Safely resolve Settings instance if invoked directly without FastAPI DI."""
    if settings is None or not isinstance(settings, Settings):
        return get_settings()
    return settings


def _get_active_service_settings(db: Optional[Session], settings: Settings) -> Tuple[Settings, Optional[Mailbox]]:
    """Resolve scoped Settings using the currently active Mailbox in the database."""
    resolved_db = _resolve_db(db)
    if resolved_db is not None:
        try:
            mailbox_service = MailboxService(db=resolved_db, settings=settings)
            active_mb = mailbox_service.get_active_mailbox()
            if active_mb:
                addr, pwd = mailbox_service.get_mailbox_credentials(active_mb)
                scoped = settings.model_copy(
                    update={
                        "GMAIL_ADDRESS": addr,
                        "GMAIL_APP_PASSWORD": SecretStr(pwd) if pwd else None,
                        "IMAP_HOST": active_mb.imap_host,
                        "IMAP_PORT": active_mb.imap_port,
                        "SMTP_HOST": active_mb.smtp_host,
                        "SMTP_PORT": active_mb.smtp_port,
                    }
                )
                return scoped, active_mb
        except Exception:
            pass
    return settings, None


# ==========================================
# Health Endpoint
# ==========================================

@router.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Application Health Check",
    description="Check whether the FastAPI server is running and healthy.",
    responses={200: {"model": HealthResponse}},
)
@router.get(
    "/api/email/health",
    response_model=HealthResponse,
    include_in_schema=False,
)
def get_health() -> HealthResponse:
    """Return runtime health status and UTC timestamp."""
    return HealthResponse(
        status="healthy",
        service="gmail-fastapi-integration",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ==========================================
# Connection & Mailbox Switching Endpoints
# ==========================================

@router.get(
    "/api/email/connection",
    response_model=ConnectionDetailsResponse,
    summary="Get Active Gmail Connection & Available Mailboxes",
    description="Returns active mailbox credentials (masked), connection health, and all configured mailboxes.",
)
def get_connection_details(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectionDetailsResponse:
    settings = _resolve_settings(settings)
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()
    all_mailboxes = mailbox_service.list_mailboxes()

    available_reads = []
    for mb in all_mailboxes:
        count = db.query(Email).filter(Email.mailbox_id == mb.id).count()
        available_reads.append(
            MailboxRead(
                id=mb.id,
                email_address=mb.email_address,
                email_address_masked=mask_email(mb.email_address),
                is_active=mb.is_active,
                imap_host=mb.imap_host,
                imap_port=mb.imap_port,
                smtp_host=mb.smtp_host,
                smtp_port=mb.smtp_port,
                total_emails_stored=count,
                created_at=mb.created_at,
                updated_at=mb.updated_at,
            )
        )

    if not active_mb:
        return ConnectionDetailsResponse(
            active_mailbox_id=None,
            email_address=None,
            email_address_masked="Not connected",
            is_connected=False,
            total_emails_stored=0,
            available_mailboxes=available_reads,
            message="No Gmail account connected.",
        )

    active_count = db.query(Email).filter(Email.mailbox_id == active_mb.id).count()
    return ConnectionDetailsResponse(
        active_mailbox_id=active_mb.id,
        email_address=active_mb.email_address,
        email_address_masked=mask_email(active_mb.email_address),
        is_connected=True,
        imap_host=active_mb.imap_host,
        imap_port=active_mb.imap_port,
        smtp_host=active_mb.smtp_host,
        smtp_port=active_mb.smtp_port,
        total_emails_stored=active_count,
        available_mailboxes=available_reads,
        message="Active Gmail connection operational.",
    )


@router.put(
    "/api/email/connection",
    response_model=ConnectionDetailsResponse,
    summary="Connect, Validate, and Switch Active Gmail Account",
    description="Validates new Gmail credentials with IMAP, stops previous sync worker, persists with encryption, sets as active mailbox, and starts new sync worker.",
)
async def update_connection(
    request: UpdateConnectionRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectionDetailsResponse:
    settings = _resolve_settings(settings)
    mailbox_service = MailboxService(db=db, settings=settings)

    # 1. Validate credentials against Gmail IMAP
    try:
        mailbox_service.validate_gmail_credentials(
            email_address=request.email_address,
            app_password=request.app_password,
            imap_host=request.imap_host or "imap.gmail.com",
            imap_port=request.imap_port or 993,
        )
    except (IMAPConfigurationError, IMAPAuthenticationError, IMAPConnectionError) as err:
        logger.warning("Mailbox connection validation failed for %s: %s", request.email_address, str(err))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gmail authentication failed: {str(err)}. Current active connection was preserved.",
        )

    # 2. Stop current background worker safely
    worker = get_sync_worker(settings=settings)
    await worker.stop(db=db)

    # 3. Connect, encrypt, and activate new mailbox
    new_mb, _ = mailbox_service.connect_and_activate_mailbox(
        email_address=request.email_address,
        app_password=request.app_password,
        imap_host=request.imap_host or "imap.gmail.com",
        imap_port=request.imap_port or 993,
        smtp_host=request.smtp_host or "smtp.gmail.com",
        smtp_port=request.smtp_port or 587,
        validate=False,  # Already validated
    )

    # 4. Restart worker for new mailbox
    if settings.BACKGROUND_SYNC_ENABLED:
        await worker.start()
        # Trigger initial sync batch
        try:
            asyncio.create_task(worker.sync_now(batch_size=50))
        except Exception:
            pass

    return get_connection_details(db=db, settings=settings)


@router.post(
    "/api/email/connection/switch",
    response_model=ConnectionDetailsResponse,
    summary="Switch Active Mailbox to Existing Configured Account",
)
async def switch_mailbox(
    request: SwitchMailboxRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectionDetailsResponse:
    settings = _resolve_settings(settings)
    mailbox_service = MailboxService(db=db, settings=settings)

    target_mb = None
    if request.mailbox_id:
        target_mb = mailbox_service.get_mailbox_by_id(request.mailbox_id)
    elif request.email_address:
        target_mb = mailbox_service.get_mailbox_by_email(request.email_address)

    if not target_mb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specified mailbox account was not found.",
        )

    # Stop current worker safely
    worker = get_sync_worker(settings=settings)
    await worker.stop(db=db)

    # Switch active mailbox
    mailbox_service.switch_active_mailbox(target_mb.id)

    # Restart worker for newly activated mailbox
    if settings.BACKGROUND_SYNC_ENABLED:
        await worker.start()

    return get_connection_details(db=db, settings=settings)


@router.delete(
    "/api/email/connection/{mailbox_id}",
    response_model=ConnectionDetailsResponse,
    summary="Safely Disconnect and Delete a Connected Mailbox",
    description="Permanently removes a mailbox, stops its background sync, deletes its scoped emails, classifications, and cursors safely.",
)
async def delete_mailbox(
    mailbox_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectionDetailsResponse:
    settings = _resolve_settings(settings)
    mailbox_service = MailboxService(db=db, settings=settings)

    target = mailbox_service.get_mailbox_by_id(mailbox_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mailbox with ID {mailbox_id} not found.",
        )

    # If deleting active mailbox, stop worker first
    if target.is_active:
        worker = get_sync_worker(settings=settings)
        await worker.stop(db=db)

    # Perform scoped removal
    mailbox_service.remove_mailbox(mailbox_id)

    # Restart worker for newly active mailbox if any
    active_mb = mailbox_service.get_active_mailbox()
    if active_mb and settings.BACKGROUND_SYNC_ENABLED:
        worker = get_sync_worker(settings=settings)
        await worker.start()

    return get_connection_details(db=db, settings=settings)


# ==========================================
# Configuration & Sync Status Endpoints
# ==========================================

@router.get(
    "/api/email/sync-status",
    response_model=SyncStatusResponse,
    summary="Get Gmail Synchronization & Worker Status (Active Mailbox Only)",
)
def get_email_sync_status(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SyncStatusResponse:
    from app.routes.email_inbox_routes import _get_sync_status_data
    settings = _resolve_settings(settings)
    return _get_sync_status_data(db=db, settings=settings)


@router.get(
    "/api/email/config-status",
    response_model=ConfigStatusResponse,
    summary="Check Gmail Configuration Status",
    description="Inspects active mailbox presence without leaking credentials.",
)
def get_config_status(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConfigStatusResponse:
    settings = _resolve_settings(settings)
    scoped_settings, active_mb = _get_active_service_settings(db, settings)
    is_conf = bool(active_mb or scoped_settings.is_configured)
    active_email = active_mb.email_address if active_mb else scoped_settings.GMAIL_ADDRESS

    msg = (
        f"Gmail account {mask_email(active_email)} is active and ready for operations."
        if is_conf
        else "Gmail credentials are not configured or missing."
    )

    return ConfigStatusResponse(
        configured=is_conf,
        gmail_address_configured=bool(active_email and active_email.strip()),
        gmail_address_masked=mask_email(active_email) if (active_email and active_email.strip()) else None,
        app_password_configured=bool(active_mb or (scoped_settings.GMAIL_APP_PASSWORD and scoped_settings.GMAIL_APP_PASSWORD.get_secret_value())),
        imap_host=active_mb.imap_host if active_mb else scoped_settings.IMAP_HOST,
        imap_port=active_mb.imap_port if active_mb else scoped_settings.IMAP_PORT,
        smtp_host=active_mb.smtp_host if active_mb else scoped_settings.SMTP_HOST,
        smtp_port=active_mb.smtp_port if active_mb else scoped_settings.SMTP_PORT,
        message=msg,
    )


# ==========================================
# Connection Test Endpoints (Scoped to Active Mailbox)
# ==========================================

@router.get(
    "/api/email/test-imap",
    response_model=ConnectionTestResponse,
    summary="Test Active Mailbox IMAP Authentication & Inbox Access",
)
def test_imap(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectionTestResponse:
    settings = _resolve_settings(settings)
    scoped_settings, active_mb = _get_active_service_settings(db, settings)

    if not scoped_settings.is_configured and not active_mb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail credentials are not configured.",
        )

    service = IMAPService(settings=scoped_settings)
    try:
        res = service.test_connection()
        if isinstance(res, dict):
            res_dict = dict(res)
            res_dict.setdefault("service", "IMAP")
            return ConnectionTestResponse(**res_dict)
        return res
    except IMAPConfigurationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except IMAPAuthenticationError as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(err))
    except IMAPConnectionError as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err))


@router.get(
    "/api/email/test-smtp",
    response_model=ConnectionTestResponse,
    summary="Test Active Mailbox SMTP STARTTLS Authentication",
)
def test_smtp(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectionTestResponse:
    settings = _resolve_settings(settings)
    scoped_settings, active_mb = _get_active_service_settings(db, settings)

    if not scoped_settings.is_configured and not active_mb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail credentials are not configured.",
        )

    service = SMTPService(settings=scoped_settings)
    try:
        res = service.test_connection()
        if isinstance(res, dict):
            res_dict = dict(res)
            res_dict.setdefault("service", "SMTP")
            return ConnectionTestResponse(**res_dict)
        return res
    except SMTPConfigurationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except SMTPAuthenticationError as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(err))
    except SMTPConnectionError as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err))


# ==========================================
# Aliased Endpoints Scoped to Active Mailbox
# ==========================================

@router.get(
    "/api/email/inbox",
    summary="Get Active Mailbox Emails",
    description="Alias for /api/emails strictly scoped to active mailbox.",
)
def get_email_inbox_alias(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    from app.routes.email_inbox_routes import list_emails
    return list_emails(page=page, size=size, search=search, category=category, db=db, settings=settings)


@router.get(
    "/api/email/inbox-imap",
    response_model=InboxResponse,
    summary="Fetch IMAP Inbox Messages Directly",
    include_in_schema=False,
)
def get_inbox_emails(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    mailbox: str = Query(default="INBOX"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InboxResponse:
    settings = _resolve_settings(settings)
    scoped_settings, active_mb = _get_active_service_settings(db, settings)

    if not scoped_settings.is_configured and not active_mb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail credentials are not configured.",
        )

    service = IMAPService(settings=scoped_settings)
    try:
        emails, total, uid_val = service.fetch_inbox_emails(mailbox=mailbox, limit=limit, offset=offset)
        return InboxResponse(
            total=total,
            count=len(emails),
            offset=offset,
            limit=limit,
            uid_validity=uid_val,
            emails=emails,
        )
    except IMAPConfigurationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except IMAPAuthenticationError as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(err))
    except IMAPConnectionError as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err))


@router.get(
    "/api/classifications",
    summary="Get Active Mailbox Classifications",
)
def get_classifications_alias(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    from app.routes.classification_routes import list_classification_results
    return list_classification_results(limit=limit, offset=offset, db=db, settings=settings)


@router.get(
    "/api/email/{message_id}",
    response_model=EmailDetail,
    summary="Fetch Single Email by UID (Active Mailbox Only)",
)
def get_email_by_identifier(
    message_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> EmailDetail:
    settings = _resolve_settings(settings)
    scoped_settings, active_mb = _get_active_service_settings(db, settings)

    if not scoped_settings.is_configured and not active_mb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail credentials are not configured.",
        )

    service = IMAPService(settings=scoped_settings)
    try:
        return service.get_email_by_uid(uid=message_id, mailbox="INBOX")
    except IMAPConfigurationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except IMAPAuthenticationError as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(err))
    except IMAPMessageNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except IMAPConnectionError as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err))


# ==========================================
# Explicit Outbound Email Sending
# ==========================================

@router.post(
    "/api/email/send-test",
    response_model=SendEmailResponse,
    summary="Send Explicit Test Email via Active Mailbox",
)
def send_test_email(
    request: SendTestEmailRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SendEmailResponse:
    settings = _resolve_settings(settings)
    scoped_settings, active_mb = _get_active_service_settings(db, settings)

    if not scoped_settings.is_configured and not active_mb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail credentials are not configured.",
        )

    service = SMTPService(settings=scoped_settings)
    try:
        return service.send_email(
            recipient=request.recipient,
            subject="FastAPI Gmail Integration Test",
            body="This is an automated test email sent from the FastAPI Gmail Integration.",
        )
    except SMTPConfigurationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except SMTPAuthenticationError as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(err))
    except SMTPSendError as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err))


@router.post(
    "/api/email/send",
    response_model=SendEmailResponse,
    summary="Send Custom Email via Active Mailbox",
)
def send_custom_email(
    request: SendEmailRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SendEmailResponse:
    settings = _resolve_settings(settings)
    scoped_settings, active_mb = _get_active_service_settings(db, settings)

    if not scoped_settings.is_configured and not active_mb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail credentials are not configured.",
        )

    service = SMTPService(settings=scoped_settings)
    try:
        return service.send_email(
            recipient=request.recipient,
            subject=request.subject,
            body=request.body,
            body_html=request.body_html,
        )
    except SMTPConfigurationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except SMTPAuthenticationError as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(err))
    except SMTPSendError as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err))
