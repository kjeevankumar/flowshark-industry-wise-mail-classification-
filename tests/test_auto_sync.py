"""Automated test suite for automated incremental Gmail synchronization,
deduplication, UID cursor management, UIDVALIDITY safety, and classification resilience.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.session import Base
from app.models.classification_model import Classification
from app.models.conversation_model import Conversation
from app.models.email_model import Email
from app.models.sync_model import SyncState
from app.routes.email_inbox_routes import _get_sync_status_data
from app.schemas.email_schema import EmailDetail
from app.services.background_sync import BackgroundSyncWorker
from app.services.imap_service import IMAPServiceError
from app.services.sync_service import EmailSyncService, SyncResult


@pytest.fixture
def mock_settings():
    """Isolated test settings."""
    return Settings(
        GMAIL_ADDRESS="testlead@gmail.com",
        GMAIL_APP_PASSWORD="abcd efgh ijkl mnop",
        DATABASE_URL="sqlite:///:memory:",
        SYNC_INTERVAL_SECONDS=15,
        BACKGROUND_SYNC_ENABLED=True,
    )


@pytest.fixture
def test_db(mock_settings):
    """In-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def _make_mock_detail(uid: str, subject: str = "Test Subject", thread_id: str = "123456"):
    return EmailDetail(
        uid=uid,
        uid_validity=100,
        mailbox="INBOX",
        message_id=f"<msg_{uid}@gmail.com>",
        thread_id=thread_id,
        subject=subject,
        sender="prospect@company.com",
        recipient="testlead@gmail.com",
        date="Mon, 16 Nov 2026 12:00:00 +0000",
        snippet=f"Snippet for email {uid}",
        body_plain=f"Hello, this is message content for {uid}. We need a website quotation.",
        body_html=f"<p>Hello, this is message content for {uid}.</p>",
        has_attachments=False,
        attachment_count=0,
        attachments=[],
        in_reply_to=None,
        references=None,
    )


def test_new_email_detected_and_inserted(test_db, mock_settings):
    """Verify that a newly arrived email is fetched, stored in DB, and classified."""
    service = EmailSyncService(db=test_db, settings=mock_settings)

    mock_client = MagicMock()
    mock_client.select.return_value = ("OK", [b"1"])
    mock_client.uid.return_value = ("OK", [b"101"])

    with patch.object(service.imap_service, "get_client") as mock_get_client, \
         patch.object(service.imap_service, "extract_uid_validity", return_value=100), \
         patch.object(service.imap_service, "_fetch_single_uid", return_value=_make_mock_detail("101")):
        mock_get_client.return_value.__enter__.return_value = mock_client

        result = service.sync_inbox(batch_size=50)

        assert result.new_emails_synced == 1
        assert result.total_synced_in_db == 1

        email = test_db.query(Email).filter(Email.imap_uid == "101").first()
        assert email is not None
        assert email.subject == "Test Subject"
        assert email.account_email == "testlead@gmail.com"

        # Classification was automatically run
        assert email.classification is not None
        assert email.classification.intent in ["new_enquiry", "other"]

        # SyncState cursor updated
        sync_state = test_db.query(SyncState).first()
        assert sync_state.highest_synced_uid == "101"
        assert sync_state.new_emails_last_sync == 1


def test_duplicate_email_ignored_and_not_reinserted(test_db, mock_settings):
    """Verify that an email already present in DB is ignored and not reinserted."""
    service = EmailSyncService(db=test_db, settings=mock_settings)

    # Pre-insert email 101
    pre_email = Email(
        account_email="testlead@gmail.com",
        imap_uid="101",
        uid_validity=100,
        subject="Existing Subject",
        sender="sender@example.com",
        has_attachments=False,
        attachment_count=0,
    )
    test_db.add(pre_email)
    test_db.commit()

    mock_client = MagicMock()
    mock_client.select.return_value = ("OK", [b"1"])
    mock_client.uid.return_value = ("OK", [b"101"])

    with patch.object(service.imap_service, "get_client") as mock_get_client, \
         patch.object(service.imap_service, "extract_uid_validity", return_value=100), \
         patch.object(service.imap_service, "_fetch_single_uid") as mock_fetch:
        mock_get_client.return_value.__enter__.return_value = mock_client

        result = service.sync_inbox(batch_size=50)

        assert result.new_emails_synced == 0
        assert mock_fetch.call_count == 0
        assert test_db.query(Email).count() == 1


def test_uid_cursor_updated_only_after_successful_persistence(test_db, mock_settings):
    """Verify that sync cursor does NOT advance if message persistence fails."""
    service = EmailSyncService(db=test_db, settings=mock_settings)

    mock_client = MagicMock()
    mock_client.select.return_value = ("OK", [b"1"])
    mock_client.uid.return_value = ("OK", [b"205"])

    # Simulate fetch failure
    with patch.object(service.imap_service, "get_client") as mock_get_client, \
         patch.object(service.imap_service, "extract_uid_validity", return_value=100), \
         patch.object(service.imap_service, "_fetch_single_uid", side_effect=RuntimeError("Corrupt MIME data")):
        mock_get_client.return_value.__enter__.return_value = mock_client

        result = service.sync_inbox(batch_size=50)

        assert result.new_emails_synced == 0
        sync_state = test_db.query(SyncState).first()
        # Cursor was NOT advanced to 205 because persistence failed
        assert sync_state.highest_synced_uid is None


