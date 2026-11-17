"""SQLAlchemy model for tracking synchronization state per account."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class SyncState(Base):
    """Tracks incremental synchronization progress for a Gmail mailbox."""

    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=True, unique=True, index=True)
    account_email = Column(String(255), unique=True, nullable=False, index=True)
    uid_validity = Column(Integer, nullable=False, default=1)
    last_synced_uid = Column(String(64), nullable=True)
    highest_synced_uid = Column(String(64), nullable=True)
    total_synced = Column(Integer, default=0, nullable=False)
    inbox_total = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="idle", nullable=False)  # idle, syncing, completed, failed
    worker_status = Column(String(50), default="stopped", nullable=False)  # stopped, running, idle, syncing, error
    last_synced_at = Column(DateTime, nullable=True)
    new_emails_last_sync = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)

    mailbox = relationship("Mailbox", back_populates="sync_state")

