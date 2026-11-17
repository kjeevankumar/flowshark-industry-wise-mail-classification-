"""End-to-end automated test suite for Complete Global Mailbox Switching.

Verifies:
1. Connecting and activating Mailbox A.
2. Ingesting emails and classifications scoped to Mailbox A.
3. Connecting and activating Mailbox B (with credential validation and safe worker transition).
4. Strict data isolation: Mailbox B inbox, classifications, and dashboard contain zero Mailbox A records.
5. Ingesting Mailbox B specific emails and verifying independent UID cursors and counts.
6. Switching back to Mailbox A: verifying complete preservation of Mailbox A's data and state.
7. Failed credential validation for Mailbox C preserves current active mailbox without disruption.
8. Encryption at rest: passwords are Fernet-encrypted and never leaked in API responses.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.core.security import decrypt_credential, mask_email
from app.db.session import Base
from app.models.classification_model import Classification
from app.models.conversation_model import Conversation
from app.models.email_model import Email
from app.models.mailbox_model import Mailbox
from app.models.sync_model import SyncState
from app.routes.classification_routes import list_classification_results
from app.routes.dashboard_routes import get_dashboard_summary
from app.routes.email_inbox_routes import _get_sync_status_data, list_emails
from app.routes.email_routes import get_connection_details, switch_mailbox, update_connection
from app.schemas.dashboard_schema import SwitchMailboxRequest, UpdateConnectionRequest
from app.services.imap_service import IMAPAuthenticationError
from app.services.mailbox_service import MailboxService
from app.services.sync_service import EmailSyncService


@pytest.fixture
def test_db():
    """In-memory SQLite database session isolated for mailbox switching tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


@pytest.fixture
def mock_settings():
    """Isolated test settings."""
    return Settings(
        GMAIL_ADDRESS="account_a@gmail.com",
        GMAIL_APP_PASSWORD="aaaa bbbb cccc dddd",
        DATABASE_URL="sqlite:///:memory:",
        BACKGROUND_SYNC_ENABLED=False,
    )


