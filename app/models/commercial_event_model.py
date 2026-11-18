"""SQLAlchemy model for Commercial Events (Purchase Orders, Invoices, Payments)."""

from datetime import datetime, timezone
from sqlalchemy import (
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


class CommercialEvent(Base):
    """Tracks verifiable commercial transactions and events associated with emails and opportunities."""

    __tablename__ = "commercial_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)

    # Event taxonomy:
    # po_received, invoice_requested, invoice_update_requested,
    # payment_remittance_received, payment_followup_received, payment_dispute_raised, invoice_issued
    event_type = Column(String(100), nullable=False, index=True)

    amount = Column(Float, nullable=True)
    currency = Column(String(10), default="USD", nullable=True)
    reference_number = Column(String(255), nullable=True, index=True)  # PO Number, UTR Number, Invoice Number
    event_date = Column(DateTime, nullable=True)

    status = Column(String(50), default="recorded", nullable=False)  # recorded, pending_verification, task_created, resolved
    notes = Column(Text, nullable=True)
    raw_details = Column(JSON, nullable=True)  # items, payment_terms, dispute_reason, tax_info

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
        Index("ix_commercial_events_mailbox_type", "mailbox_id", "event_type"),
        Index("ix_commercial_events_lead", "lead_id", "created_at"),
    )

    # ORM Relationships
    tenant = orm_relationship("Tenant", back_populates="commercial_events")
    mailbox = orm_relationship("Mailbox")
    email = orm_relationship("Email", back_populates="commercial_events")
    lead = orm_relationship("Lead", back_populates="commercial_events")
    contact = orm_relationship("Contact")
