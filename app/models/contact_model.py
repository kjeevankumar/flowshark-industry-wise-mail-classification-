"""SQLAlchemy model for contacts and relationship memory."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship as orm_relationship

from app.db.session import Base


class Contact(Base):
    """Stores business contacts, relationship memory, and current pipeline state."""

    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=True, index=True)

    email_address = Column(String(255), nullable=False, index=True)  # Normalized lowercase
    name = Column(String(255), nullable=True)
    company_name = Column(String(255), nullable=True)

    relationship_type = Column(String(50), default="unknown", nullable=False)  # new_contact, existing_lead, existing_customer, unknown
    current_lead_stage = Column(String(50), default="unknown", nullable=False)  # new, qualified, proposal_sent, negotiation, won, lost, unknown
    business_context = Column(Text, nullable=True)
    industry = Column(String(100), default="Unknown", nullable=True)
    sub_industry = Column(String(100), nullable=True)
    last_interaction_at = Column(DateTime, nullable=True, index=True)

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
        UniqueConstraint("mailbox_id", "email_address", name="uq_contact_mailbox_email"),
        Index("ix_contacts_mailbox_email", "mailbox_id", "email_address"),
        Index("ix_contacts_relationship", "mailbox_id", "relationship_type"),
    )

    # Relationships
    mailbox = orm_relationship("Mailbox", back_populates="contacts")
    leads = orm_relationship("Lead", back_populates="contact", cascade="all, delete-orphan", order_by="desc(Lead.updated_at)")
    emails = orm_relationship("Email", back_populates="contact")
    conversations = orm_relationship("Conversation", back_populates="contact")