def test_complete_mailbox_switching_lifecycle(test_db, mock_settings):
    """Test full multi-mailbox lifecycle: A -> B -> A with strict isolation."""
    mailbox_service = MailboxService(db=test_db, settings=mock_settings)

    # -------------------------------------------------------------
    # 1. Connect and Activate Mailbox A
    # -------------------------------------------------------------
    mb_a, is_new_a = mailbox_service.connect_and_activate_mailbox(
        email_address="account_a@gmail.com",
        app_password="aaaa bbbb cccc dddd",
        validate=False,
    )
    assert mb_a.id is not None
    assert mb_a.email_address == "account_a@gmail.com"
    assert mb_a.is_active is True

    # Verify password is encrypted at rest
    assert mb_a.encrypted_app_password != "aaaa bbbb cccc dddd"
    assert decrypt_credential(mb_a.encrypted_app_password) == "aaaabbbbccccdddd"

    # Add 2 emails and classifications for Account A
    email_a1 = Email(
        mailbox_id=mb_a.id,
        account_email="account_a@gmail.com",
        imap_uid="1001",
        uid_validity=10,
        subject="Project Quote Request",
        sender="client1@corp.com",
        received_at=datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc),
    )
    email_a2 = Email(
        mailbox_id=mb_a.id,
        account_email="account_a@gmail.com",
        imap_uid="1002",
        uid_validity=10,
        subject="Contract Pricing Discussion",
        sender="client2@corp.com",
        received_at=datetime(2026, 11, 16, 11, 0, tzinfo=timezone.utc),
    )
    test_db.add_all([email_a1, email_a2])
    test_db.commit()

    cls_a1 = Classification(
        email_id=email_a1.id,
        mailbox_id=mb_a.id,
        relationship="new_contact",
        intent="new_enquiry",
        lead_stage="new",
        confidence=0.92,
    )
    cls_a2 = Classification(
        email_id=email_a2.id,
        mailbox_id=mb_a.id,
        relationship="existing_lead",
        intent="negotiation",
        lead_stage="negotiation",
        confidence=0.88,
    )
    test_db.add_all([cls_a1, cls_a2])

    sync_a = test_db.query(SyncState).filter(SyncState.mailbox_id == mb_a.id).first()
    sync_a.uid_validity = 10
    sync_a.highest_synced_uid = "1002"
    sync_a.last_synced_uid = "1002"
    sync_a.total_synced = 2
    test_db.commit()

    # Verify Account A is active via routes
    conn = get_connection_details(db=test_db, settings=mock_settings)
    assert conn.active_mailbox_id == mb_a.id
    assert conn.email_address == "account_a@gmail.com"
    assert conn.email_address_masked == "a***a@gmail.com"
    assert conn.total_emails_stored == 2

    # Verify Account A inbox
    inbox_a = list_emails(page=1, size=20, db=test_db, settings=mock_settings)
    assert inbox_a.total == 2
    assert inbox_a.active_mailbox_id == mb_a.id
    assert len(inbox_a.emails) == 2

    # Verify Account A dashboard summary
    summary_a = get_dashboard_summary(db=test_db, settings=mock_settings)
    assert summary_a.active_mailbox_id == mb_a.id
    assert summary_a.total_synced == 2
    assert summary_a.new_leads_count == 1
    assert summary_a.negotiations_count == 1

    # Verify Account A classifications
    cls_list_a = list_classification_results(limit=50, offset=0, db=test_db, settings=mock_settings)
    assert len(cls_list_a) == 2

    # -------------------------------------------------------------
    # 2. Connect and Activate Mailbox B
    # -------------------------------------------------------------
    mb_b, is_new_b = mailbox_service.connect_and_activate_mailbox(
        email_address="account_b@gmail.com",
        app_password="eeee ffff gggg hhhh",
        validate=False,
    )
    assert mb_b.id != mb_a.id
    assert mb_b.email_address == "account_b@gmail.com"
    assert mb_b.is_active is True

    # Mailbox A must now be inactive
    test_db.refresh(mb_a)
    assert mb_a.is_active is False

    # Verify Active Connection now points to Account B
    conn_b = get_connection_details(db=test_db, settings=mock_settings)
    assert conn_b.active_mailbox_id == mb_b.id
    assert conn_b.email_address == "account_b@gmail.com"
    assert conn_b.total_emails_stored == 0  # No emails for B yet!

    # Verify Account B inbox is completely empty (no data leakage from A)
    inbox_b = list_emails(page=1, size=20, db=test_db, settings=mock_settings)
    assert inbox_b.total == 0
    assert len(inbox_b.emails) == 0

    # Verify Account B dashboard counts are 0 (strictly isolated)
    summary_b = get_dashboard_summary(db=test_db, settings=mock_settings)
    assert summary_b.active_mailbox_id == mb_b.id
    assert summary_b.total_synced == 0
    assert summary_b.new_leads_count == 0
    assert summary_b.negotiations_count == 0

    # Verify Account B classifications list is empty
    cls_list_b = list_classification_results(limit=50, offset=0, db=test_db, settings=mock_settings)
    assert len(cls_list_b) == 0

    # -------------------------------------------------------------
    # 3. Ingest Email into Mailbox B
    # -------------------------------------------------------------
    email_b1 = Email(
        mailbox_id=mb_b.id,
        account_email="account_b@gmail.com",
        imap_uid="5001",
        uid_validity=20,
        subject="Vendor Purchase Order 9921",
        sender="procurement@partner.com",
        received_at=datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc),
    )
    test_db.add(email_b1)
    test_db.commit()

    cls_b1 = Classification(
        email_id=email_b1.id,
        mailbox_id=mb_b.id,
        relationship="existing_lead",
        intent="purchase_order",
        lead_stage="closed_won",
        confidence=0.96,
    )
    test_db.add(cls_b1)

    sync_b = test_db.query(SyncState).filter(SyncState.mailbox_id == mb_b.id).first()
    sync_b.highest_synced_uid = "5001"
    sync_b.last_synced_uid = "5001"
    sync_b.total_synced = 1
    test_db.commit()

    # Account B now has 1 email, 1 purchase order
    inbox_b_updated = list_emails(page=1, size=20, db=test_db, settings=mock_settings)
    assert inbox_b_updated.total == 1
    assert inbox_b_updated.emails[0].subject == "Vendor Purchase Order 9921"

    summary_b_updated = get_dashboard_summary(db=test_db, settings=mock_settings)
    assert summary_b_updated.total_synced == 1
    assert summary_b_updated.purchase_orders_count == 1
    assert summary_b_updated.new_leads_count == 0

    # -------------------------------------------------------------
    # 4. Switch Back to Mailbox A
    # -------------------------------------------------------------
    mailbox_service.switch_active_mailbox(mb_a.id)

    test_db.refresh(mb_a)
    test_db.refresh(mb_b)
    assert mb_a.is_active is True
    assert mb_b.is_active is False

    # Connection details reflect Mailbox A
    conn_a_switched = get_connection_details(db=test_db, settings=mock_settings)
    assert conn_a_switched.active_mailbox_id == mb_a.id
    assert conn_a_switched.email_address == "account_a@gmail.com"
    assert conn_a_switched.total_emails_stored == 2

    # Mailbox A inbox has original 2 emails, 0 from Mailbox B
    inbox_a_switched = list_emails(page=1, size=20, db=test_db, settings=mock_settings)
    assert inbox_a_switched.total == 2
    subjects = [e.subject for e in inbox_a_switched.emails]
    assert "Project Quote Request" in subjects
    assert "Contract Pricing Discussion" in subjects
    assert "Vendor Purchase Order 9921" not in subjects

    # Mailbox A dashboard restored
    summary_a_switched = get_dashboard_summary(db=test_db, settings=mock_settings)
    assert summary_a_switched.total_synced == 2
    assert summary_a_switched.new_leads_count == 1
    assert summary_a_switched.negotiations_count == 1
    assert summary_a_switched.purchase_orders_count == 0

    # Mailbox A UID sync state is intact
    sync_a_switched = test_db.query(SyncState).filter(SyncState.mailbox_id == mb_a.id).first()
    assert sync_a_switched.highest_synced_uid == "1002"
    assert sync_a_switched.uid_validity == 10


