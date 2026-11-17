"""Automated API endpoint and business logic tests.

Verifies:
- FastAPI router registration and paths
- Health check endpoint logic
- Safe configuration status inspection
- Missing credentials rejection (400 Bad Request)
- Pydantic payload and parameter validation
- Mocked IMAP operations (connectivity test, inbox listing, message retrieval)
- Mocked SMTP operations (independent auth test, explicit test email, custom email)
- Error status codes (401 Unauthorized, 404 Not Found, 502 Bad Gateway)
- Strictly zero automated outbound email sending
"""

from unittest.mock import MagicMock, patch
from fastapi import HTTPException
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.main import app
import app.routes.email_routes as email_routes
from app.schemas.email_schema import (
    EmailDetail,
    EmailSummary,
    SendEmailRequest,
    SendEmailResponse,
    SendTestEmailRequest,
)
from app.services.imap_service import (
    IMAPAuthenticationError,
    IMAPConnectionError,
    IMAPMessageNotFoundError,
)
from app.services.smtp_service import (
    SMTPAuthenticationError,
    SMTPSendError,
)


# ==========================================
# Route Registration Tests
# ==========================================

def test_routes_registered_on_fastapi():
    """Ensure all required endpoints are registered on the FastAPI app with expected HTTP methods."""
    routes_map = {route.path: route.methods for route in app.routes if hasattr(route, "methods")}

    assert "/api/health" in routes_map
    assert "GET" in routes_map["/api/health"]

    assert "/api/email/config-status" in routes_map
    assert "GET" in routes_map["/api/email/config-status"]

    assert "/api/email/test-imap" in routes_map
    assert "GET" in routes_map["/api/email/test-imap"]

    assert "/api/email/test-smtp" in routes_map
    assert "GET" in routes_map["/api/email/test-smtp"]

    assert "/api/email/inbox" in routes_map
    assert "GET" in routes_map["/api/email/inbox"]

    assert "/api/email/{message_id}" in routes_map
    assert "GET" in routes_map["/api/email/{message_id}"]

    assert "/api/email/send-test" in routes_map
    assert "POST" in routes_map["/api/email/send-test"]

    assert "/api/email/send" in routes_map
    assert "POST" in routes_map["/api/email/send"]


# ==========================================
# Health & Config Status Tests
# ==========================================

def test_health_check_logic():
    """Verify application health endpoint returns valid structure."""
    result = email_routes.get_health()
    assert result.status == "healthy"
    assert result.service == "gmail-fastapi-integration"
    assert result.version == "1.0.0"
    assert result.timestamp is not None


def test_config_status_unconfigured(mock_unconfigured_settings: Settings):
    """Verify config-status when credentials are not present."""
    result = email_routes.get_config_status(settings=mock_unconfigured_settings)
    assert result.configured is False
    assert result.gmail_address_configured is False
    assert result.app_password_configured is False
    assert result.gmail_address_masked is None
    assert "missing" in result.message.lower()


def test_config_status_configured(mock_configured_settings: Settings):
    """Verify config-status masks the email address and never leaks passwords."""
    result = email_routes.get_config_status(settings=mock_configured_settings)
    assert result.configured is True
    assert result.gmail_address_configured is True
    assert result.app_password_configured is True
    assert result.gmail_address_masked == "t***r@gmail.com"
    # Verify plain password is never exposed in output dict/str
    result_dict = result.model_dump()
    assert "abcd efgh" not in str(result_dict)


# ==========================================
# Missing Configuration Enforcement Tests
# ==========================================

def test_missing_config_rejects_imap_test(mock_unconfigured_settings: Settings):
    """Unconfigured environment must raise 400 on IMAP test."""
    with pytest.raises(HTTPException) as exc:
        email_routes.test_imap(settings=mock_unconfigured_settings)
    assert exc.value.status_code == 400
    assert "not configured" in exc.value.detail


def test_missing_config_rejects_smtp_test(mock_unconfigured_settings: Settings):
    """Unconfigured environment must raise 400 on SMTP test."""
    with pytest.raises(HTTPException) as exc:
        email_routes.test_smtp(settings=mock_unconfigured_settings)
    assert exc.value.status_code == 400
    assert "not configured" in exc.value.detail


def test_missing_config_rejects_inbox(mock_unconfigured_settings: Settings):
    """Unconfigured environment must raise 400 on inbox fetch."""
    with pytest.raises(HTTPException) as exc:
        email_routes.get_inbox_emails(limit=10, offset=0, settings=mock_unconfigured_settings)
    assert exc.value.status_code == 400


