"""Pydantic schemas for request and response validation.

Defines all data transfer objects (DTOs) with strict validation, descriptive fields,
and realistic documentation examples for OpenAPI / Swagger UI.
"""

from datetime import datetime, timezone
import re
from typing import Annotated, List, Optional
from pydantic import AfterValidator, BaseModel, Field

# RFC-compliant email address validation pattern without external dependencies
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_email_address(value: str) -> str:
    """Validate email address format and strip whitespace."""
    if not isinstance(value, str):
        raise ValueError("Email address must be a string")
    cleaned = value.strip()
    if not EMAIL_REGEX.match(cleaned):
        raise ValueError(f"'{value}' is not a valid email address.")
    return cleaned


EmailAddress = Annotated[str, AfterValidator(validate_email_address)]


# ==========================================
# Health & Status Schemas
# ==========================================

class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(..., examples=["healthy"])
    service: str = Field(..., examples=["gmail-fastapi-integration"])
    version: str = Field(..., examples=["1.0.0"])
    timestamp: str = Field(..., examples=["2026-11-16T12:00:00Z"])


class ConfigStatusResponse(BaseModel):
    """Configuration status response without revealing credentials."""
    configured: bool = Field(..., description="Whether both Gmail address and App Password are set")
    gmail_address_configured: bool = Field(..., description="True if GMAIL_ADDRESS is present")
    gmail_address_masked: Optional[str] = Field(None, examples=["u***@gmail.com"], description="Masked Gmail address")
    app_password_configured: bool = Field(..., description="True if GMAIL_APP_PASSWORD is set")
    imap_host: str = Field(..., examples=["imap.gmail.com"])
    imap_port: int = Field(..., examples=[993])
    smtp_host: str = Field(..., examples=["smtp.gmail.com"])
    smtp_port: int = Field(..., examples=[587])
    message: str = Field(..., examples=["Gmail credentials configured and ready."])


class ConnectionTestResponse(BaseModel):
    """Result of an IMAP or SMTP connection/authentication test."""
    success: bool = Field(..., examples=[True])
    service: str = Field(..., examples=["IMAP"])
    message: str = Field(..., examples=["Successfully connected and authenticated to Gmail IMAP."])
    inbox_total_messages: Optional[int] = Field(None, examples=[152], description="Total messages in INBOX (for IMAP)")
    uid_validity: Optional[int] = Field(None, examples=[658941230], description="Mailbox UIDVALIDITY (for IMAP)")
    details: Optional[dict] = Field(None, description="Optional diagnostic metadata")


# ==========================================
# Email Data Schemas
# ==========================================

class AttachmentMetadata(BaseModel):
    """Metadata describing an email attachment without holding raw bytes in memory."""
    filename: str = Field(..., examples=["invoice_nov2026.pdf"])
    content_type: str = Field(..., examples=["application/pdf"])
    size_bytes: int = Field(..., examples=[45210])


class EmailSummary(BaseModel):
    """Summary representation of an email for inbox listing and previews."""
    uid: str = Field(..., examples=["1042"], description="IMAP UID (permanent message identifier within mailbox)")
    uid_validity: Optional[int] = Field(None, examples=[658941230], description="Mailbox UIDVALIDITY context")
    mailbox: str = Field(default="INBOX", examples=["INBOX"], description="Mailbox folder name")
    message_id: Optional[str] = Field(None, examples=["<CAGy123@mail.gmail.com>"], description="RFC 2822 Message-ID header")
    thread_id: Optional[str] = Field(None, examples=["1859340294812345"], description="Gmail Thread ID (X-GM-THRID)")
    subject: str = Field(..., examples=["Project Update & Weekly Milestone"])
    sender: str = Field(..., examples=["Alice Smith <alice@example.com>"])
    recipient: Optional[str] = Field(None, examples=["bob@example.com"])
    date: Optional[str] = Field(None, examples=["Mon, 16 Nov 2026 14:32:00 +0000"])
    snippet: str = Field(..., examples=["Hi Bob, here is the weekly progress report on our project..."])
    has_attachments: bool = Field(..., examples=[False])
    attachment_count: int = Field(..., examples=[0])
    in_reply_to: Optional[str] = Field(None, examples=["<ref456@mail.gmail.com>"], description="RFC 2822 In-Reply-To header")
    references: Optional[str] = Field(None, examples=["<thread123@mail.gmail.com>"], description="RFC 2822 References header")


