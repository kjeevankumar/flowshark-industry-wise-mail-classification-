"""Conversation Context and Sender Relationship Intelligence Service.

Handles:
- Sender email normalization (RFC 2822 parsing, lowercase address extraction).
- Multi-signal thread retrieval (Gmail X-GM-THRID, RFC In-Reply-To, References, Message-ID).
- Sender history retrieval (prior messages from same sender within mailbox).
- Contact and Lead memory retrieval (existing relationship, current lead stage, business context).
- Chronological context assembly for hybrid & LLM classification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parseaddr
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from app.core.datetime_utils import safe_datetime_le, safe_sort_key

from app.models.classification_model import Classification
from app.models.contact_model import Contact
from app.models.conversation_model import Conversation
from app.models.email_model import Email
from app.models.lead_model import Lead, LeadActivityHistory
from app.models.organization_model import Organization
from app.models.tenant_model import Tenant

logger = logging.getLogger("gmail_fastapi.context_service")

FREEMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "hotmail.com",
    "outlook.com", "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
    "aol.com", "zoho.com", "proton.me", "protonmail.com", "mail.com"
}


def normalize_sender_address(raw_sender: Optional[str]) -> Tuple[str, str]:
    """Extract normalized (clean_email, display_name) from raw From header.

    Examples:
        '"G1 Digitalizing" <g1digitalizing@gmail.com>' -> ('g1digitalizing@gmail.com', 'G1 Digitalizing')
        'user@example.com' -> ('user@example.com', 'user')
    """
    if not raw_sender:
        return "", ""
    name, addr = parseaddr(raw_sender)
    clean_addr = addr.strip().lower()
    clean_name = name.strip() or (clean_addr.split("@")[0] if "@" in clean_addr else "")
    return clean_addr, clean_name


def extract_message_ids(header_text: Optional[str]) -> List[str]:
    """Extract individual Message-IDs from In-Reply-To or References headers."""
    if not header_text:
        return []
    # Match patterns like <anything@anything>
    matches = re.findall(r"<([^>]+)>", header_text)
    if matches:
        return [f"<{m.strip()}>" for m in matches]
    # Fallback to splitting whitespace if no angle brackets
    return [h.strip() for h in header_text.split() if h.strip()]


@dataclass
class ConversationContext:
    """Structured context assembled for classifying an email."""
    has_context: bool = False
    sender_email: str = ""
    sender_name: str = ""
    contact_id: Optional[int] = None
    contact_relationship: str = "unknown"  # new_contact, existing_lead, existing_customer, unknown
    contact_lead_stage: str = "unknown"
    contact_company: Optional[str] = None
    contact_business_context: Optional[str] = None
    contact_industry: Optional[str] = None
    contact_sub_industry: Optional[str] = None

    lead_id: Optional[int] = None
    lead_title: Optional[str] = None
    lead_stage: str = "unknown"
    lead_business_context: Optional[str] = None
    lead_target_industry: Optional[str] = None
    lead_sub_industry: Optional[str] = None

    prior_emails: List[Dict[str, Any]] = field(default_factory=list)
    prior_classifications: List[Dict[str, Any]] = field(default_factory=list)
    is_reply: bool = False
    is_same_sender_continuation: bool = False
    context_summary: str = ""
    context_used: str = ""


class ContextService:
    """Manages sender memory, contact entities, lead records, and conversation context."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_organization(
        self,
        name: str,
        domain: Optional[str] = None,
        tenant_id: Optional[int] = None,
        industry: str = "Unknown",
        sub_industry: Optional[str] = None,
        business_activity: Optional[str] = None,
    ) -> Optional[Organization]:
        """Find or create an external client Organization."""
        if not name or name.strip().lower() in ["unknown", "none", ""]:
            return None
        clean_name = name.strip()
        query = self.db.query(Organization).filter(Organization.name.ilike(clean_name))
        if tenant_id is not None:
            query = query.filter(Organization.tenant_id == tenant_id)
        org = query.first()

        if not org and domain:
            query_d = self.db.query(Organization).filter(Organization.domain == domain.strip().lower())
            if tenant_id is not None:
                query_d = query_d.filter(Organization.tenant_id == tenant_id)
            org = query_d.first()

        if not org:
            org = Organization(
                tenant_id=tenant_id,
                name=clean_name,
                domain=domain.strip().lower() if domain else None,
                industry=industry or "Unknown",
                sub_industry=sub_industry,
                business_activity=business_activity,
            )
            self.db.add(org)
            self.db.flush()
        else:
            if industry and industry != "Unknown" and getattr(org, "industry", "Unknown") == "Unknown":
                org.industry = industry
            if sub_industry and not getattr(org, "sub_industry", None):
                org.sub_industry = sub_industry
            if domain and not org.domain:
                org.domain = domain.strip().lower()
        return org

    def get_or_create_contact(
        self,
        raw_sender: str,
        mailbox_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
        initial_relationship: str = "unknown",
        initial_stage: str = "unknown",
        business_context: Optional[str] = None,
        industry: Optional[str] = None,
        sub_industry: Optional[str] = None,
    ) -> Contact:
        """Find or create a Contact record for a normalized email address with Organization association."""
        clean_email, display_name = normalize_sender_address(raw_sender)
        if not clean_email:
            clean_email = (raw_sender or "unknown").strip().lower()
            display_name = raw_sender or "Unknown"

        query = self.db.query(Contact).filter(Contact.email_address == clean_email)
        if mailbox_id is not None:
            query = query.filter(Contact.mailbox_id == mailbox_id)
        contact = query.first()

        # Extract domain & organization
        email_domain = clean_email.split("@")[1] if "@" in clean_email else ""
        org = None
        if email_domain and email_domain not in FREEMAIL_DOMAINS:
            org_name = display_name if display_name and not display_name.lower().endswith(email_domain) else email_domain.split(".")[0].title()
            org = self.get_or_create_organization(
                name=org_name,
                domain=email_domain,
                tenant_id=tenant_id,
                industry=industry or "Unknown",
                sub_industry=sub_industry,
            )

        if not contact:
            company_name = org.name if org else (display_name if display_name and not display_name.lower().endswith("@gmail.com") else None)

            contact = Contact(
                tenant_id=tenant_id,
                mailbox_id=mailbox_id,
                organization_id=org.id if org else None,
                email_address=clean_email,
                name=display_name,
                company_name=company_name,
                relationship_type=initial_relationship,
                current_lead_stage=initial_stage,
                business_context=business_context,
                industry=industry or (org.industry if org else "Unknown"),
                sub_industry=sub_industry or (org.sub_industry if org else None),
            )
            self.db.add(contact)
            self.db.flush()
        else:
            if tenant_id and not contact.tenant_id:
                contact.tenant_id = tenant_id
            if org and not contact.organization_id:
                contact.organization_id = org.id
            if display_name and not contact.name:
                contact.name = display_name
            if business_context and not contact.business_context:
                contact.business_context = business_context
            if industry and industry != "Unknown" and getattr(contact, "industry", "Unknown") == "Unknown":
                contact.industry = industry
            if sub_industry and not getattr(contact, "sub_industry", None):
                contact.sub_industry = sub_industry

        return contact

    def get_or_create_lead_for_contact(
        self,
        contact: Contact,
        title: str,
        initial_stage: str = "new",
        business_context: Optional[str] = None,
        mailbox_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        target_industry: Optional[str] = None,
        sub_industry: Optional[str] = None,
        requested_solution_domain: Optional[str] = None,
        priority: str = "warm",
        thread_id: Optional[str] = None,
        is_reply_or_continuation: bool = False,
        opportunity_id: Optional[int] = None,
    ) -> Lead:
        """Find active lead or create a new distinct lead opportunity for a contact."""
        # 1. Explicit opportunity ID
        if opportunity_id:
            opp = self.db.query(Lead).filter(Lead.id == opportunity_id).first()
            if opp:
                return opp

        # 2. If it is a verified thread reply/continuation, associate with existing thread lead
        if is_reply_or_continuation and thread_id:
            thread_lead = (
                self.db.query(Lead)
                .join(Email, Email.lead_id == Lead.id)
                .filter(
                    Email.gmail_thread_id == thread_id,
                    Email.mailbox_id == (mailbox_id or contact.mailbox_id),
                )
                .order_by(Lead.updated_at.desc())
                .first()
            )
            if thread_lead:
                if business_context and not thread_lead.business_context:
                    thread_lead.business_context = business_context
                return thread_lead

        # 3. If explicit continuation of active contact lead
        if is_reply_or_continuation:
            active_lead = (
                self.db.query(Lead)
                .filter(
                    Lead.contact_id == contact.id,
                    Lead.status.notin_(["won", "lost"]),
                )
                .order_by(Lead.updated_at.desc())
                .first()
            )
            if active_lead:
                if business_context and not active_lead.business_context:
                    active_lead.business_context = business_context
                return active_lead

        # 4. Otherwise, create a NEW distinct Business Opportunity
        clean_title = (title or "").strip()
        clean_title = re.sub(r"^(re|fwd|fw):\s*", "", clean_title, flags=re.IGNORECASE).strip()
        if not clean_title or clean_title.lower() in ["(no subject)", "no subject"]:
            company_or_contact = contact.company_name or contact.name or contact.email_address
            clean_title = f"{requested_solution_domain or 'Opportunity'} – {company_or_contact}"

        lead = Lead(
            tenant_id=tenant_id or contact.tenant_id,
            mailbox_id=mailbox_id or contact.mailbox_id,
            organization_id=organization_id or contact.organization_id,
            contact_id=contact.id,
            title=clean_title,
            status=initial_stage if initial_stage != "unknown" else "new",
            priority=priority,
            business_context=business_context,
            source="email",
            target_industry=target_industry or "Unknown",
            sub_industry=sub_industry,
            requested_solution_domain=requested_solution_domain or "Unknown",
        )
        self.db.add(lead)
        self.db.flush()

        activity = LeadActivityHistory(
            mailbox_id=mailbox_id or contact.mailbox_id,
            lead_id=lead.id,
            contact_id=contact.id,
            activity_type="lead_created",
            to_stage=lead.status,
            description=f"Created new opportunity '{clean_title}'.",
        )
        self.db.add(activity)

        return lead

    def build_conversation_context(self, email_record: Email) -> ConversationContext:
        """Retrieve full conversational, sender, lead, and thread context for an email."""
        clean_email, display_name = normalize_sender_address(email_record.sender)

        # 1. Fetch Contact record if exists
        contact = None
        if clean_email:
            contact_q = self.db.query(Contact).filter(Contact.email_address == clean_email)
            if email_record.mailbox_id is not None:
                contact_q = contact_q.filter(Contact.mailbox_id == email_record.mailbox_id)
            contact = contact_q.first()

        # 2. Fetch associated Lead ONLY if explicitly linked or part of verified thread
        lead = None
        if email_record.lead_id:
            lead = self.db.query(Lead).filter(Lead.id == email_record.lead_id).first()
        elif email_record.gmail_thread_id:
            thread_lead = (
                self.db.query(Lead)
                .join(Email, Email.lead_id == Lead.id)
                .filter(
                    Email.gmail_thread_id == email_record.gmail_thread_id,
                    Email.id != email_record.id,
                )
                .order_by(Lead.updated_at.desc())
                .first()
            )
            if thread_lead:
                lead = thread_lead

        # 3. Retrieve prior emails using multi-signal strategy:
        # Distinguish verified thread emails from general sender history
        thread_prior_emails: Dict[int, Email] = {}
        sender_prior_emails: Dict[int, Email] = {}

        # a) By Gmail thread ID
        if email_record.gmail_thread_id:
            th_q = self.db.query(Email).filter(
                Email.gmail_thread_id == email_record.gmail_thread_id,
                Email.id != email_record.id,
            )
            if email_record.mailbox_id is not None:
                th_q = th_q.filter(Email.mailbox_id == email_record.mailbox_id)
            for em in th_q.all():
                thread_prior_emails[em.id] = em

        # b) By RFC In-Reply-To and References
        rfc_ids: Set[str] = set()
        if email_record.in_reply_to:
            rfc_ids.update(extract_message_ids(email_record.in_reply_to))
        if email_record.references_header:
            rfc_ids.update(extract_message_ids(email_record.references_header))

        if rfc_ids:
            rfc_q = self.db.query(Email).filter(
                Email.message_id.in_(list(rfc_ids)),
                Email.id != email_record.id,
            )
            if email_record.mailbox_id is not None:
                rfc_q = rfc_q.filter(Email.mailbox_id == email_record.mailbox_id)
            for em in rfc_q.all():
                thread_prior_emails[em.id] = em

        # c) By normalized sender address history
        if clean_email:
            sender_q = self.db.query(Email).filter(
                Email.sender.ilike(f"%{clean_email}%"),
                Email.id != email_record.id,
            )
            if email_record.mailbox_id is not None:
                sender_q = sender_q.filter(Email.mailbox_id == email_record.mailbox_id)
            for em in sender_q.order_by(Email.received_at.asc(), Email.id.asc()).limit(5).all():
                sender_prior_emails[em.id] = em

        # Isolate conversation: if exact thread emails exist, use them. Otherwise background history.
        if thread_prior_emails:
            candidate_list = list(thread_prior_emails.values())
        else:
            candidate_list = list(sender_prior_emails.values())

        # Filter out those received after current email if timestamps exist
        if email_record.received_at:
            candidate_list = [
                em for em in candidate_list
                if (em.received_at is None or safe_datetime_le(em.received_at, email_record.received_at))
                and em.id < (email_record.id or 999999999)
            ]
        else:
            candidate_list = [
                em for em in candidate_list
                if em.id < (email_record.id or 999999999)
            ]

        candidate_list.sort(key=lambda x: (safe_sort_key(x.received_at), x.id or 0))

        # Check reply status
        is_reply = bool(
            email_record.subject.lower().startswith("re:")
            or email_record.in_reply_to
            or (email_record.references_header and email_record.references_header.strip())
        )

        has_context = bool(candidate_list or contact or lead)
        is_same_sender = any(
            normalize_sender_address(em.sender)[0] == clean_email
            for em in candidate_list
        )

        # Extract classifications for prior emails
        prior_emails_info: List[Dict[str, Any]] = []
        prior_classifications_info: List[Dict[str, Any]] = []

        context_lines: List[str] = []

        if contact:
            rel = contact.relationship_type
            stage = contact.current_lead_stage
            ctx = contact.business_context or ""
            lead_info = f", Lead: '{lead.title}' ({lead.status})" if lead else ""
            context_lines.append(
                f"[Contact Memory] Sender '{contact.name or clean_email}' <{clean_email}> is {rel.upper()} (Stage: {stage.upper()}){lead_info}. {ctx}"
            )

        context_used_fragments: List[str] = []

        # Take up to last 4 preceding messages for prompt context
        for em in candidate_list[-4:]:
            clean_text = (em.snippet or em.body_text or "")[:180].replace("\n", " ").strip()
            em_date = str(em.received_at)[:19] if em.received_at else "Prior"

            # Query classification for prior email
            cls_q = self.db.query(Classification).filter(Classification.email_id == em.id).first()
            cls_summary = ""
            if cls_q:
                ind_str = f" | {getattr(cls_q, 'sender_industry', 'Unknown')} -> {getattr(cls_q, 'target_industry', 'Unknown')}" if getattr(cls_q, 'target_industry', None) else ""
                cls_summary = f" [Classified as: {cls_q.relationship} | {cls_q.intent} | {cls_q.lead_stage}{ind_str}]"
                prior_classifications_info.append({
                    "email_id": em.id,
                    "relationship": cls_q.relationship,
                    "intent": cls_q.intent,
                    "lead_stage": cls_q.lead_stage,
                    "sender_industry": getattr(cls_q, "sender_industry", "Unknown"),
                    "target_industry": getattr(cls_q, "target_industry", "Unknown"),
                    "sub_industry": getattr(cls_q, "sub_industry", None),
                    "reason": cls_q.classification_reason,
                })

            context_lines.append(
                f"[{em_date}] From: {em.sender} | Subject: '{em.subject}'{cls_summary} | Preview: {clean_text}"
            )

            prior_emails_info.append({
                "id": em.id,
                "sender": em.sender,
                "subject": em.subject,
                "received_at": str(em.received_at) if em.received_at else None,
                "snippet": clean_text,
                "gmail_thread_id": em.gmail_thread_id,
            })

        # Formulate context_used description
        if contact and contact.relationship_type != "unknown":
            context_used_fragments.append(
                f"Known contact ({contact.relationship_type}, stage: {contact.current_lead_stage})"
            )
        if lead:
            context_used_fragments.append(
                f"Associated lead '{lead.title}' in stage '{lead.status}'"
            )
        if candidate_list:
            last_prior = candidate_list[-1]
            context_used_fragments.append(
                f"{len(candidate_list)} prior email(s) found (last: '{last_prior.subject}')"
            )

        context_used = "; ".join(context_used_fragments) if context_used_fragments else "None (first contact or isolated email)"
        context_summary = "\n".join(context_lines)

        return ConversationContext(
            has_context=has_context,
            sender_email=clean_email,
            sender_name=display_name,
            contact_id=contact.id if contact else None,
            contact_relationship=contact.relationship_type if contact else "unknown",
            contact_lead_stage=contact.current_lead_stage if contact else "unknown",
            contact_company=contact.company_name if contact else None,
            contact_business_context=contact.business_context if contact else None,
            contact_industry=getattr(contact, "industry", None) if contact else None,
            contact_sub_industry=getattr(contact, "sub_industry", None) if contact else None,
            lead_id=lead.id if lead else None,
            lead_title=lead.title if lead else None,
            lead_stage=lead.status if lead else "unknown",
            lead_business_context=lead.business_context if lead else None,
            lead_target_industry=getattr(lead, "target_industry", None) if lead else None,
            lead_sub_industry=getattr(lead, "sub_industry", None) if lead else None,
            prior_emails=prior_emails_info,
            prior_classifications=prior_classifications_info,
            is_reply=is_reply,
            is_same_sender_continuation=is_same_sender,
            context_summary=context_summary,
            context_used=context_used,
        )
