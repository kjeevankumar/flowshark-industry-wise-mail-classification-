export type Relationship = 'new_contact' | 'existing_lead' | 'existing_customer' | 'unknown' | 'not_applicable';

export type Intent =
  | 'new_enquiry'
  | 'negotiation'
  | 'follow_up'
  | 'business_clarification'
  | 'purchase_order'
  | 'invoice'
  | 'complaint'
  | 'other'
  | 'not_applicable';

export type LeadStage =
  | 'new'
  | 'qualified'
  | 'proposal_sent'
  | 'negotiation'
  | 'won'
  | 'lost'
  | 'unknown'
  | 'not_applicable';

export type RelevanceCategory =
  | 'business_enquiry'
  | 'business_conversation'
  | 'customer_support'
  | 'purchase_commercial'
  | 'internal_communication'
  | 'account_security_notification'
  | 'system_notification'
  | 'automated_notification'
  | 'newsletter_marketing'
  | 'spam_irrelevant'
  | 'unknown_review';

export type PipelineCategory =
  | 'new_leads'
  | 'negotiations'
  | 'follow_ups'
  | 'clarifications'
  | 'existing_leads'
  | 'purchase_orders'
  | 'invoices'
  | 'needs_review';

export interface Organization {
  id: number;
  tenant_id?: number;
  name: string;
  domain?: string;
  industry?: string;
  sub_industry?: string;
  created_at: string;
}

export interface Task {
  id: number;
  tenant_id?: number;
  mailbox_id?: number;
  lead_id?: number;
  email_id?: number;
  contact_id?: number;
  title: string;
  description?: string;
  assigned_to?: string;
  due_date?: string;
  status: 'pending' | 'completed' | 'cancelled';
  priority: 'high' | 'medium' | 'low';
  who_owes_response: string;
  created_at: string;
  completed_at?: string;
}

export interface Contact {
  id: number;
  mailbox_id?: number;
  tenant_id?: number;
  organization_id?: number;
  email_address: string;
  name?: string;
  company_name?: string;
  relationship_type: Relationship;
  current_lead_stage: LeadStage;
  business_context?: string;
  industry?: string;
  sub_industry?: string;
  last_interaction_at?: string;
}

export interface Lead {
  id: number;
  mailbox_id?: number;
  tenant_id?: number;
  contact_id: number;
  organization_id?: number;
  title: string;
  status: LeadStage;
  priority?: 'hot' | 'warm' | 'low';
  estimated_value?: number;
  business_context?: string;
  source: string;
  target_industry?: string;
  requested_solution_domain?: string;
  sub_industry?: string;
  assigned_to?: string;
  organization?: Organization;
  tasks?: Task[];
  created_at: string;
  updated_at: string;
}

export interface ClassificationHistoryItem {
  id: number;
  email_id?: number;
  classification_id: number;
  previous_values: Record<string, any>;
  corrected_values: Record<string, any>;
  notes?: string;
  corrected_by: string;
  corrected_at: string;
}

export interface EmailContextResponse {
  has_context: boolean;
  sender_email: string;
  sender_name: string;
  contact_id?: number;
  contact_relationship: string;
  contact_lead_stage: string;
  contact_company?: string;
  lead_id?: number;
  lead_title?: string;
  lead_stage: string;
  lead_business_context?: string;
  context_summary: string;
  context_used: string;
  prior_emails: Array<{
    id: number;
    sender: string;
    subject: string;
    received_at?: string;
    snippet: string;
    gmail_thread_id?: string;
  }>;
  prior_classifications: Array<{
    email_id: number;
    relationship: string;
    intent: string;
    lead_stage: string;
    reason?: string;
  }>;
}

export interface Classification {
  id: number;
  mailbox_id?: number;
  tenant_id?: number;
  organization_id?: number;
  email_id: number;
  contact_id?: number;
  lead_id?: number;
  relationship: Relationship;
  intent: Intent;
  commercial_intent?: string;
  lead_stage: LeadStage;
  confidence: number;
  classification_reason?: string;
  executive_explanation?: string;
  key_signals?: string[];
  context_used?: string;
  suggested_next_action?: string;

  // Priority & Qualification Scoring
  priority_score?: number;
  priority_level?: 'hot' | 'warm' | 'low';
  action_urgency?: 'high' | 'medium' | 'low';
  business_potential?: 'high' | 'medium' | 'low' | 'unknown';
  information_completeness?: 'complete' | 'partial' | 'missing';

  // Business Relevance & Pipeline
  relevance_category?: RelevanceCategory | string;
  is_business_relevant?: boolean;
  pipeline_category?: PipelineCategory | string;
  supporting_evidence?: string[];

