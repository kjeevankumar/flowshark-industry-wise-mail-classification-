"""IMAP Service for Gmail integration.

Implements:
- SSL connection to imap.gmail.com on port 993 with configurable timeout.
- UID-based fetching and search with mailbox UIDVALIDITY tracking.
- Read-only INBOX access (readonly=True) and BODY.PEEK[] to never alter \\Seen / unread status.
- Extraction of Gmail thread IDs (X-GM-THRID) alongside RFC 2822 Message-ID, In-Reply-To, References.
- Robust error handling without exposing credentials or internal tokens.
- Safe connection closing and logout.
"""

from contextlib import contextmanager
import imaplib
import logging
import re
import socket
from typing import Generator, List, Optional, Tuple

from app.config import Settings, get_settings
from app.schemas.email_schema import EmailDetail, EmailSummary
from app.services.email_parser import email_detail_to_summary, parse_raw_email

logger = logging.getLogger("gmail_fastapi.imap")


class IMAPServiceError(Exception):
    """Base exception for IMAP service errors."""
    pass


class IMAPConfigurationError(IMAPServiceError):
    """Raised when IMAP credentials or settings are missing/invalid."""
    pass


class IMAPAuthenticationError(IMAPServiceError):
    """Raised when authentication against the IMAP server fails."""
    pass


class IMAPConnectionError(IMAPServiceError):
    """Raised when network connection or SSL handshake fails."""
    pass


class IMAPMessageNotFoundError(IMAPServiceError):
    """Raised when a specific message UID is not found in the mailbox."""
    pass


