"""Email synchronization service for Gmail via IMAP with full Mailbox scoping.

Handles:
- Safe, non-destructive incremental mailbox synchronization with batch limits.
- Mailbox UIDVALIDITY change detection and recovery.
- Scoped deduplication using (mailbox_id, uid_validity, imap_uid).
- Conversation thread grouping scoped to the active mailbox.
- Immediate hybrid AI classification after storage with mailbox isolation.
- Strict error isolation: classification errors never rollback email storage.
- Mailbox-scoped sync progress tracking in SyncState table.
"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import time
from typing import List, NamedTuple, Optional, Set
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.classification_model import Classification
from app.models.conversation_model import Conversation
from app.models.email_model import Email
from app.models.mailbox_model import Mailbox
from app.models.sync_model import SyncState
from app.services.hybrid_classifier import HybridClassifier
from app.services.imap_service import IMAPService, IMAPServiceError
from app.services.mailbox_service import MailboxService

logger = logging.getLogger("gmail_fastapi.sync")


class SyncResult(NamedTuple):
    """Result summary of a synchronization run."""
    new_emails_synced: int
    total_inbox_messages: int
    total_synced_in_db: int
    uid_validity: int
    status: str
    duration_seconds: float
    message: str


class EmailSyncService:
    """Manages incremental synchronization of Gmail inbox messages into the local database."""

    def __init__(
        self,
        db: Session,
        settings: Optional[Settings] = None,
        mailbox: Optional[Mailbox] = None,
    ):
        self.db = db
        self.settings = settings or get_settings()
        self.mailbox_service = MailboxService(db=self.db, settings=self.settings)

        # Resolve mailbox
        self.mailbox = mailbox or self.mailbox_service.get_active_mailbox()

        if self.mailbox:
            email_addr, clean_pwd = self.mailbox_service.get_mailbox_credentials(self.mailbox)
            scoped_settings = self.settings.model_copy(
                update={
                    "GMAIL_ADDRESS": email_addr,
                    "GMAIL_APP_PASSWORD": SecretStr(clean_pwd) if clean_pwd else None,
                    "IMAP_HOST": self.mailbox.imap_host,
                    "IMAP_PORT": self.mailbox.imap_port,
                    "SMTP_HOST": self.mailbox.smtp_host,
                    "SMTP_PORT": self.mailbox.smtp_port,
                }
            )
            self.imap_service = IMAPService(settings=scoped_settings)
            self.account_email = email_addr
            self.mailbox_id = self.mailbox.id
        else:
            self.imap_service = IMAPService(settings=self.settings)
            self.account_email = self.settings.GMAIL_ADDRESS or "unknown"
            self.mailbox_id = None

    def get_or_create_sync_state(self) -> SyncState:
        """Fetch or initialize the SyncState record for this mailbox."""
        state = None
        if self.mailbox_id:
            state = (
                self.db.query(SyncState)
                .filter(SyncState.mailbox_id == self.mailbox_id)
                .first()
            )
        if not state:
            state = (
                self.db.query(SyncState)
                .filter(SyncState.account_email.ilike(self.account_email))
                .first()
            )

        if not state:
            state = SyncState(
                mailbox_id=self.mailbox_id,
                account_email=self.account_email,
                uid_validity=1,
                status="idle",
                worker_status="idle",
                total_synced=0,
                inbox_total=0,
                new_emails_last_sync=0,
            )
            self.db.add(state)
            self.db.commit()
            self.db.refresh(state)
        elif self.mailbox_id and not state.mailbox_id:
            state.mailbox_id = self.mailbox_id
            self.db.commit()

        return state

    def sync_inbox(self, batch_size: int = 50) -> SyncResult:
        """Run incremental synchronization of recent messages from INBOX.

        Args:
            batch_size: Maximum new messages to fetch and insert in this run (1 to 100).
        """
        start_time = time.time()
        sync_state = self.get_or_create_sync_state()

        # Enforce batch bounds
        batch_size = max(1, min(batch_size, 100))

        sync_state.status = "syncing"
        self.db.commit()

        try:
            with self.imap_service.get_client() as client:
                # Open strictly in read-only mode
                res, data = client.select("INBOX", readonly=True)
                if res != "OK":
                    raise IMAPServiceError(f"Failed to access INBOX: {data}")

                total_inbox_messages = int(data[0].decode("utf-8", errors="ignore")) if data and data[0] else 0
                uid_validity = self.imap_service.extract_uid_validity(client, "INBOX") or 1

                # Check for UIDVALIDITY invalidation
                if sync_state.highest_synced_uid is not None and sync_state.uid_validity != uid_validity:
                    logger.warning(
                        "Mailbox UIDVALIDITY changed from %s to %s for account %s (Mailbox ID %s). Resetting sync pointer.",
                        sync_state.uid_validity,
                        uid_validity,
                        self.account_email,
                        self.mailbox_id,
                    )
                    sync_state.uid_validity = uid_validity
                    sync_state.last_synced_uid = None
                    sync_state.highest_synced_uid = None
                    self.db.commit()
                elif sync_state.uid_validity != uid_validity:
                    sync_state.uid_validity = uid_validity
                    self.db.commit()

                # Determine candidate UIDs
                candidate_uids: List[int] = []
                last_uid_int = None
                if sync_state.highest_synced_uid:
                    try:
                        last_uid_int = int(sync_state.highest_synced_uid)
                    except ValueError:
                        last_uid_int = None

                if last_uid_int is not None and last_uid_int > 0:
                    # Incremental search: fetch UIDs starting after last_uid_int
                    search_cmd = f"UID {last_uid_int + 1}:*"
                    res, search_data = client.uid("search", None, search_cmd)
                    if res == "OK" and search_data and search_data[0]:
                        raw_uids = search_data[0].split()
                        for item in raw_uids:
                            try:
                                u_int = int(item)
                                # Filter strictly greater than last_uid_int
                                if u_int > last_uid_int:
                                    candidate_uids.append(u_int)
                            except ValueError:
                                continue
                else:
                    # Initial search: search ALL and filter against DB
                    res, search_data = client.uid("search", None, "ALL")
                    if res == "OK" and search_data and search_data[0]:
                        raw_uids = search_data[0].split()
                        all_uids: List[int] = []
                        for item in raw_uids:
                            try:
                                all_uids.append(int(item))
                            except ValueError:
                                continue

                        # Query existing UIDs already in DB for this mailbox
                        query = self.db.query(Email.imap_uid).filter(Email.uid_validity == uid_validity)
                        if self.mailbox_id:
                            query = query.filter(
                                (Email.mailbox_id == self.mailbox_id)
                                | (Email.mailbox_id.is_(None) & (Email.account_email == self.account_email))
                            )
                        else:
                            query = query.filter(Email.account_email == self.account_email)

                        existing_uids: Set[str] = {t[0] for t in query.all()}
                        candidate_uids = [u for u in all_uids if str(u) not in existing_uids]

                # Sort ascending so we process and store chronologically (oldest-new to newest)
                candidate_uids.sort()

                # Limit to requested batch_size
                if len(candidate_uids) > batch_size:
                    candidate_uids = candidate_uids[-batch_size:]

                newly_synced_count = 0
                highest_committed_uid = last_uid_int or 0
                classifier = HybridClassifier(db=self.db, settings=self.settings)

                for uid_num in candidate_uids:
                    uid_str = str(uid_num)

                    # Deduplication check in DB scoped to mailbox
                    dedup_q = self.db.query(Email).filter(
                        Email.uid_validity == uid_validity,
                        Email.imap_uid == uid_str,
                    )
                    if self.mailbox_id:
                        dedup_q = dedup_q.filter(
                            (Email.mailbox_id == self.mailbox_id)
                            | (Email.mailbox_id.is_(None) & (Email.account_email == self.account_email))
                        )
                    else:
                        dedup_q = dedup_q.filter(Email.account_email == self.account_email)

                    if dedup_q.first():
                        if uid_num > highest_committed_uid:
                            highest_committed_uid = uid_num
                        continue

                    try:
                        # Fetch email using BODY.PEEK[]
                        detail = self.imap_service._fetch_single_uid(
                            client=client,
                            uid=uid_str,
                            uid_validity=uid_validity,
                            mailbox="INBOX",
                        )

                        # Parse received date
                        parsed_date = None
                        if detail.date:
                            try:
                                parsed_date = parsedate_to_datetime(detail.date)
                            except Exception:
                                parsed_date = datetime.now(timezone.utc)

                        email_row = Email(
                            mailbox_id=self.mailbox_id,
                            account_email=self.account_email,
                            imap_uid=uid_str,
                            uid_validity=uid_validity,
                            message_id=detail.message_id,
                            gmail_thread_id=detail.thread_id,
                            in_reply_to=detail.in_reply_to,
                            references_header=detail.references,
                            sender=detail.sender,
                            recipient=detail.recipient,
                            subject=detail.subject,
                            snippet=detail.snippet,
                            body_text=detail.body_plain,
                            body_html=detail.body_html,
                            received_at=parsed_date,
                            has_attachments=detail.has_attachments,
                            attachment_count=len(detail.attachments),
                        )
                        self.db.add(email_row)

                        # Update conversation thread record scoped to mailbox
                        thread_id = detail.thread_id or f"msg_{uid_str}"
                        conv_q = self.db.query(Conversation).filter(Conversation.gmail_thread_id == thread_id)
                        if self.mailbox_id:
                            conv_q = conv_q.filter(Conversation.mailbox_id == self.mailbox_id)
                        conv = conv_q.first()

                        if not conv:
                            conv = Conversation(
                                mailbox_id=self.mailbox_id,
                                gmail_thread_id=thread_id,
                                primary_contact=detail.sender,
                                subject=detail.subject,
                                message_count=1,
                                last_message_at=parsed_date,
                                relationship="unknown",
                                current_lead_stage="unknown",
                            )
                            self.db.add(conv)
                        else:
                            conv.message_count += 1
                            if parsed_date and (not conv.last_message_at or parsed_date > conv.last_message_at):
                                conv.last_message_at = parsed_date

                        # Commit the email to database BEFORE classification
                        self.db.commit()
                        self.db.refresh(email_row)

                        # Immediate Hybrid AI Classification
                        try:
                            classifier.classify_email(email_row)
                            self.db.commit()
                        except Exception as class_err:
                            logger.warning(
                                "Classification failed for email ID %s (UID %s): %s",
                                email_row.id,
                                uid_str,
                                str(class_err),
                            )
                            # Fallback classification record so email is categorized in Needs Review
                            try:
                                existing_class = (
                                    self.db.query(Classification)
                                    .filter(Classification.email_id == email_row.id)
                                    .first()
                                )
                                if not existing_class:
                                    fallback_class = Classification(
                                        mailbox_id=self.mailbox_id,
                                        email_id=email_row.id,
                                        relationship="unknown",
                                        intent="other",
                                        lead_stage="unknown",
                                        confidence=0.30,
                                        classification_reason=f"Classification deferred due to service error: {str(class_err)}",
                                        key_signals=[],
                                        suggested_next_action="Manual review required",
                                        sender_industry="Unknown",
                                        target_industry="Unknown",
                                        sub_industry=None,
                                        business_activity=None,
                                        industry_confidence=0.0,
                                        industry_reason="Classification deferred due to service error.",
                                        industry_evidence=[],
                                        industry_requires_review=True,
                                        classification_method="fallback_error",
                                        requires_human_review=True,
                                        model_provider="fallback",
                                        model_name="error-fallback",
                                    )
                                    self.db.add(fallback_class)
                                    self.db.commit()
                            except Exception:
                                self.db.rollback()

                        newly_synced_count += 1
                        if uid_num > highest_committed_uid:
                            highest_committed_uid = uid_num

                    except Exception as msg_err:
                        self.db.rollback()
                        logger.warning("Failed to sync message UID %s: %s", uid_str, str(msg_err))

                # Update sync state only after successful database commits
                count_q = self.db.query(Email)
                if self.mailbox_id:
                    count_q = count_q.filter(Email.mailbox_id == self.mailbox_id)
                else:
                    count_q = count_q.filter(Email.account_email == self.account_email)
                total_in_db = count_q.count()

                duration = time.time() - start_time

                sync_state.status = "completed"
                sync_state.last_synced_at = datetime.now(timezone.utc)
                sync_state.inbox_total = total_inbox_messages
                sync_state.total_synced = total_in_db
                if highest_committed_uid > 0:
                    sync_state.highest_synced_uid = str(highest_committed_uid)
                    sync_state.last_synced_uid = str(highest_committed_uid)
                sync_state.new_emails_last_sync = newly_synced_count
                sync_state.error_message = None
                self.db.commit()

                return SyncResult(
                    new_emails_synced=newly_synced_count,
                    total_inbox_messages=total_inbox_messages,
                    total_synced_in_db=total_in_db,
                    uid_validity=uid_validity,
                    status="completed",
                    duration_seconds=round(duration, 2),
                    message=f"Successfully synced {newly_synced_count} emails for {self.account_email}. Total in database: {total_in_db}.",
                )

        except Exception as err:
            sync_state.status = "failed"
            sync_state.error_message = str(err)
            self.db.commit()
            logger.error("Inbox sync failed for mailbox %s: %s", self.account_email, str(err))
            raise
