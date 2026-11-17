"""SQLAlchemy models for business leads and lead lifecycle activity history."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship as orm_relationship

from app.db.session import Base


class Lead(Base):
    """Tracks a single business opportunity lifecycle with associated emails."""

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String(500), nullable=False)
    status = Column(String(50), default="new", nullable=False)  # new, qualified, proposal_sent, negotiation, won, lost
    estimated_value = Column(Float, nullable=True)
    business_context = Column(Text, nullable=True)
    source = Column(String(100), default="email", nullable=False)
    target_industry = Column(String(100), default="Unknown", nullable=True)
    sub_industry = Column(String(100), nullable=True)

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
    closed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_leads_mailbox_status", "mailbox_id", "status"),
        Index("ix_leads_contact_status", "contact_id", "status"),
    )

    # Relationships
    mailbox = orm_relationship("Mailbox", back_populates="leads")
    contact = orm_relationship("Contact", back_populates="leads")
    emails = orm_relationship("Email", back_populates="lead")
    conversations = orm_relationship("Conversation", back_populates="lead")
    activities = orm_relationship(
        "LeadActivityHistory",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="desc(LeadActivityHistory.created_at)",
    )


class LeadActivityHistory(Base):
    """Auditable log of lead lifecycle events and stage transitions."""

    __tablename__ = "lead_activities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="SET NULL"), nullable=True, index=True)

    activity_type = Column(String(100), nullable=False)  # email_classified, stage_transition, manual_correction, relationship_update
    from_stage = Column(String(50), nullable=True)
    to_stage = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_lead_activities_lead", "lead_id", "created_at"),
    )

    lead = orm_relationship("Lead", back_populates="activities")