  // Industry Dimensions (Section 6 & 8)
  sender_industry?: string;
  customer_org_industry?: string;
  target_industry?: string;
  requested_solution_domain?: string;
  sub_industry?: string;
  business_activity?: string;
  industry_confidence?: number;
  industry_reason?: string;
  industry_evidence?: string[];
  industry_requires_review?: boolean;

  classification_method: string;
  requires_human_review: boolean;
  review_reasons?: string[];
  model_provider?: string;
  model_name?: string;
  created_at: string;
}

export interface IndustryTaxonomyResponse {
  industries: Record<string, string[]>;
  total_industries: number;
}

export interface IndustryDistributionItem {
  industry?: string;
  target_industry?: string;
  count: number;
  percentage: number;
}

export interface IndustryAnalyticsResponse {
  active_mailbox_id?: number;
  total_classified: number;
  total_by_industry: Record<string, number>;
  new_enquiries_by_industry: Record<string, number>;
  existing_leads_by_industry: Record<string, number>;
  follow_ups_by_industry: Record<string, number>;
  lead_stages_by_industry: Record<string, Record<string, number>>;
  industry_distribution: IndustryDistributionItem[];
  target_industry_distribution: IndustryDistributionItem[];
}

export interface IndustryCorrectionRequest {
  sender_industry?: string;
  target_industry?: string;
  sub_industry?: string;
  notes?: string;
}

export interface Email {
  id: number;
  mailbox_id?: number;
  tenant_id?: number;
  organization_id?: number;
  contact_id?: number;
  lead_id?: number;
  account_email: string;
  imap_uid: string;
  uid_validity: number;
  message_id?: string;
  gmail_thread_id?: string;
  in_reply_to?: string;
  references_header?: string;
  sender: string;
  recipient?: string;
  subject: string;
  snippet?: string;
  body_text?: string;
  body_html?: string;
  received_at?: string;
  has_attachments: boolean;
  attachment_count: number;
  sync_timestamp: string;
  classification?: Classification;
  contact?: Contact;
  lead?: Lead;
  organization?: Organization;
  tasks?: Task[];
}

export interface PaginatedEmails {
  active_mailbox_id?: number;
  items: Email[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface DashboardSummary {
  active_mailbox_id?: number;
  active_mailbox_email?: string;
  active_mailbox_masked?: string;
  total_synced: number;
  total_classified: number;
  new_leads_count: number;
  negotiations_count: number;
  follow_ups_count: number;
  clarifications_count: number;
  existing_leads_count: number;
  purchase_orders_count: number;
  invoices_count: number;
  needs_review_count: number;
  non_business_count?: number;
  human_corrected_count: number;
  is_llm_active: boolean;
  active_llm_provider: string;
  recent_activity: Email[];
}

export interface ConfigStatus {
  configured: boolean;
  gmail_address_configured: boolean;
  gmail_address_masked?: string;
  app_password_configured: boolean;
  imap_host: string;
  imap_port: number;
  smtp_host: string;
  smtp_port: number;
  message: string;
}

export interface MailboxRead {
  id: number;
  email_address: string;
  email_address_masked: string;
  is_active: boolean;
  imap_host: string;
  imap_port: number;
  smtp_host: string;
  smtp_port: number;
  total_emails_stored: number;
  created_at: string;
  updated_at: string;
}

export interface ConnectionDetailsResponse {
  active_mailbox_id?: number;
  email_address?: string;
  email_address_masked: string;
  is_connected: boolean;
  imap_host?: string;
  imap_port?: number;
  smtp_host?: string;
  smtp_port?: number;
  total_emails_stored: number;
  available_mailboxes: MailboxRead[];
  message: string;
}

export interface UpdateConnectionRequest {
  email_address: string;
  app_password: string;
  imap_host?: string;
  imap_port?: number;
  smtp_host?: string;
  smtp_port?: number;
}

export interface SwitchMailboxRequest {
  mailbox_id?: number;
  email_address?: string;
}

export interface SyncStatus {
  active_mailbox_id?: number;
  account_email: string;
  connection_status: string; // 'connected' | 'disconnected' | 'unconfigured' | 'error'
  worker_status: string;     // 'running' | 'idle' | 'syncing' | 'stopped' | 'error'
  status: string;            // 'completed' | 'idle' | 'syncing' | 'failed'
  last_successful_sync?: string;
  last_synced_at?: string;
  last_processed_uid?: string;
  highest_synced_uid?: string;
  uid_validity: number;
  total_emails_stored: number;
  total_synced_in_db: number;
  inbox_total: number;
  new_emails_last_sync: number;
  new_emails_retrieved_latest_sync: number;
  latest_sync_error?: string;
  error_message?: string;
  sync_interval_seconds: number;
  is_worker_running: boolean;
}