def test_missing_config_rejects_get_email_by_identifier(mock_unconfigured_settings: Settings):
    """Unconfigured environment must raise 400 on email retrieval."""
    with pytest.raises(HTTPException) as exc:
        email_routes.get_email_by_identifier("101", settings=mock_unconfigured_settings)
    assert exc.value.status_code == 400


def test_missing_config_rejects_send_test(mock_unconfigured_settings: Settings):
    """Unconfigured environment must raise 400 on send test."""
    req = SendTestEmailRequest(recipient="recipient@example.com")
    with pytest.raises(HTTPException) as exc:
        email_routes.send_test_email(request=req, settings=mock_unconfigured_settings)
    assert exc.value.status_code == 400


def test_missing_config_rejects_send_custom(mock_unconfigured_settings: Settings):
    """Unconfigured environment must raise 400 on custom send."""
    req = SendEmailRequest(recipient="recipient@example.com", subject="Hi", body="Hello")
    with pytest.raises(HTTPException) as exc:
        email_routes.send_custom_email(request=req, settings=mock_unconfigured_settings)
    assert exc.value.status_code == 400


# ==========================================
# Payload & Schema Validation Tests
# ==========================================

def test_invalid_recipient_format():
    """Pydantic must validate email format and reject invalid emails."""
    with pytest.raises(ValidationError):
        SendTestEmailRequest(recipient="not-an-email")

    with pytest.raises(ValidationError):
        SendEmailRequest(recipient="invalid-addr", subject="Subject", body="Body")


def test_missing_required_fields_in_send():
    """Missing or empty subject/body must trigger validation error."""
    with pytest.raises(ValidationError):
        SendEmailRequest(recipient="user@example.com", subject="", body="Body")

    with pytest.raises(ValidationError):
        SendEmailRequest(recipient="user@example.com", subject="Subject", body="")


# ==========================================
# Mocked IMAP Operations Tests
# ==========================================

@patch("app.routes.email_routes.IMAPService.test_connection")
def test_mocked_imap_test_success(mock_test, mock_configured_settings: Settings):
    """Verify successful IMAP test response with UIDVALIDITY and count."""
    mock_test.return_value = {
        "success": True,
        "message": "Successfully authenticated with Gmail IMAP.",
        "inbox_total_messages": 42,
        "uid_validity": 987654321,
    }

    result = email_routes.test_imap(settings=mock_configured_settings)
    assert result.success is True
    assert result.service == "IMAP"
    assert result.inbox_total_messages == 42
    assert result.uid_validity == 987654321


@patch("app.routes.email_routes.IMAPService.test_connection")
def test_mocked_imap_test_auth_failure(mock_test, mock_configured_settings: Settings):
    """Verify 401 HTTPException when IMAP credentials fail."""
    mock_test.side_effect = IMAPAuthenticationError("IMAP authentication failed.")
    with pytest.raises(HTTPException) as exc:
        email_routes.test_imap(settings=mock_configured_settings)
    assert exc.value.status_code == 401
    assert "authentication failed" in exc.value.detail.lower()


@patch("app.routes.email_routes.IMAPService.fetch_inbox_emails")
def test_mocked_inbox_listing(mock_fetch, mock_configured_settings: Settings):
    """Verify inbox listing endpoint returns structured summaries and pagination."""
    mock_emails = [
        EmailSummary(
            uid="1001",
            uid_validity=987654321,
            mailbox="INBOX",
            message_id="<msg-1@gmail.com>",
            thread_id="1859340294812345",
            subject="Hello World",
            sender="alice@example.com",
            recipient="testuser@gmail.com",
            date="Mon, 16 Nov 2026 12:00:00 +0000",
            snippet="Hello there...",
            has_attachments=False,
            attachment_count=0,
            in_reply_to=None,
            references=None,
        )
    ]
    mock_fetch.return_value = (mock_emails, 1, 987654321)

    result = email_routes.get_inbox_emails(limit=10, offset=0, settings=mock_configured_settings)
    assert result.total == 1
    assert result.count == 1
    assert result.uid_validity == 987654321
    assert len(result.emails) == 1
    email_item = result.emails[0]
    assert email_item.uid == "1001"
    assert email_item.thread_id == "1859340294812345"
    assert email_item.subject == "Hello World"