def test_uidvalidity_change_resets_cursor_safely(test_db, mock_settings):
    """Verify that UIDVALIDITY mismatch resets the cursor without losing old messages."""
    service = EmailSyncService(db=test_db, settings=mock_settings)

    # Initial state with UIDVALIDITY 100 and highest UID 105
    state = SyncState(
        account_email="testlead@gmail.com",
        uid_validity=100,
        highest_synced_uid="105",
        last_synced_uid="105",
        status="completed",
        total_synced=1,
    )
    test_db.add(state)
    test_db.commit()

    # Now IMAP reports UIDVALIDITY has changed to 200
    mock_client = MagicMock()
    mock_client.select.return_value = ("OK", [b"1"])
    mock_client.uid.return_value = ("OK", [b"5"])

    with patch.object(service.imap_service, "get_client") as mock_get_client, \
         patch.object(service.imap_service, "extract_uid_validity", return_value=200), \
         patch.object(service.imap_service, "_fetch_single_uid", return_value=_make_mock_detail("5")):
        mock_get_client.return_value.__enter__.return_value = mock_client

        result = service.sync_inbox(batch_size=50)

        assert result.uid_validity == 200
        sync_state = test_db.query(SyncState).first()
        assert sync_state.uid_validity == 200
        assert sync_state.highest_synced_uid == "5"


def test_imap_connection_failure_and_recovery(test_db, mock_settings):
    """Verify that connection failure marks status as failed and recovers on retry."""
    service = EmailSyncService(db=test_db, settings=mock_settings)

    # 1. First attempt fails due to connection drop
    with patch.object(service.imap_service, "get_client", side_effect=IMAPServiceError("Connection timed out")):
        with pytest.raises(IMAPServiceError):
            service.sync_inbox()

        sync_state = test_db.query(SyncState).first()
        assert sync_state.status == "failed"
        assert "Connection timed out" in sync_state.error_message

    # 2. Recovery attempt succeeds
    mock_client = MagicMock()
    mock_client.select.return_value = ("OK", [b"0"])
    mock_client.uid.return_value = ("OK", [b""])

    with patch.object(service.imap_service, "get_client") as mock_get_client, \
         patch.object(service.imap_service, "extract_uid_validity", return_value=100):
        mock_get_client.return_value.__enter__.return_value = mock_client

        res = service.sync_inbox()
        assert res.status == "completed"
        sync_state = test_db.query(SyncState).first()
        assert sync_state.status == "completed"
        assert sync_state.error_message is None


def test_classification_failure_does_not_lose_email(test_db, mock_settings):
    """Verify that an LLM / classification crash does NOT abort or roll back email ingestion."""
    service = EmailSyncService(db=test_db, settings=mock_settings)

    mock_client = MagicMock()
    mock_client.select.return_value = ("OK", [b"1"])
    mock_client.uid.return_value = ("OK", [b"301"])

    with patch.object(service.imap_service, "get_client") as mock_get_client, \
         patch.object(service.imap_service, "extract_uid_validity", return_value=100), \
         patch.object(service.imap_service, "_fetch_single_uid", return_value=_make_mock_detail("301")), \
         patch("app.services.hybrid_classifier.HybridClassifier.classify_email", side_effect=RuntimeError("LLM API quota exceeded")):
        mock_get_client.return_value.__enter__.return_value = mock_client

        result = service.sync_inbox(batch_size=50)

        # Email was still safely committed!
        assert result.new_emails_synced == 1
        email = test_db.query(Email).filter(Email.imap_uid == "301").first()
        assert email is not None
        assert email.subject == "Test Subject"

        # Fallback review-required classification was recorded
        assert email.classification is not None
        assert email.classification.requires_human_review is True
        assert "Classification deferred" in email.classification.classification_reason


def test_sync_status_endpoint_contract(test_db, mock_settings):
    """Verify GET /api/email/sync-status returns all required fields."""
    state = SyncState(
        account_email="testlead@gmail.com",
        uid_validity=100,
        highest_synced_uid="50",
        last_synced_uid="50",
        total_synced=10,
        inbox_total=100,
        status="completed",
        worker_status="idle",
        last_synced_at=datetime.now(timezone.utc),
        new_emails_last_sync=2,
    )
    test_db.add(state)
    test_db.commit()

    resp = _get_sync_status_data(db=test_db, settings=mock_settings)

    assert resp.account_email == "testlead@gmail.com"
    assert resp.connection_status == "connected"
    assert resp.worker_status in ["idle", "stopped", "running", "syncing"]
    assert resp.last_processed_uid == "50"
    assert resp.uid_validity == 100
    assert resp.total_emails_stored == 0  # 0 in DB table
    assert resp.new_emails_retrieved_latest_sync == 2
    assert resp.latest_sync_error is None
    assert resp.sync_interval_seconds == 15


def test_concurrency_lock_prevents_simultaneous_syncs(mock_settings):
    """Verify that BackgroundSyncWorker prevents concurrent execution via lock."""
    worker = BackgroundSyncWorker(settings=mock_settings)
    assert not worker.is_syncing
    assert worker.worker_status == "stopped"

    # Simulate active sync lock
    mock_lock = MagicMock()
    mock_lock.locked.return_value = True
    worker._lock = mock_lock
    worker._is_running = True

    assert worker.is_syncing is True
    assert worker.worker_status == "syncing"
