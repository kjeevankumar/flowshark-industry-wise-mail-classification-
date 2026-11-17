"""Pytest configuration and reusable test fixtures."""

from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
import pytest
from starlette.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


@pytest.fixture
def mock_unconfigured_settings() -> Settings:
    """Returns a Settings instance where credentials are not configured."""
    return Settings(
        GMAIL_ADDRESS=None,
        GMAIL_APP_PASSWORD=None,
        IMAP_HOST="imap.gmail.com",
        IMAP_PORT=993,
        SMTP_HOST="smtp.gmail.com",
        SMTP_PORT=587,
        APP_ENV="testing",
    )


@pytest.fixture
def mock_configured_settings() -> Settings:
    """Returns a Settings instance with valid dummy credentials."""
    return Settings(
        GMAIL_ADDRESS="testuser@gmail.com",
        GMAIL_APP_PASSWORD="abcd efgh ijkl mnop",
        IMAP_HOST="imap.gmail.com",
        IMAP_PORT=993,
        SMTP_HOST="smtp.gmail.com",
        SMTP_PORT=587,
        APP_ENV="testing",
    )


@pytest.fixture
def client(mock_unconfigured_settings: Settings) -> TestClient:
    """Default test client with unconfigured settings."""
    app.dependency_overrides[get_settings] = lambda: mock_unconfigured_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def configured_client(mock_configured_settings: Settings) -> TestClient:
    """Test client with configured dummy settings."""
    app.dependency_overrides[get_settings] = lambda: mock_configured_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ==========================================
# Sample Raw MIME Emails for Parser Testing
# ==========================================

@pytest.fixture
def sample_plaintext_email_bytes() -> bytes:
    """Generates a raw RFC 822 plain text email with standard headers."""
    msg = MIMEText("Hello world! This is a simple test email.\nHave a great day.", "plain", "utf-8")
    msg["Subject"] = "Simple Plaintext Test"
    msg["From"] = "Sender Name <sender@example.com>"
    msg["To"] = "recipient@example.com"
    msg["Date"] = "Mon, 16 Nov 2026 10:00:00 +0000"
    msg["Message-ID"] = "<msg-001@example.com>"
    msg["In-Reply-To"] = "<parent-000@example.com>"
    msg["References"] = "<thread-root@example.com> <parent-000@example.com>"
    return msg.as_bytes()


@pytest.fixture
def sample_multipart_email_bytes() -> bytes:
    """Generates a multipart/alternative email with plain text and HTML bodies."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Multipart Alternative Email"
    msg["From"] = "Marketing <marketing@company.com>"
    msg["To"] = "client@example.com"
    msg["Date"] = "Mon, 16 Nov 2026 11:30:00 +0000"
    msg["Message-ID"] = "<msg-002@company.com>"

    text_part = MIMEText("Plain version: Welcome to our platform!", "plain", "utf-8")
    html_part = MIMEText("<html><body><h3>Welcome to our platform!</h3><p>Enjoy your trial.</p></body></html>", "html", "utf-8")
    msg.attach(text_part)
    msg.attach(html_part)
    return msg.as_bytes()


@pytest.fixture
def sample_email_with_attachment_bytes() -> bytes:
    """Generates a multipart email containing text and a PDF attachment."""
    msg = MIMEMultipart("mixed")
    msg["Subject"] = "Invoice for November 2026"
    msg["From"] = "Billing <billing@service.com>"
    msg["To"] = "accounting@client.com"
    msg["Date"] = "Mon, 16 Nov 2026 12:15:00 +0000"
    msg["Message-ID"] = "<msg-003@service.com>"

    body = MIMEText("Please find attached the invoice for your latest billing cycle.", "plain", "utf-8")
    msg.attach(body)

    # Attach fake PDF
    att = MIMEBase("application", "pdf")
    att.set_payload(b"%PDF-1.4 simulated pdf binary content here...")
    encoders.encode_base64(att)
    att.add_header("Content-Disposition", "attachment", filename="invoice_nov2026.pdf")
    msg.attach(att)
    return msg.as_bytes()


@pytest.fixture
def sample_mime_encoded_subject_bytes() -> bytes:
    """Generates an email with RFC 2047 MIME-encoded subjects (Base64 UTF-8 and Quoted-Printable)."""
    # Raw RFC 822 formatted message with encoded subject
    raw = (
        b"From: =?UTF-8?B?Sm/Do28gU2lsdmE=?= <joao@example.com>\r\n"
        b"To: user@example.com\r\n"
        b"Subject: =?UTF-8?B?UmVsYXTDs3JpbyBGZWxpY2lkYWRlOiDwn5iK?= - =?ISO-8859-1?Q?Caf=E9?=\r\n"
        b"Date: Mon, 16 Nov 2026 13:00:00 +0000\r\n"
        b"Message-ID: <msg-encoded-004@example.com>\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"Contedo do email com acentos e caracteres especiais.\r\n"
    )
    return raw

