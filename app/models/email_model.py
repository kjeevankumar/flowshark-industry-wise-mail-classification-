"""SQLAlchemy model for synchronized email records."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class Email(Base):
    """Stores full details of synchronized emails from Gmail."""

    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    account_email = Column(String(255), nullable=False, index=True)
    imap_uid = Column(String(64), nullable=False, index=True)
    uid_validity = Column(Integer, nullable=False, default=1)
    message_id = Column(String(500), nullable=True, index=True)
    gmail_thread_id = Column(String(64), nullable=True, index=True)
    in_reply_to = Column(String(500), nullable=True)
    references_header = Column(Text, nullable=True)
    sender = Column(String(500), nullable=False)
    recipient = Column(String(500), nullable=True)
    cc = Column(String(500), nullable=True)
    bcc = Column(String(500), nullable=True)
    subject = Column(String(1000), nullable=False, default="(No Subject)")
    snippet = Column(String(1000), nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    received_at = Column(DateTime, nullable=True, index=True)
    has_attachments = Column(Boolean, default=False, nullable=False)
    attachment_count = Column(Integer, default=0, nullable=False)
    sync_timestamp = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Scoped indexes & Unique constraint
    __table_args__ = (
        UniqueConstraint("account_email", "uid_validity", "imap_uid", name="uq_email_account_uid_validity"),
        Index("ix_emails_mailbox_received_at", "mailbox_id", "received_at"),
        Index("ix_emails_mailbox_imap_uid", "mailbox_id", "imap_uid"),
        Index("ix_emails_mailbox_thread", "mailbox_id", "gmail_thread_id"),
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="emails")
    organization = relationship("Organization", back_populates="emails")
    mailbox = relationship("Mailbox", back_populates="emails")
    contact = relationship("Contact", back_populates="emails")
    lead = relationship("Lead", back_populates="emails")
    tasks = relationship("Task", back_populates="email", cascade="all, delete-orphan")
    classification = relationship(
        "Classification",
        back_populates="email",
        uselist=False,
        cascade="all, delete-orphan",
    )

