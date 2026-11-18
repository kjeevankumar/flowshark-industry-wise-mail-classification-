"""SQLAlchemy model for external customer Organizations / Companies."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship as orm_relationship

from app.db.session import Base


class Organization(Base):
    """Represents an external client company or prospective business account."""

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), nullable=True, index=True)  # e.g., "apexlogistics.com"
    industry = Column(String(100), default="Unknown", nullable=False, index=True)
    sub_industry = Column(String(100), nullable=True)
    business_activity = Column(Text, nullable=True)

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
        Index("ix_org_tenant_name", "tenant_id", "name"),
        Index("ix_org_tenant_domain", "tenant_id", "domain"),
    )

    # Relationships
    tenant = orm_relationship("Tenant", back_populates="organizations")
    contacts = orm_relationship("Contact", back_populates="organization")
    leads = orm_relationship("Lead", back_populates="organization")
    emails = orm_relationship("Email", back_populates="organization")