@patch("app.routes.email_routes.IMAPService.get_email_by_uid")
def test_mocked_get_email_by_uid_success(mock_get, mock_configured_settings: Settings):
    """Verify retrieval of a single email by UID."""
    mock_detail = EmailDetail(
        uid="1002",
        uid_validity=987654321,
        mailbox="INBOX",
        message_id="<msg-2@gmail.com>",
        thread_id="1859340294812345",
        subject="Detailed Subject",
        sender="sender@example.com",
        recipient="testuser@gmail.com",
        date="Mon, 16 Nov 2026 13:00:00 +0000",
        snippet="Snippet here",
        body_plain="Detailed plain body content",
        body_html="<p>Detailed plain body content</p>",
        in_reply_to="<parent-0@gmail.com>",
        references="<parent-0@gmail.com>",
        has_attachments=False,
        attachments=[],
    )
    mock_get.return_value = mock_detail

    result = email_routes.get_email_by_identifier("1002", settings=mock_configured_settings)
    assert result.uid == "1002"
    assert result.body_plain == "Detailed plain body content"
    assert result.in_reply_to == "<parent-0@gmail.com>"


@patch("app.routes.email_routes.IMAPService.get_email_by_uid")
def test_mocked_get_email_not_found(mock_get, mock_configured_settings: Settings):
    """Verify 404 HTTPException when UID is not in mailbox."""
    mock_get.side_effect = IMAPMessageNotFoundError("Message with UID '9999' was not found.")
    with pytest.raises(HTTPException) as exc:
        email_routes.get_email_by_identifier("9999", settings=mock_configured_settings)
    assert exc.value.status_code == 404
    assert "9999" in exc.value.detail


# ==========================================
# Mocked SMTP Operations Tests
# ==========================================

@patch("app.routes.email_routes.SMTPService.test_connection")
def test_mocked_smtp_test_success(mock_test, mock_configured_settings: Settings):
    """Verify independent SMTP authentication test without sending messages."""
    mock_test.return_value = {
        "success": True,
        "message": "Successfully authenticated with Gmail SMTP server.",
        "details": {"smtp_host": "smtp.gmail.com", "smtp_port": 587},
    }

    result = email_routes.test_smtp(settings=mock_configured_settings)
    assert result.success is True
    assert result.service == "SMTP"


@patch("app.routes.email_routes.SMTPService.test_connection")
def test_mocked_smtp_test_auth_failure(mock_test, mock_configured_settings: Settings):
    """Verify 401 HTTPException on SMTP credential failure."""
    mock_test.side_effect = SMTPAuthenticationError("SMTP authentication failed.")
    with pytest.raises(HTTPException) as exc:
        email_routes.test_smtp(settings=mock_configured_settings)
    assert exc.value.status_code == 401
    assert "authentication failed" in exc.value.detail.lower()


@patch("app.routes.email_routes.SMTPService.send_email")
def test_mocked_send_test_email(mock_send, mock_configured_settings: Settings):
    """Verify manual test email sending with explicit authorization."""
    mock_send.return_value = SendEmailResponse(
        success=True,
        message="Email sent successfully via Gmail SMTP.",
        recipient="destination@example.com",
        message_id="<test-id-123@smtp.gmail.com>",
    )

    req = SendTestEmailRequest(recipient="destination@example.com")
    result = email_routes.send_test_email(request=req, settings=mock_configured_settings)
    assert result.success is True
    assert result.recipient == "destination@example.com"
    assert result.message_id == "<test-id-123@smtp.gmail.com>"


@patch("app.routes.email_routes.SMTPService.send_email")
def test_mocked_send_custom_email(mock_send, mock_configured_settings: Settings):
    """Verify custom email dispatch."""
    mock_send.return_value = SendEmailResponse(
        success=True,
        message="Email sent successfully via Gmail SMTP.",
        recipient="customer@example.com",
        message_id="<custom-id-456@smtp.gmail.com>",
    )

    req = SendEmailRequest(
        recipient="customer@example.com",
        subject="Greetings",
        body="This is the message body.",
        body_html="<p>This is the message body.</p>",
    )
    result = email_routes.send_custom_email(request=req, settings=mock_configured_settings)
    assert result.success is True
    assert result.message_id == "<custom-id-456@smtp.gmail.com>"


@patch("app.routes.email_routes.SMTPService.send_email")
def test_mocked_send_failure(mock_send, mock_configured_settings: Settings):
    """Verify 502 HTTPException when SMTP transmission fails."""
    mock_send.side_effect = SMTPSendError("Failed to transmit email: Connection dropped")

    req = SendEmailRequest(recipient="client@example.com", subject="Test", body="Hello")
    with pytest.raises(HTTPException) as exc:
        email_routes.send_custom_email(request=req, settings=mock_configured_settings)
    assert exc.value.status_code == 502
    assert "Connection dropped" in exc.value.detail
