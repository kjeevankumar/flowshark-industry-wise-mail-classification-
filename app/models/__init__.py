"""Database models package."""

from app.models.mailbox_model import Mailbox
from app.models.classification_model import Classification, ClassificationHistory
from app.models.conversation_model import Conversation
from app.models.email_model import Email
from app.models.sync_model import SyncState
from app.models.contact_model import Contact
from app.models.lead_model import Lead, LeadActivityHistory

__all__ = [
    "Mailbox",
    "Classification",
    "ClassificationHistory",
    "Conversation",
    "Email",
    "SyncState",
    "Contact",
    "Lead",
    "LeadActivityHistory",
]