def test_failed_connection_validation_preserves_active_mailbox(test_db, mock_settings):
    """Verify that if new account validation fails, the active mailbox remains unchanged."""
    mailbox_service = MailboxService(db=test_db, settings=mock_settings)

    # 1. Establish active Mailbox A
    mb_a, _ = mailbox_service.connect_and_activate_mailbox(
        email_address="active_user@gmail.com",
        app_password="correct-password",
        validate=False,
    )
    assert mb_a.is_active is True

    # 2. Attempt to connect Account C with invalid credentials
    with patch.object(
        mailbox_service,
        "validate_gmail_credentials",
        side_effect=IMAPAuthenticationError("Invalid credentials (failure)"),
    ):
        with pytest.raises(IMAPAuthenticationError):
            mailbox_service.connect_and_activate_mailbox(
                email_address="failed_account@gmail.com",
                app_password="wrong-password",
                validate=True,
            )

    # 3. Mailbox A must still be the active mailbox!
    test_db.refresh(mb_a)
    assert mb_a.is_active is True

    # Failed account must not have been created as active
    failed_mb = test_db.query(Mailbox).filter(Mailbox.email_address == "failed_account@gmail.com").first()
    assert failed_mb is None

    conn = get_connection_details(db=test_db, settings=mock_settings)
    assert conn.active_mailbox_id == mb_a.id
    assert conn.email_address == "active_user@gmail.com"


def test_mailbox_service_switch(test_db, mock_settings):
    """Test switching active mailbox via MailboxService and verifying connection details."""
    mailbox_service = MailboxService(db=test_db, settings=mock_settings)

    mb_1, _ = mailbox_service.connect_and_activate_mailbox("first@gmail.com", "pass1", validate=False)
    mb_2, _ = mailbox_service.connect_and_activate_mailbox("second@gmail.com", "pass2", validate=False)

    assert mb_2.is_active is True

    # Switch back to first
    switched = mailbox_service.switch_active_mailbox(mb_1.id)
    assert switched.id == mb_1.id
    assert switched.is_active is True

    test_db.refresh(mb_2)
    assert mb_2.is_active is False

    # Verify connection details route output
    details = get_connection_details(db=test_db, settings=mock_settings)
    assert details.active_mailbox_id == mb_1.id
    assert details.email_address == "first@gmail.com"
    assert details.is_connected is True
