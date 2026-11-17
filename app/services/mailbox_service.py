"""Mailbox service for multi-account management, active mailbox resolution,
credential validation, encrypted persistence, and account switching.
"""

from datetime import datetime, timezone
import imaplib
import logging
import ssl
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.security import decrypt_credential, encrypt_credential
from app.models.classification_model import Classification, ClassificationHistory
from app.models.contact_model import Contact
from app.models.conversation_model import Conversation
from app.models.email_model import Email
from app.models.lead_model import Lead, LeadActivityHistory
from app.models.mailbox_model import Mailbox
from app.models.sync_model import SyncState
from app.services.imap_service import IMAPAuthenticationError, IMAPConfigurationError, IMAPConnectionError

logger = logging.getLogger("gmail_fastapi.mailbox_service")


class MailboxService:
    """Manages active mailbox lifecycle and database-scoped multi-account switching."""

    def __init__(self, db: Session, settings: Optional[Settings] = None):
        self.db = db
        self.settings = settings or get_settings()

    def get_active_mailbox(self) -> Optional[Mailbox]:
        """Fetch the currently active mailbox record from database.

        If no mailbox is currently marked active, attempts to activate the most
        recent mailbox or bootstraps from environment settings.
        """
        active = self.db.query(Mailbox).filter(Mailbox.is_active == True).first()
        if active:
            # Associate unassigned records for this active account if any
            self.db.query(SyncState).filter(
                SyncState.mailbox_id.is_(None),
                SyncState.account_email.ilike(active.email_address),
            ).update({"mailbox_id": active.id})
            self.db.query(Email).filter(
                Email.mailbox_id.is_(None),
                Email.account_email.ilike(active.email_address),
            ).update({"mailbox_id": active.id})
            self.db.commit()
            return active

        # Fallback: check if any mailbox exists
        first_mb = self.db.query(Mailbox).order_by(Mailbox.id.asc()).first()
        if first_mb:
            first_mb.is_active = True
            self.db.commit()
            self.db.refresh(first_mb)
            return first_mb

        # Fallback: bootstrap from environment settings or existing email
        email_to_use = self.settings.GMAIL_ADDRESS
        if not email_to_use:
            first_email = self.db.query(Email).first()
            if first_email and first_email.account_email:
                email_to_use = first_email.account_email

        if email_to_use:
            addr = email_to_use.strip().lower()
            enc_pwd = encrypt_credential(self.settings.clean_app_password or "")
            new_mb = Mailbox(
                email_address=addr,
                encrypted_app_password=enc_pwd,
                is_active=True,
                imap_host=self.settings.IMAP_HOST,
                imap_port=self.settings.IMAP_PORT,
                smtp_host=self.settings.SMTP_HOST,
                smtp_port=self.settings.SMTP_PORT,
            )
            self.db.add(new_mb)
            self.db.commit()
            self.db.refresh(new_mb)

            # Associate any unassigned records with this new mailbox
            self.db.query(SyncState).filter(
                SyncState.mailbox_id.is_(None),
                SyncState.account_email.ilike(addr),
            ).update({"mailbox_id": new_mb.id})
            self.db.query(Email).filter(
                Email.mailbox_id.is_(None),
            ).update({"mailbox_id": new_mb.id})
            self.db.query(Classification).filter(
                Classification.mailbox_id.is_(None),
            ).update({"mailbox_id": new_mb.id})
            self.db.query(Conversation).filter(
                Conversation.mailbox_id.is_(None),
            ).update({"mailbox_id": new_mb.id})
            self.db.commit()

            return new_mb

        return None

    def list_mailboxes(self) -> List[Mailbox]:
        """List all configured mailboxes in the database."""
        return self.db.query(Mailbox).order_by(Mailbox.id.asc()).all()

    def get_mailbox_by_id(self, mailbox_id: int) -> Optional[Mailbox]:
        """Lookup mailbox by ID."""
        return self.db.query(Mailbox).filter(Mailbox.id == mailbox_id).first()

    def get_mailbox_by_email(self, email_address: str) -> Optional[Mailbox]:
        """Lookup mailbox by email address."""
        clean_addr = email_address.strip().lower()
        return self.db.query(Mailbox).filter(Mailbox.email_address.ilike(clean_addr)).first()

    def get_mailbox_credentials(self, mailbox: Mailbox) -> Tuple[str, str]:
        """Retrieve email address and decrypted app password for a mailbox."""
        raw_pwd = decrypt_credential(mailbox.encrypted_app_password or "")
        clean_pwd = "".join(raw_pwd.split())
        return mailbox.email_address, clean_pwd

    def validate_gmail_credentials(
        self,
        email_address: str,
        app_password: str,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
    ) -> None:
        """Validate Gmail credentials by attempting SSL connection and IMAP login.

        Raises:
            IMAPConfigurationError: If input arguments are missing.
            IMAPAuthenticationError: If Gmail rejects credentials.
            IMAPConnectionError: If network/socket connection fails.
        """
        clean_email = email_address.strip()
        clean_password = "".join(app_password.split())

        if not clean_email or "@" not in clean_email:
            raise IMAPConfigurationError("Invalid Gmail email address format.")
        if not clean_password:
            raise IMAPConfigurationError("Gmail App Password cannot be empty.")

        context = ssl.create_default_context()
        try:
            client = imaplib.IMAP4_SSL(
                host=imap_host,
                port=imap_port,
                ssl_context=context,
                timeout=15,
            )
        except Exception as err:
            raise IMAPConnectionError(f"Failed to connect to IMAP server {imap_host}:{imap_port}: {str(err)}")

        try:
            res, _ = client.login(clean_email, clean_password)
            if res != "OK":
                raise IMAPAuthenticationError("Gmail authentication was rejected by the IMAP server.")
        except imaplib.IMAP4.error as err:
            raise IMAPAuthenticationError(f"Gmail IMAP authentication failed: {str(err)}")
        except Exception as err:
            raise IMAPConnectionError(f"Error during IMAP authentication handshake: {str(err)}")
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def connect_and_activate_mailbox(
        self,
        email_address: str,
        app_password: str,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        validate: bool = True,
    ) -> Tuple[Mailbox, bool]:
        """Validate, persist with encryption, and switch active mailbox.

        If validation fails, the current active mailbox is strictly preserved.
        """
        clean_addr = email_address.strip().lower()
        clean_pwd = "".join(app_password.split())

        if validate:
            self.validate_gmail_credentials(
                email_address=clean_addr,
                app_password=clean_pwd,
                imap_host=imap_host,
                imap_port=imap_port,
            )

        encrypted_pwd = encrypt_credential(clean_pwd)

        # Deactivate all mailboxes first
        self.db.query(Mailbox).update({Mailbox.is_active: False})

        # Lookup or create target mailbox
        existing = (
            self.db.query(Mailbox)
            .filter(Mailbox.email_address.ilike(clean_addr))
            .first()
        )

        is_new = False
        if existing:
            existing.encrypted_app_password = encrypted_pwd
            existing.imap_host = imap_host
            existing.imap_port = imap_port
            existing.smtp_host = smtp_host
            existing.smtp_port = smtp_port
            existing.is_active = True
            existing.updated_at = datetime.now(timezone.utc)
            target_mb = existing
        else:
            target_mb = Mailbox(
                email_address=clean_addr,
                encrypted_app_password=encrypted_pwd,
                is_active=True,
                imap_host=imap_host,
                imap_port=imap_port,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
            )
            self.db.add(target_mb)
            is_new = True

        self.db.commit()
        self.db.refresh(target_mb)

        # Ensure dedicated SyncState exists for this mailbox
        sync_state = (
            self.db.query(SyncState)
            .filter((SyncState.mailbox_id == target_mb.id) | (SyncState.account_email == clean_addr))
            .first()
        )
        if not sync_state:
            sync_state = SyncState(
                mailbox_id=target_mb.id,
                account_email=clean_addr,
                uid_validity=1,
                status="idle",
                worker_status="idle",
                total_synced=0,
                inbox_total=0,
                new_emails_last_sync=0,
            )
            self.db.add(sync_state)
            self.db.commit()
        else:
            if not sync_state.mailbox_id:
                sync_state.mailbox_id = target_mb.id
                self.db.commit()

        logger.info(
            "Mailbox activated: ID %d (%s). Previous mailboxes preserved.",
            target_mb.id,
            clean_addr,
        )
        return target_mb, is_new

    def switch_active_mailbox(self, mailbox_id: int) -> Mailbox:
        """Switch active mailbox to an existing configured mailbox ID."""
        target = self.get_mailbox_by_id(mailbox_id)
        if not target:
            raise ValueError(f"Mailbox with ID {mailbox_id} does not exist.")

        self.db.query(Mailbox).update({Mailbox.is_active: False})
        target.is_active = True
        target.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(target)

        logger.info("Switched active mailbox to ID %d (%s).", target.id, target.email_address)
        return target

    def remove_mailbox(self, mailbox_id_or_email: Any) -> Dict[str, Any]:
        """Safely and permanently remove a mailbox and all its scoped data.

        Performs scoped deletion within a database transaction:
        - Classifications & audit history
        - Scoped conversations & sync state
        - Scoped leads & activities
        - Scoped contacts (not shared with other mailboxes)
        - Scoped emails
        - Mailbox credentials & record
        - Switches active mailbox to another available mailbox or None
        """
        if isinstance(mailbox_id_or_email, int) or (isinstance(mailbox_id_or_email, str) and mailbox_id_or_email.isdigit()):
            target = self.get_mailbox_by_id(int(mailbox_id_or_email))
        else:
            target = self.get_mailbox_by_email(str(mailbox_id_or_email))

        if not target:
            raise ValueError(f"Mailbox '{mailbox_id_or_email}' not found.")

        target_id = target.id
        target_email = target.email_address
        was_active = target.is_active

        logger.info("Initiating safe removal of mailbox ID %d (%s)...", target_id, target_email)

        # 1. Collect all email IDs for this mailbox
        email_ids = [
            e[0] for e in self.db.query(Email.id).filter(
                (Email.mailbox_id == target_id) | (Email.account_email.ilike(target_email))
            ).all()
        ]
        emails_count = len(email_ids)

        # 2. Delete ClassificationHistory
        if email_ids:
            self.db.query(ClassificationHistory).filter(
                (ClassificationHistory.email_id.in_(email_ids)) | (ClassificationHistory.mailbox_id == target_id)
            ).delete(synchronize_session=False)
        else:
            self.db.query(ClassificationHistory).filter(ClassificationHistory.mailbox_id == target_id).delete(synchronize_session=False)

        # 3. Delete Classifications
        if email_ids:
            self.db.query(Classification).filter(
                (Classification.email_id.in_(email_ids)) | (Classification.mailbox_id == target_id)
            ).delete(synchronize_session=False)
        else:
            self.db.query(Classification).filter(Classification.mailbox_id == target_id).delete(synchronize_session=False)

        # 4. Delete LeadActivityHistory
        lead_ids = [
            l[0] for l in self.db.query(Lead.id).filter(Lead.mailbox_id == target_id).all()
        ]
        if lead_ids:
            self.db.query(LeadActivityHistory).filter(LeadActivityHistory.lead_id.in_(lead_ids)).delete(synchronize_session=False)

        # 5. Delete Leads
        self.db.query(Lead).filter(Lead.mailbox_id == target_id).delete(synchronize_session=False)

        # 6. Delete Conversations
        self.db.query(Conversation).filter(Conversation.mailbox_id == target_id).delete(synchronize_session=False)

        # 7. Delete Contacts strictly belonging to this mailbox that have no other mailbox references
        contacts = self.db.query(Contact).filter(Contact.mailbox_id == target_id).all()
        for cont in contacts:
            other_refs = self.db.query(Email).filter(
                Email.contact_id == cont.id,
                Email.mailbox_id != target_id,
            ).count()
            if other_refs == 0:
                self.db.delete(cont)

        # 8. Delete Emails
        self.db.query(Email).filter(
            (Email.mailbox_id == target_id) | (Email.account_email.ilike(target_email))
        ).delete(synchronize_session=False)

        # 9. Delete SyncState
        self.db.query(SyncState).filter(
            (SyncState.mailbox_id == target_id) | (SyncState.account_email.ilike(target_email))
        ).delete(synchronize_session=False)

        # 10. Delete Mailbox record
        self.db.delete(target)
        self.db.flush()

        # 11. Reconcile active mailbox if the deleted one was active
        new_active_mb = None
        if was_active:
            candidate = self.db.query(Mailbox).filter(Mailbox.id != target_id).order_by(Mailbox.id.asc()).first()
            if candidate:
                candidate.is_active = True
                candidate.updated_at = datetime.now(timezone.utc)
                new_active_mb = candidate.email_address
                logger.info("Promoted Mailbox ID %d (%s) to active.", candidate.id, candidate.email_address)

        self.db.commit()

        logger.info(
            "Successfully removed mailbox '%s' (%d emails deleted). Active mailbox is now: %s",
            target_email,
            emails_count,
            new_active_mb or "None (disconnected)",
        )
        return {
            "status": "success",
            "removed_mailbox_id": target_id,
            "removed_email": target_email,
            "emails_deleted": emails_count,
            "new_active_mailbox": new_active_mb,
        }
