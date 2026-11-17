"""SQLAlchemy model for connected Gmail mailboxes."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship as orm_relationship

from app.db.session import Base


class Mailbox(Base):
    """Represents a configured Gmail mailbox account.

    Tracks active status, encrypted credentials, connection endpoints, and relationships.
    """

    __tablename__ = "mailboxes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email_address = Column(String(255), unique=True, nullable=False, index=True)
    encrypted_app_password = Column(Text, nullable=True)  # Fernet encrypted at rest
    is_active = Column(Boolean, default=False, nullable=False, index=True)

    imap_host = Column(String(255), default="imap.gmail.com", nullable=False)
    imap_port = Column(Integer, default=993, nullable=False)
    smtp_host = Column(String(255), default="smtp.gmail.com", nullable=False)
    smtp_port = Column(Integer, default=587, nullable=False)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Scoped Relationships
    emails = orm_relationship("Email", back_populates="mailbox", cascade="all, delete-orphan")
    conversations = orm_relationship("Conversation", back_populates="mailbox", cascade="all, delete-orphan")
    classifications = orm_relationship("Classification", back_populates="mailbox", cascade="all, delete-orphan")
    sync_state = orm_relationship("SyncState", back_populates="mailbox", uselist=False, cascade="all, delete-orphan")
    contacts = orm_relationship("Contact", back_populates="mailbox", cascade="all, delete-orphan")
    leads = orm_relationship("Lead", back_populates="mailbox", cascade="all, delete-orphan")