class EmailDetail(BaseModel):
    """Comprehensive email representation including bodies, full headers, and attachment list."""
    uid: str = Field(..., examples=["1042"], description="IMAP UID (permanent message identifier within mailbox)")
    uid_validity: Optional[int] = Field(None, examples=[658941230], description="Mailbox UIDVALIDITY context")
    mailbox: str = Field(default="INBOX", examples=["INBOX"], description="Mailbox folder name")
    message_id: Optional[str] = Field(None, examples=["<CAGy123@mail.gmail.com>"], description="RFC 2822 Message-ID header")
    thread_id: Optional[str] = Field(None, examples=["1859340294812345"], description="Gmail Thread ID (X-GM-THRID)")
    subject: str = Field(..., examples=["Project Update & Weekly Milestone"])
    sender: str = Field(..., examples=["Alice Smith <alice@example.com>"])
    recipient: Optional[str] = Field(None, examples=["bob@example.com"])
    cc: Optional[str] = Field(None, examples=["carol@example.com"])
    bcc: Optional[str] = Field(None)
    date: Optional[str] = Field(None, examples=["Mon, 16 Nov 2026 14:32:00 +0000"])
    snippet: str = Field(..., examples=["Hi Bob, here is the weekly progress report on our project..."])
    body_plain: Optional[str] = Field(None, examples=["Hi Bob,\n\nHere is the weekly progress report..."])
    body_html: Optional[str] = Field(None, examples=["<p>Hi Bob,</p><p>Here is the weekly progress report...</p>"])
    in_reply_to: Optional[str] = Field(None, examples=["<parent123@mail.gmail.com>"], description="RFC 2822 In-Reply-To header")
    references: Optional[str] = Field(None, examples=["<thread123@mail.gmail.com> <parent123@mail.gmail.com>"], description="RFC 2822 References header")
    has_attachments: bool = Field(..., examples=[True])
    attachments: List[AttachmentMetadata] = Field(default_factory=list)


class InboxResponse(BaseModel):
    """Paginated inbox listing response."""
    total: int = Field(..., examples=[120], description="Total number of messages available in INBOX")
    count: int = Field(..., examples=[10], description="Number of messages returned in this page")
    offset: int = Field(..., examples=[0], description="Pagination offset applied")
    limit: int = Field(..., examples=[10], description="Page limit applied")
    uid_validity: Optional[int] = Field(None, examples=[658941230], description="Mailbox UIDVALIDITY")
    emails: List[EmailSummary] = Field(default_factory=list)


# ==========================================
# Email Sending Schemas
# ==========================================

class SendTestEmailRequest(BaseModel):
    """Request payload to trigger an explicit test email."""
    recipient: EmailAddress = Field(
        ...,
        examples=["your_email@gmail.com"],
        description="Recipient email address to receive the test message",
    )


class SendEmailRequest(BaseModel):
    """Request payload to send a custom email."""
    recipient: EmailAddress = Field(
        ...,
        examples=["customer@example.com"],
        description="Target recipient email address",
    )
    subject: str = Field(
        ...,
        min_length=1,
        max_length=500,
        examples=["Important: Service Notification"],
        description="Email subject line",
    )
    body: str = Field(
        ...,
        min_length=1,
        examples=["Hello, this is a notification message sent via FastAPI Gmail integration."],
        description="Plain text email body content",
    )
    body_html: Optional[str] = Field(
        None,
        examples=["<p>Hello, this is a <strong>notification</strong> message.</p>"],
        description="Optional HTML formatted email body content",
    )


class SendEmailResponse(BaseModel):
    """Response returned upon email dispatch."""
    success: bool = Field(..., examples=[True])
    message: str = Field(..., examples=["Email sent successfully"])
    recipient: str = Field(..., examples=["customer@example.com"])
    message_id: Optional[str] = Field(None, examples=["<20261116120000.12345.gmail@fastapi>"])
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        examples=["2026-11-16T12:00:00Z"],
    )


# ==========================================
# Error Response Schemas
# ==========================================

class ErrorResponse(BaseModel):
    """Standard error response format."""
    detail: str = Field(..., examples=["Authentication failed. Please verify your Gmail address and App Password."])
    error_code: Optional[str] = Field(None, examples=["AUTHENTICATION_FAILED"])
