"""Pydantic schemas for Email Inbox, Classification, and Dashboard APIs."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ClassificationCorrectionRequest(BaseModel):
    """Payload to record a human correction to an email classification."""
    relevance_category: Optional[str] = Field(None, examples=["business_enquiry"])
    is_business_relevant: Optional[bool] = Field(None, examples=[True])
    pipeline_category: Optional[str] = Field(None, examples=["new_leads"])
    relationship: Optional[str] = Field(None, examples=["existing_lead"])
    intent: Optional[str] = Field(None, examples=["negotiation"])
    lead_stage: Optional[str] = Field(None, examples=["negotiation"])
    sender_industry: Optional[str] = Field(None, examples=["IT & Software"])
    target_industry: Optional[str] = Field(None, examples=["Healthcare"])
    sub_industry: Optional[str] = Field(None, examples=["Healthcare Technology"])
    notes: Optional[str] = Field(None, examples=["Customer asked for a 15% discount."])


class IndustryCorrectionRequest(BaseModel):
    """Payload to record a human correction specifically to industry classification."""
    sender_industry: Optional[str] = Field(None, examples=["IT & Software"])
    target_industry: Optional[str] = Field(None, examples=["Healthcare"])
    sub_industry: Optional[str] = Field(None, examples=["Healthcare Technology"])
    notes: Optional[str] = Field(None, examples=["Verified via company website."])


class IndustryTaxonomyResponse(BaseModel):
    """Taxonomy response containing all supported primary industries and sub-industries."""
    industries: Dict[str, List[str]]
    total_industries: int


class IndustryAnalyticsResponse(BaseModel):
    """Aggregated industry distribution and sales lifecycle metrics."""
    active_mailbox_id: Optional[int] = None
    total_classified: int = 0
    total_by_industry: Dict[str, int] = Field(default_factory=dict)
    new_enquiries_by_industry: Dict[str, int] = Field(default_factory=dict)
    existing_leads_by_industry: Dict[str, int] = Field(default_factory=dict)
    follow_ups_by_industry: Dict[str, int] = Field(default_factory=dict)
    lead_stages_by_industry: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    industry_distribution: List[Dict[str, Any]] = Field(default_factory=list)
    target_industry_distribution: List[Dict[str, Any]] = Field(default_factory=list)


class ContactRead(BaseModel):
    """Representation of a business contact with relationship memory."""
    id: int
    mailbox_id: Optional[int] = None
    tenant_id: Optional[int] = None
    organization_id: Optional[int] = None
    email_address: str
    name: Optional[str] = None
    company_name: Optional[str] = None
    relationship_type: str
    current_lead_stage: str
    business_context: Optional[str] = None
    industry: Optional[str] = "Unknown"
    sub_industry: Optional[str] = None
    last_interaction_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationRead(BaseModel):
    """Representation of a customer company/organization."""
    id: int
    tenant_id: Optional[int] = None
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = "Unknown"
    sub_industry: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommercialEventRead(BaseModel):
    """Representation of an audited commercial event (PO, Invoice Request, Payment Remittance, etc.)."""
    id: int
    tenant_id: Optional[int] = None
    mailbox_id: Optional[int] = None
    email_id: int
    lead_id: Optional[int] = None
    contact_id: Optional[int] = None
    event_type: str
    amount: Optional[float] = None
    currency: Optional[str] = "USD"
    reference_number: Optional[str] = None
    event_date: Optional[datetime] = None
    status: str = "recorded"
    raw_details: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskRead(BaseModel):
    """Representation of an actionable business task or follow-up."""
    id: int
    tenant_id: Optional[int] = None
    mailbox_id: Optional[int] = None
    lead_id: Optional[int] = None
    email_id: Optional[int] = None
    contact_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    status: str
    priority: str
    who_owes_response: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LeadRead(BaseModel):
    """Representation of a business lead opportunity."""
    id: int
    mailbox_id: Optional[int] = None
    tenant_id: Optional[int] = None
    contact_id: int
    organization_id: Optional[int] = None
    title: str
    status: str
    priority: Optional[str] = "warm"
    estimated_value: Optional[float] = None
    business_context: Optional[str] = None
    source: str
    target_industry: Optional[str] = "Unknown"
    requested_solution_domain: Optional[str] = "Unknown"
    sub_industry: Optional[str] = None
    assigned_to: Optional[str] = None
    organization: Optional[OrganizationRead] = None
    tasks: List[TaskRead] = Field(default_factory=list)
    commercial_events: List[CommercialEventRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassificationHistoryRead(BaseModel):
    """Representation of an audit trail entry for a classification correction or update."""
    id: int
    email_id: Optional[int] = None
    classification_id: int
    previous_values: Dict[str, Any]
    corrected_values: Dict[str, Any]
    notes: Optional[str] = None
    corrected_by: str
    corrected_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassificationRead(BaseModel):
    """Representation of an email classification."""
    id: int
    mailbox_id: Optional[int] = None
    tenant_id: Optional[int] = None
    organization_id: Optional[int] = None
    email_id: int
    contact_id: Optional[int] = None
    lead_id: Optional[int] = None
    relationship: str
    intent: str
    commercial_intent: Optional[str] = "none"
    lead_stage: str
    confidence: float
    classification_reason: Optional[str] = None
    executive_explanation: Optional[str] = None
    key_signals: Optional[List[str]] = Field(default_factory=list)
    context_used: Optional[str] = None
    suggested_next_action: Optional[str] = None

    # Priority & Qualification
    priority_score: Optional[float] = 0.5
    priority_level: Optional[str] = "warm"
    action_urgency: Optional[str] = "medium"
    business_potential: Optional[str] = "medium"
    information_completeness: Optional[str] = "partial"

    # Business Relevance & Pipeline
    relevance_category: Optional[str] = "unknown_review"
    is_business_relevant: Optional[bool] = True
    pipeline_category: Optional[str] = "needs_review"
    supporting_evidence: Optional[List[str]] = Field(default_factory=list)

    # Industry Dimensions
    sender_industry: Optional[str] = "Unknown"
    customer_org_industry: Optional[str] = "Unknown"
    target_industry: Optional[str] = "Unknown"
    requested_solution_domain: Optional[str] = "Unknown"
    sub_industry: Optional[str] = None
    business_activity: Optional[str] = None
    industry_confidence: Optional[float] = 0.0
    industry_reason: Optional[str] = None
    industry_evidence: Optional[List[str]] = Field(default_factory=list)
    industry_requires_review: Optional[bool] = False

    classification_method: str
    requires_human_review: bool
    review_reasons: Optional[List[str]] = Field(default_factory=list)
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailRead(BaseModel):
    """Full representation of a synchronized email with classification."""
    id: int
    mailbox_id: Optional[int] = None
    tenant_id: Optional[int] = None
    organization_id: Optional[int] = None
    contact_id: Optional[int] = None
    lead_id: Optional[int] = None
    account_email: str
    imap_uid: str
    uid_validity: int
    message_id: Optional[str] = None
    gmail_thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    references_header: Optional[str] = None
    sender: str
    recipient: Optional[str] = None
    subject: str
    snippet: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    received_at: Optional[datetime] = None
    has_attachments: bool
    attachment_count: int
    sync_timestamp: datetime
    classification: Optional[ClassificationRead] = None
    contact: Optional[ContactRead] = None
    lead: Optional[LeadRead] = None
    organization: Optional[OrganizationRead] = None
    tasks: List[TaskRead] = Field(default_factory=list)
    commercial_events: List[CommercialEventRead] = Field(default_factory=list)

    @field_serializer("received_at", "sync_timestamp", mode="plain", check_fields=False)
    def serialize_email_dt(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc).isoformat()
        return dt.astimezone(timezone.utc).isoformat()

    model_config = ConfigDict(from_attributes=True)


class PaginatedEmailsResponse(BaseModel):
    """Paginated list of synchronized emails."""
    active_mailbox_id: Optional[int] = None
    items: List[EmailRead]
    total: int
    page: int
    size: int
    pages: int

    @property
    def emails(self) -> List[EmailRead]:
        return self.items


class SyncRequest(BaseModel):
    """Request payload to initiate incremental mailbox synchronization."""
    batch_size: int = Field(default=50, ge=1, le=100, description="Max messages to fetch in this batch (1-100)")


class SyncStatusResponse(BaseModel):
    """Status of email synchronization and background worker for the account."""
    active_mailbox_id: Optional[int] = None
    account_email: str
    connection_status: str = Field(default="connected", description="IMAP connection status")
    worker_status: str = Field(default="idle", description="Background worker status: running, idle, syncing, stopped, error")
    status: str = Field(default="idle", description="Sync status: idle, syncing, completed, failed")
    last_successful_sync: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    last_processed_uid: Optional[str] = None
    highest_synced_uid: Optional[str] = None
    uid_validity: int
    total_emails_stored: int = 0
    total_synced_in_db: int = 0
    inbox_total: int = 0
    new_emails_last_sync: int = 0
    new_emails_retrieved_latest_sync: int = 0
    latest_sync_error: Optional[str] = None
    error_message: Optional[str] = None
    sync_interval_seconds: int = 30
    is_worker_running: bool = False

    @field_serializer("last_successful_sync", "last_synced_at", mode="plain", check_fields=False)
    def serialize_sync_dt(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc).isoformat()
        return dt.astimezone(timezone.utc).isoformat()


class ClassifyBatchRequest(BaseModel):
    """Request payload to batch classify emails."""
    email_ids: Optional[List[int]] = Field(None, description="Explicit list of email IDs to classify")
    unclassified_only: bool = Field(default=True, description="Only classify emails that lack classification")
    limit: int = Field(default=20, ge=1, le=100, description="Max emails to process in batch")


class ClassifyBatchResponse(BaseModel):
    """Summary of batch classification execution."""
    processed_count: int
    successful_count: int
    failed_count: int
    results: List[ClassificationRead]


class DashboardSummaryResponse(BaseModel):
    """High-level metrics and counters for the FlowShark lead dashboard."""
    active_mailbox_id: Optional[int] = None
    active_mailbox_email: Optional[str] = None
    active_mailbox_masked: Optional[str] = None
    total_synced: int
    total_classified: int
    new_leads_count: int
    negotiations_count: int
    follow_ups_count: int
    clarifications_count: int
    existing_leads_count: int
    purchase_orders_count: int
    invoices_count: int
    invoice_billing_count: int = 0
    invoice_requests_count: int = 0
    invoice_updates_count: int = 0
    payments_count: int = 0
    payment_remittances_count: int = 0
    payment_followups_count: int = 0
    payment_disputes_count: int = 0
    needs_review_count: int
    non_business_count: int = 0
    human_corrected_count: int
    is_llm_active: bool
    active_llm_provider: str
    recent_activity: List[EmailRead]


class MailboxRead(BaseModel):
    """Read schema for a configured mailbox."""
    id: int
    email_address: str
    email_address_masked: str
    is_active: bool
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    total_emails_stored: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConnectionDetailsResponse(BaseModel):
    """Details of active Gmail connection and available mailboxes."""
    active_mailbox_id: Optional[int] = None
    email_address: Optional[str] = None
    email_address_masked: Optional[str] = None
    is_connected: bool = False
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    total_emails_stored: int = 0
    available_mailboxes: List[MailboxRead] = Field(default_factory=list)
    message: str = "Active mailbox details"


class UpdateConnectionRequest(BaseModel):
    """Payload to connect, validate, and switch to a Gmail account."""
    email_address: str = Field(..., examples=["newaccount@gmail.com"], description="Gmail account address")
    app_password: str = Field(..., examples=["abcd efgh ijkl mnop"], description="Google App Password (16 chars)")
    imap_host: str = Field(default="imap.gmail.com", examples=["imap.gmail.com"])
    imap_port: int = Field(default=993, examples=[993])
    smtp_host: str = Field(default="smtp.gmail.com", examples=["smtp.gmail.com"])
    smtp_port: int = Field(default=587, examples=[587])


class SwitchMailboxRequest(BaseModel):
    """Payload to switch active mailbox to an already configured account."""
    mailbox_id: Optional[int] = Field(None, examples=[2], description="Target mailbox ID to activate")
    email_address: Optional[str] = Field(None, examples=["account_b@gmail.com"], description="Target mailbox email")

