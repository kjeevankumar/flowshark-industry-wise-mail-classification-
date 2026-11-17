"""SMTP Service for Gmail integration.

Implements:
- TLS connection to smtp.gmail.com on port 587 with STARTTLS and timeout.
- Authentication using Gmail address and 16-character App Password.
- Independent SMTP authentication testing without sending any messages.
- Sending text and multipart/alternative (HTML) emails with RFC 2822 compliance.
- Safe connection cleanup and strict redaction of credentials in logs.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib
import socket
from typing import Generator, Optional, Tuple

from app.config import Settings, get_settings
from app.schemas.email_schema import SendEmailResponse

logger = logging.getLogger("gmail_fastapi.smtp")


class SMTPServiceError(Exception):
    """Base exception for SMTP service errors."""
    pass


class SMTPConfigurationError(SMTPServiceError):
    """Raised when SMTP credentials or settings are missing/invalid."""
    pass


class SMTPAuthenticationError(SMTPServiceError):
    """Raised when authentication against the SMTP server fails."""
    pass


class SMTPConnectionError(SMTPServiceError):
    """Raised when connection or TLS handshake to the SMTP server fails."""
    pass


class SMTPSendError(SMTPServiceError):
    """Raised when email transmission fails."""
    pass


class SMTPService:
    """Manages SMTP connections and email dispatch."""

    def __init__(self, settings: Optional[Settings] = None):
        if settings is None or not isinstance(settings, Settings):
            self.settings = get_settings()
        else:
            self.settings = settings

    def _validate_configuration(self) -> Tuple[str, str]:
        """Validate credentials without exposing them in logs or exceptions."""
        if not self.settings.GMAIL_ADDRESS or not self.settings.GMAIL_ADDRESS.strip():
            raise SMTPConfigurationError("Gmail address is not configured. Please set GMAIL_ADDRESS in .env.")
        clean_pwd = self.settings.clean_app_password
        if not clean_pwd:
            raise SMTPConfigurationError("Gmail App Password is not configured. Please set GMAIL_APP_PASSWORD in .env.")
        return self.settings.GMAIL_ADDRESS.strip(), clean_pwd

    @contextmanager
    def get_client(self) -> Generator[smtplib.SMTP, None, None]:
        """Establish an authenticated SMTP connection with STARTTLS and safe cleanup."""
        username, password = self._validate_configuration()
        client: Optional[smtplib.SMTP] = None

        try:
            # Connect with configured socket timeout
            client = smtplib.SMTP(
                host=self.settings.SMTP_HOST,
                port=self.settings.SMTP_PORT,
                timeout=self.settings.SMTP_TIMEOUT_SECONDS,
            )
            # Send EHLO and initiate TLS encryption
            client.ehlo()
            client.starttls()
            client.ehlo()
        except (socket.timeout, TimeoutError) as err:
            logger.error("SMTP connection timed out connecting to %s:%s", self.settings.SMTP_HOST, self.settings.SMTP_PORT)
            raise SMTPConnectionError(f"Connection to SMTP server {self.settings.SMTP_HOST}:{self.settings.SMTP_PORT} timed out.") from err
        except (socket.gaierror, ConnectionRefusedError, OSError) as err:
            logger.error("SMTP connection failed: %s", str(err))
            raise SMTPConnectionError(f"Failed to connect to SMTP server: {str(err)}") from err

        try:
            # Authenticate
            client.login(username, password)
        except smtplib.SMTPAuthenticationError as err:
            logger.warning("SMTP authentication failed for %s", self.settings.masked_gmail_address)
            raise SMTPAuthenticationError("SMTP authentication failed. Please verify your Gmail address and 16-character App Password.") from err
        except smtplib.SMTPServerDisconnected as err:
            logger.warning("SMTP disconnected during authentication for %s", self.settings.masked_gmail_address)
            raise SMTPAuthenticationError(
                "SMTP connection closed by Gmail during authentication. This occurs when an invalid password or regular account password is used instead of a 16-character Google App Password."
            ) from err
        except smtplib.SMTPException as err:
            logger.error("SMTP error during handshake: %s", str(err))
            raise SMTPConnectionError(f"SMTP error during handshake: {str(err)}") from err

        try:
            yield client
        finally:
            if client:
                try:
                    # Cleanly close connection
                    client.quit()
                except Exception:
                    pass

    def test_connection(self) -> dict:
        """Test SMTP connection and authentication WITHOUT sending any email."""
        with self.get_client() as client:
            # Verify client state
            noop_code, _ = client.noop()
            return {
                "success": True,
                "message": f"Successfully connected, encrypted with STARTTLS, and authenticated with Gmail SMTP server ({self.settings.SMTP_HOST}:{self.settings.SMTP_PORT}).",
                "details": {
                    "smtp_host": self.settings.SMTP_HOST,
                    "smtp_port": self.settings.SMTP_PORT,
                    "noop_status": noop_code,
                },
            }

    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None,
    ) -> SendEmailResponse:
        """Compose and send a compliant RFC 2822 email via Gmail SMTP."""
        username, _ = self._validate_configuration()

        # Build message
        if body_html:
            msg = MIMEMultipart("alternative")
            part_text = MIMEText(body, "plain", "utf-8")
            part_html = MIMEText(body_html, "html", "utf-8")
            msg.attach(part_text)
            msg.attach(part_html)
        else:
            msg = MIMEText(body, "plain", "utf-8")

        # Set standard headers
        msg["From"] = username
        msg["To"] = recipient.strip()
        msg["Subject"] = subject.strip()
        msg["Date"] = email.utils.formatdate(localtime=True)
        message_id = email.utils.make_msgid(domain=self.settings.SMTP_HOST)
        msg["Message-ID"] = message_id

        with self.get_client() as client:
            try:
                client.send_message(msg)
                logger.info("Successfully sent email to %s with Message-ID %s", recipient, message_id)
            except smtplib.SMTPRecipientsRefused as err:
                logger.warning("Recipient rejected: %s", recipient)
                raise SMTPSendError(f"Recipient email '{recipient}' was rejected by Gmail.") from err
            except smtplib.SMTPSenderRefused as err:
                raise SMTPSendError("Sender address was rejected by Gmail.") from err
            except smtplib.SMTPDataError as err:
                raise SMTPSendError(f"Gmail SMTP data error: {str(err)}") from err
            except Exception as err:
                raise SMTPSendError(f"Failed to transmit email: {str(err)}") from err

        return SendEmailResponse(
            success=True,
            message="Email sent successfully via Gmail SMTP.",
            recipient=recipient.strip(),
            message_id=message_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
