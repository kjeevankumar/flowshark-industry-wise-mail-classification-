"""SQLAlchemy model for AI email classifications and correction history."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship as orm_relationship

from app.db.session import Base


class Classification(Base):
    """Stores the multi-dimensional classification results for an email."""

    __tablename__ = "classifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)

    # Multi-dimensional classification fields
    relationship = Column(String(50), nullable=False)  # new_contact, existing_lead, existing_customer, unknown
    intent = Column(String(50), nullable=False)        # new_enquiry, negotiation, follow_up, business_clarification, purchase_order, invoice, complaint, other
    lead_stage = Column(String(50), nullable=False)    # new, qualified, proposal_sent, negotiation, won, lost, unknown

    confidence = Column(Float, nullable=False, default=0.0)
    classification_reason = Column(Text, nullable=True)
    key_signals = Column(JSON, nullable=True)  # List of string signals
    context_used = Column(Text, nullable=True)
    suggested_next_action = Column(Text, nullable=True)

    # Industry Classification Dimensions
    sender_industry = Column(String(100), default="Unknown", nullable=False, index=True)
    target_industry = Column(String(100), default="Unknown", nullable=False, index=True)
    sub_industry = Column(String(100), nullable=True)
    business_activity = Column(Text, nullable=True)
    industry_confidence = Column(Float, default=0.0, nullable=False)
    industry_reason = Column(Text, nullable=True)
    industry_evidence = Column(JSON, nullable=True)  # List of string signals/evidence
    industry_requires_review = Column(Boolean, default=False, nullable=False, index=True)

    classification_method = Column(String(50), nullable=False, default="hybrid")  # hybrid, llm, rule_based, manual_correction
    requires_human_review = Column(Boolean, default=False, nullable=False, index=True)
    model_provider = Column(String(50), nullable=True)  # gemini, openai, fallback
    model_name = Column(String(100), nullable=True)

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
        Index("ix_classifications_mailbox_intent", "mailbox_id", "intent"),
        Index("ix_classifications_mailbox_relationship", "mailbox_id", "relationship"),
        Index("ix_classifications_mailbox_review", "mailbox_id", "requires_human_review"),
        Index("ix_classifications_mailbox_target_ind", "mailbox_id", "target_industry"),
        Index("ix_classifications_mailbox_sender_ind", "mailbox_id", "sender_industry"),
    )

    # ORM Relationships
    mailbox = orm_relationship("Mailbox", back_populates="classifications")
    email = orm_relationship("Email", back_populates="classification")
    contact = orm_relationship("Contact")
    lead = orm_relationship("Lead")
    history = orm_relationship(
        "ClassificationHistory",
        back_populates="classification",
        cascade="all, delete-orphan",
        order_by="desc(ClassificationHistory.corrected_at)",
    )


class ClassificationHistory(Base):
    """Audit trail of human corrections to email classifications."""

    __tablename__ = "classification_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"), nullable=True, index=True)
    classification_id = Column(Integer, ForeignKey("classifications.id", ondelete="CASCADE"), nullable=False, index=True)

    previous_values = Column(JSON, nullable=False)
    corrected_values = Column(JSON, nullable=False)
    notes = Column(Text, nullable=True)
    corrected_by = Column(String(100), default="user", nullable=False)
    corrected_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    classification = orm_relationship("Classification", back_populates="history")
