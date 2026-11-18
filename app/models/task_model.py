"""SQLAlchemy model for actionable business Tasks and Follow-ups."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship as orm_relationship

from app.db.session import Base


class Task(Base):
    """Tracks a concrete follow-up task or action item on a lead or email."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    assigned_to = Column(String(255), nullable=True)  # Employee name or email
    due_date = Column(DateTime, nullable=True, index=True)

    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, completed, overdue, cancelled
    priority = Column(String(50), default="medium", nullable=False)  # high, medium, low
    who_owes_response = Column(String(50), default="company", nullable=False)  # company, customer

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_tasks_lead_status", "lead_id", "status"),
        Index("ix_tasks_mailbox_due", "mailbox_id", "due_date"),
    )

    # Relationships
    tenant = orm_relationship("Tenant", back_populates="tasks")
    mailbox = orm_relationship("Mailbox")
    lead = orm_relationship("Lead", back_populates="tasks")
    email = orm_relationship("Email", back_populates="tasks")
    contact = orm_relationship("Contact", back_populates="tasks")
