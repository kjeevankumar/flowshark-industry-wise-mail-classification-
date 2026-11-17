"""SQLAlchemy model for grouped conversation threads."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship as orm_relationship

from app.db.session import Base


class Conversation(Base):
    """Tracks conversation-level thread state, history, and lead stage progression."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    gmail_thread_id = Column(String(64), nullable=False, index=True)
    primary_contact = Column(String(255), nullable=True, index=True)
    subject = Column(String(1000), nullable=True)
    message_count = Column(Integer, default=1, nullable=False)
    last_message_at = Column(DateTime, nullable=True, index=True)
    relationship = Column(String(50), default="unknown", nullable=False)  # new_contact, existing_lead, existing_customer
    current_lead_stage = Column(String(50), default="unknown", nullable=False)  # new, qualified, proposal_sent, negotiation, won, lost
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

    __table_args__ = (
        Index("ix_conversations_mailbox_thread", "mailbox_id", "gmail_thread_id"),
        Index("ix_conversations_mailbox_last_msg", "mailbox_id", "last_message_at"),
    )

    mailbox = orm_relationship("Mailbox", back_populates="conversations")
    contact = orm_relationship("Contact", back_populates="conversations")
    lead = orm_relationship("Lead", back_populates="conversations")

