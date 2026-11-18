"""SQLAlchemy model for Tenants (Companies) in FlowShark B2B SaaS."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship as orm_relationship

from app.db.session import Base


class Tenant(Base):
    """Represents a customer company subscribing to FlowShark."""

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)

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

    # Relationships
    mailboxes = orm_relationship("Mailbox", back_populates="tenant", cascade="all, delete-orphan")
    organizations = orm_relationship("Organization", back_populates="tenant", cascade="all, delete-orphan")
    contacts = orm_relationship("Contact", back_populates="tenant", cascade="all, delete-orphan")
    leads = orm_relationship("Lead", back_populates="tenant", cascade="all, delete-orphan")
    emails = orm_relationship("Email", back_populates="tenant", cascade="all, delete-orphan")
    tasks = orm_relationship("Task", back_populates="tenant", cascade="all, delete-orphan")
    commercial_events = orm_relationship("CommercialEvent", back_populates="tenant", cascade="all, delete-orphan")