class IMAPService:
    """Manages IMAP connection, mailbox traversal, and email retrieval."""

    def __init__(self, settings: Optional[Settings] = None):
        if settings is None or not isinstance(settings, Settings):
            self.settings = get_settings()
        else:
            self.settings = settings

    def _validate_configuration(self) -> Tuple[str, str]:
        """Validate credentials before connecting without logging sensitive values."""
        if not self.settings.GMAIL_ADDRESS or not self.settings.GMAIL_ADDRESS.strip():
            raise IMAPConfigurationError("Gmail address is not configured. Please set GMAIL_ADDRESS in .env.")
        clean_pwd = self.settings.clean_app_password
        if not clean_pwd:
            raise IMAPConfigurationError("Gmail App Password is not configured. Please set GMAIL_APP_PASSWORD in .env.")
        return self.settings.GMAIL_ADDRESS.strip(), clean_pwd

    @contextmanager
    def get_client(self) -> Generator[imaplib.IMAP4_SSL, None, None]:
        """Context manager establishing a secure IMAP connection with timeout and safe cleanup."""
        username, password = self._validate_configuration()
        client: Optional[imaplib.IMAP4_SSL] = None

        try:
            # Connect with SSL and configured socket timeout
            client = imaplib.IMAP4_SSL(
                host=self.settings.IMAP_HOST,
                port=self.settings.IMAP_PORT,
                timeout=self.settings.IMAP_TIMEOUT_SECONDS,
            )
        except (socket.timeout, TimeoutError) as err:
            logger.error("IMAP connection timed out connecting to %s:%s", self.settings.IMAP_HOST, self.settings.IMAP_PORT)
            raise IMAPConnectionError(f"Connection to IMAP server {self.settings.IMAP_HOST}:{self.settings.IMAP_PORT} timed out.") from err
        except (socket.gaierror, ConnectionRefusedError, OSError) as err:
            logger.error("IMAP connection failed: %s", str(err))
            raise IMAPConnectionError(f"Failed to connect to IMAP server: {str(err)}") from err

        try:
            # Authenticate using Gmail address and App Password
            client.login(username, password)
        except imaplib.IMAP4.error as err:
            # Sanitize error to prevent credential reflection
            err_msg = str(err)
            logger.warning("IMAP authentication failed for account %s", self.settings.masked_gmail_address)
            raise IMAPAuthenticationError("IMAP authentication failed. Please verify your Gmail address and 16-character App Password.") from err

        try:
            yield client
        finally:
            if client:
                try:
                    # Attempt to close active mailbox if open
                    client.close()
                except Exception:
                    pass
                try:
                    # Always log out to release the IMAP session cleanly
                    client.logout()
                except Exception:
                    pass

    def extract_uid_validity(self, client: imaplib.IMAP4_SSL, mailbox: str = "INBOX") -> Optional[int]:
        """Extract the UIDVALIDITY integer of the specified mailbox."""
        try:
            # Query STATUS for UIDVALIDITY
            status, res = client.status(mailbox, "(UIDVALIDITY)")
            if status == "OK" and res and res[0]:
                match = re.search(r"UIDVALIDITY\s+(\d+)", res[0].decode("utf-8", errors="ignore"))
                if match:
                    return int(match.group(1))

            # Fallback: check client.response('UIDVALIDITY')
            val = client.response("UIDVALIDITY")
            if val and val[1] and val[1][0]:
                return int(val[1][0].decode("utf-8", errors="ignore"))
        except Exception as err:
            logger.debug("Could not parse UIDVALIDITY: %s", str(err))
        return None

    def test_connection(self, mailbox: str = "INBOX") -> dict:
        """Test IMAP authentication and read-only inbox access without modifying state."""
        with self.get_client() as client:
            # Select INBOX in strictly read-only mode
            res, data = client.select(mailbox, readonly=True)
            if res != "OK":
                raise IMAPConnectionError(f"Failed to access mailbox '{mailbox}'. Response: {data}")

            total_messages = 0
            if data and data[0]:
                try:
                    total_messages = int(data[0].decode("utf-8", errors="ignore"))
                except ValueError:
                    total_messages = 0

            uid_validity = self.extract_uid_validity(client, mailbox)

            return {
                "success": True,
                "message": f"Successfully authenticated and accessed '{mailbox}' in read-only mode.",
                "inbox_total_messages": total_messages,
                "uid_validity": uid_validity,
            }

    def fetch_inbox_emails(
        self,
        mailbox: str = "INBOX",
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[List[EmailSummary], int, Optional[int]]:
        """Fetch latest emails using UID search and BODY.PEEK[] to preserve unread state.

        Returns:
            Tuple of (list_of_summaries, total_count, uid_validity)
        """
        if limit < 1:
            limit = 10
        if limit > 50:
            limit = 50
        if offset < 0:
            offset = 0

        with self.get_client() as client:
            res, _ = client.select(mailbox, readonly=True)
            if res != "OK":
                raise IMAPConnectionError(f"Failed to select mailbox '{mailbox}'")

            uid_validity = self.extract_uid_validity(client, mailbox)

            # Search all UIDs in the mailbox
            res, search_data = client.uid("search", None, "ALL")
            if res != "OK" or not search_data or not search_data[0]:
                return [], 0, uid_validity

            # Parse UIDs as integers and sort descending (newest first)
            raw_uids = search_data[0].split()
            valid_uids: List[int] = []
            for item in raw_uids:
                try:
                    valid_uids.append(int(item))
                except ValueError:
                    continue

            valid_uids.sort(reverse=True)
            total_count = len(valid_uids)

            # Apply pagination
            page_uids = valid_uids[offset : offset + limit]
            if not page_uids:
                return [], total_count, uid_validity

            summaries: List[EmailSummary] = []
            for uid_val in page_uids:
                try:
                    detail = self._fetch_single_uid(client, str(uid_val), uid_validity, mailbox)
                    summaries.append(email_detail_to_summary(detail))
                except Exception as err:
                    logger.warning("Failed to parse message UID %s: %s", uid_val, str(err))

            return summaries, total_count, uid_validity

    def get_email_by_uid(self, uid: str, mailbox: str = "INBOX") -> EmailDetail:
        """Fetch full email detail by permanent IMAP UID."""
        with self.get_client() as client:
            res, _ = client.select(mailbox, readonly=True)
            if res != "OK":
                raise IMAPConnectionError(f"Failed to select mailbox '{mailbox}'")

            uid_validity = self.extract_uid_validity(client, mailbox)
            return self._fetch_single_uid(client, uid, uid_validity, mailbox)

    def _fetch_single_uid(
        self,
        client: imaplib.IMAP4_SSL,
        uid: str,
        uid_validity: Optional[int],
        mailbox: str,
    ) -> EmailDetail:
        """Internal helper to fetch RFC 822 data and Gmail thread metadata for a single UID."""
        # Attempt to fetch with Gmail extension X-GM-THRID alongside BODY.PEEK[]
        fetch_cmd = "(BODY.PEEK[] X-GM-THRID)"
        res, fetch_data = client.uid("fetch", uid, fetch_cmd)

        if res != "OK" or not fetch_data or fetch_data[0] is None:
            # Fallback to standard RFC fetch if Gmail extension failed
            res, fetch_data = client.uid("fetch", uid, "(BODY.PEEK[])")
            if res != "OK" or not fetch_data or fetch_data[0] is None:
                raise IMAPMessageNotFoundError(f"Message with UID '{uid}' was not found in mailbox '{mailbox}'.")

        raw_email_bytes: Optional[bytes] = None
        thread_id: Optional[str] = None

        for item in fetch_data:
            if isinstance(item, tuple):
                header_info = item[0]
                if isinstance(header_info, bytes):
                    header_str = header_info.decode("utf-8", errors="ignore")
                    # Extract X-GM-THRID if present
                    thrid_match = re.search(r"X-GM-THRID\s+(\d+)", header_str)
                    if thrid_match:
                        thread_id = thrid_match.group(1)

                raw_email_bytes = item[1]
                break

        if not raw_email_bytes:
            raise IMAPMessageNotFoundError(f"Empty content received for message UID '{uid}'")

        return parse_raw_email(
            raw_content=raw_email_bytes,
            uid=uid,
            uid_validity=uid_validity,
            mailbox=mailbox,
            thread_id=thread_id,
        )
