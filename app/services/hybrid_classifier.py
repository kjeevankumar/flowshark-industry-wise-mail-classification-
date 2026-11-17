"""Hybrid Email Classification and Conversation Context Intelligence Service.

Combines:
1. NLP preprocessing (stripping quotes, signatures, HTML).
2. Contact and Lead memory retrieval (normalized address, existing opportunity, current stage).
3. Multi-signal thread history retrieval (RFC Message-ID, In-Reply-To, References, Gmail X-GM-THRID).
4. Rule-based signal detection with negation and context awareness.
5. Semantic LLM classification with structured output and context injection.
6. Lead lifecycle management (stage preservation, opportunity tracking, preventing regressions).
7. Calibrated confidence scoring (85%+ auto-approved, <85% review recommended/needed).
8. Audit history recording on any classification change.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.datetime_utils import safe_datetime_gt, to_utc_naive
from app.models.classification_model import Classification, ClassificationHistory
from app.models.contact_model import Contact
from app.models.conversation_model import Conversation
from app.models.email_model import Email
from app.models.lead_model import Lead, LeadActivityHistory
from app.services.context_service import ContextService, ConversationContext, normalize_sender_address
from app.services.llm_provider import (
    BaseLLMProvider,
    LLMClassificationOutput,
    get_llm_provider,
)
from app.services.nlp_preprocessor import NLPPreprocessor, PreprocessedEmailText
from app.services.rule_classifier import RuleBasedClassifier, RuleSignalResult

logger = logging.getLogger("gmail_fastapi.hybrid_classifier")


class HybridClassifier:
    """Orchestrates NLP preprocessing, conversation context, sender memory, rules, and LLM classification."""

    def __init__(self, db: Session, settings: Optional[Settings] = None):
        self.db = db
        self.settings = settings or get_settings()
        self.nlp = NLPPreprocessor()
        self.rule_engine = RuleBasedClassifier()
        self.context_service = ContextService(db=self.db)
        from app.services.industry_rule_classifier import IndustryRuleClassifier
        self.industry_rule_engine = IndustryRuleClassifier()
        self.llm_provider: BaseLLMProvider = get_llm_provider(settings=self.settings)

    def classify_email(self, email_record: Email, audit_reclassification: bool = True) -> Classification:
        """Execute full context-aware classification pipeline for a single email record."""
        # Check if manual correction exists and should be preserved
        existing_class = (
            self.db.query(Classification)
            .filter(Classification.email_id == email_record.id)
            .first()
        )
        if existing_class and existing_class.classification_method == "manual_correction" and audit_reclassification:
            logger.info("Preserving manual correction for email id %s", email_record.id)
            return existing_class

        # 1. Preprocess text
        preprocessed: PreprocessedEmailText = self.nlp.preprocess(
            body_plain=email_record.body_text,
            body_html=email_record.body_html,
            subject=email_record.subject,
        )

        # 2. Retrieve rich conversational, sender, lead, and thread context
        context: ConversationContext = self.context_service.build_conversation_context(email_record)

        # 3. Business Email Relevance Detection Layer
        from app.services.relevance_detector import BusinessRelevanceDetector
        rel_detector = BusinessRelevanceDetector()
        rel_res = rel_detector.evaluate(
            sender=email_record.sender,
            subject=email_record.subject,
            body_text=preprocessed.cleaned_body,
            body_html=email_record.body_html,
        )

        # Non-business emails short-circuit: never enter lead pipelines or CRM contact/lead records
        # However, if this email is from an ongoing CRM lead/customer, evaluate with conversation context
        has_ongoing_lead_context = bool(context.has_context and context.contact_relationship in ["existing_lead", "existing_customer"])
        if not rel_res.is_business_relevant and not has_ongoing_lead_context:
            email_record.contact_id = None
            email_record.lead_id = None
            if existing_class:
                existing_class.contact_id = None
                existing_class.lead_id = None
                existing_class.relevance_category = rel_res.relevance_category
                existing_class.is_business_relevant = False
                existing_class.pipeline_category = None
                existing_class.relationship = "unknown"
                existing_class.intent = "other"
                existing_class.lead_stage = "unknown"
                existing_class.confidence = rel_res.confidence
                existing_class.classification_reason = rel_res.reason
                existing_class.key_signals = rel_res.evidence
                existing_class.supporting_evidence = rel_res.evidence
                existing_class.context_used = "Non-business notification evaluation"
                existing_class.suggested_next_action = "Archive or ignore non-business notification."
                existing_class.sender_industry = "Not Applicable"
                existing_class.target_industry = "Not Applicable"
                existing_class.sub_industry = None
                existing_class.business_activity = None
                existing_class.industry_confidence = rel_res.confidence
                existing_class.industry_reason = "Non-business notification; industry classification not applicable."
                existing_class.industry_evidence = []
                existing_class.industry_requires_review = False
                existing_class.classification_method = "rule_based"
                existing_class.requires_human_review = rel_res.needs_review
                self.db.commit()
                return existing_class
            else:
                new_cls = Classification(
                    mailbox_id=email_record.mailbox_id,
                    email_id=email_record.id,
                    contact_id=None,
                    lead_id=None,
                    relevance_category=rel_res.relevance_category,
                    is_business_relevant=False,
                    pipeline_category=None,
                    relationship="unknown",
                    intent="other",
                    lead_stage="unknown",
                    confidence=rel_res.confidence,
                    classification_reason=rel_res.reason,
                    key_signals=rel_res.evidence,
                    supporting_evidence=rel_res.evidence,
                    context_used="Non-business notification evaluation",
                    suggested_next_action="Archive or ignore non-business notification.",
                    sender_industry="Not Applicable",
                    target_industry="Not Applicable",
                    sub_industry=None,
                    business_activity=None,
                    industry_confidence=rel_res.confidence,
                    industry_reason="Non-business notification; industry classification not applicable.",
                    industry_evidence=[],
                    industry_requires_review=False,
                    classification_method="rule_based",
                    requires_human_review=rel_res.needs_review,
                    model_provider="fallback",
                    model_name="relevance_rule_engine",
                )
                self.db.add(new_cls)
                self.db.commit()
                return new_cls

        # 3. Rule-based signal evaluation with conversation context
        rule_signals: RuleSignalResult = self.rule_engine.evaluate(
            cleaned_body=preprocessed.cleaned_body,
            subject=email_record.subject,
            is_reply=context.is_reply,
            has_thread_history=context.has_context,
            context=context,
        )

        # 4. LLM semantic classification (with automated fallback if key not configured)
        output: LLMClassificationOutput = self.llm_provider.classify_email(
            subject=email_record.subject,
            preprocessed=preprocessed,
            thread_context=context.context_summary,
            rule_signals=rule_signals,
            context=context,
        )

        # 5. Context & Lifecycle Intelligence Calibration
        final_relationship = output.relationship
        final_intent = output.intent
        final_lead_stage = output.lead_stage
        confidence = output.confidence

        # Rule A: If sender is an existing customer, maintain customer relationship and stage
        if context.contact_relationship == "existing_customer":
            final_relationship = "existing_customer"
            if final_lead_stage in ["new", "unknown"]:
                final_lead_stage = context.contact_lead_stage if context.contact_lead_stage != "unknown" else "won"

        # Rule B: If sender is an existing lead or ongoing conversation, prevent classifying as "new_contact"
        elif context.contact_relationship == "existing_lead" or (context.has_context and context.is_same_sender_continuation):
            if final_relationship == "new_contact":
                final_relationship = "existing_lead"

            # Short follow-ups or continuations must preserve the ongoing lead stage
            if final_intent in ["follow_up", "business_clarification"]:
                prior_stage = context.lead_stage if context.lead_stage != "unknown" else context.contact_lead_stage
                if prior_stage != "unknown":
                    final_lead_stage = prior_stage  # Never reset to unknown or regress
                elif final_lead_stage == "unknown":
                    final_lead_stage = "qualified"

        # Rule C: Preserve lead stage on unrelated emails from known contacts (never carry over WON or LOST to new messages)
        if final_intent == "other":
            if context.contact_relationship == "existing_customer":
                final_relationship = "existing_customer"
                final_lead_stage = "won"
            elif context.contact_relationship == "existing_lead":
                final_relationship = "existing_lead"
                prior_stage = context.lead_stage if context.lead_stage != "unknown" else context.contact_lead_stage
                if prior_stage in ["qualified", "proposal_sent", "negotiation"]:
                    final_lead_stage = prior_stage
                else:
                    final_lead_stage = "unknown"

        # Rule D: Prevent prospective leads from prematurely moving to WON without formal purchase order, invoice, or explicit closed-won signals
        if final_lead_stage == "won" and final_intent not in ["purchase_order", "invoice"] and context.contact_relationship != "existing_customer":
            has_explicit_won_signals = any(
                term in preprocessed.cleaned_body.lower()
                for term in [
                    "purchase order", "po#", "po-", "po number", "attached po",
                    "official order", "contract signed", "payment completed",
                    "remittance advice", "wire transfer processed", "invoice paid"
                ]
            )
            if not has_explicit_won_signals:
                if final_intent == "negotiation":
                    final_lead_stage = "negotiation"
                elif final_intent == "new_enquiry":
                    final_lead_stage = "new"
                elif context.lead_stage in ["qualified", "proposal_sent", "negotiation"]:
                    final_lead_stage = context.lead_stage
                else:
                    final_lead_stage = "unknown"

        # Rule E: Context-informed confidence boost
        # If intent is follow_up and confirmed by sender history and lead memory, calibrate to >= 0.85
        if final_intent == "follow_up" and (context.lead_id or context.contact_relationship == "existing_lead"):
            confidence = max(confidence, 0.88)
        elif final_relationship == "existing_customer" and final_intent in ["business_clarification", "follow_up"]:
            confidence = max(confidence, 0.88)
        elif final_intent == "negotiation" and final_relationship == "existing_lead":
            confidence = max(confidence, 0.88)
        elif final_relationship == "new_contact" and final_intent == "new_enquiry":
            confidence = max(confidence, 0.88)
        elif preprocessed.is_promotional:
            confidence = max(confidence, 0.88)

        # 6. Confidence & human review heuristic calibration (Section 7)
        # Thresholds:
        # >= 0.85: eligible for automatic classification (requires_human_review = False)
        # 0.60 - 0.84: review recommended (requires_human_review = True)
        # < 0.60: needs review (requires_human_review = True)
        requires_review = confidence < 0.85

        # Check for conflicting signals between rules and LLM
        if (
            rule_signals.intent != "other"
            and rule_signals.intent != final_intent
            and rule_signals.confidence >= 0.75
        ):
            requires_review = True
            logger.info(
                "Conflicting signals between rules (%s) and LLM (%s) for email id %s",
                rule_signals.intent,
                final_intent,
                email_record.id,
            )

        # 6b. Industry Classification Resolution
        final_sender_industry = output.sender_industry or "Unknown"
        final_target_industry = output.target_industry or "Unknown"
        final_sub_industry = output.sub_industry
        final_business_activity = output.business_activity
        industry_confidence = output.industry_confidence
        industry_reason = output.industry_reason or "Automated industry evaluation."
        industry_evidence = output.industry_evidence or []
        industry_requires_review = output.industry_requires_review or (industry_confidence < 0.85)

        # Context-Aware Industry Memory (Section 4 & 5):
        # If latest email is a continuation/follow-up of an ongoing lead and sender/target is Unknown, inherit verified context
        if (
            final_sender_industry == "Unknown"
            and context.contact_industry
            and context.contact_industry != "Unknown"
            and (context.has_context and context.is_same_sender_continuation or final_intent in ["follow_up", "business_clarification"])
        ):
            final_sender_industry = context.contact_industry
            if final_target_industry == "Unknown":
                final_target_industry = context.lead_target_industry or context.contact_industry
            if not final_sub_industry:
                final_sub_industry = context.lead_sub_industry or context.contact_sub_industry
            industry_confidence = max(industry_confidence, 0.88)
            industry_requires_review = False
            industry_reason = f"Inherited verified industry ({final_sender_industry}) from ongoing business relationship."

        # 7. Sender Memory: Get or Update Contact Entity
        contact = self.context_service.get_or_create_contact(
            raw_sender=email_record.sender,
            mailbox_id=email_record.mailbox_id,
            initial_relationship=final_relationship,
            initial_stage=final_lead_stage,
            business_context=context.lead_business_context or preprocessed.cleaned_body[:200],
            industry=final_sender_industry if final_sender_industry != "Unknown" and industry_confidence >= 0.80 else None,
            sub_industry=final_sub_industry if final_sender_industry != "Unknown" and industry_confidence >= 0.80 else None,
        )

        # Update contact state
        if final_relationship != "unknown":
            contact.relationship_type = final_relationship
        if final_lead_stage != "unknown":
            contact.current_lead_stage = final_lead_stage
        if email_record.received_at:
            contact.last_interaction_at = to_utc_naive(email_record.received_at)
        if final_sender_industry != "Unknown" and industry_confidence >= 0.80:
            if not getattr(contact, "industry", None) or contact.industry == "Unknown":
                contact.industry = final_sender_industry
                contact.sub_industry = final_sub_industry

        email_record.contact_id = contact.id

        # 8. Lead Lifecycle Management: Get, Update, or Create Lead Entity
        lead = None
        if final_relationship in ["new_contact", "existing_lead"]:
            # If active lead exists, associate with it
            if context.lead_id:
                lead = self.db.query(Lead).filter(Lead.id == context.lead_id).first()
            if not lead:
                lead = (
                    self.db.query(Lead)
                    .filter(Lead.contact_id == contact.id)
                    .order_by(Lead.updated_at.desc())
                    .first()
                )

            # Only create a new lead if no active lead exists and the intent warrants a lead
            if not lead and final_intent in ["new_enquiry", "negotiation", "business_clarification", "follow_up"]:
                lead = self.context_service.get_or_create_lead_for_contact(
                    contact=contact,
                    title=email_record.subject,
                    initial_stage=final_lead_stage,
                    business_context=preprocessed.cleaned_body[:300],
                    mailbox_id=email_record.mailbox_id,
                    target_industry=final_target_industry if final_target_industry != "Unknown" and industry_confidence >= 0.80 else None,
                    sub_industry=final_sub_industry if final_target_industry != "Unknown" and industry_confidence >= 0.80 else None,
                )

            # Update existing lead lifecycle if stage changed with sufficient evidence
            if lead:
                if contact.relationship_type != "existing_customer":
                    contact.relationship_type = "existing_lead"
                old_stage = lead.status
                if final_lead_stage != "unknown" and final_lead_stage != old_stage:
                    lead.status = final_lead_stage
                    lead.updated_at = datetime.now(timezone.utc)
                    # Record lifecycle activity
                    activity = LeadActivityHistory(
                        mailbox_id=email_record.mailbox_id,
                        lead_id=lead.id,
                        contact_id=contact.id,
                        email_id=email_record.id,
                        activity_type="stage_transition",
                        from_stage=old_stage,
                        to_stage=final_lead_stage,
                        description=f"Stage transitioned from '{old_stage}' to '{final_lead_stage}' via email '{email_record.subject}'.",
                    )
                    self.db.add(activity)

                if final_target_industry != "Unknown" and industry_confidence >= 0.80:
                    if not getattr(lead, "target_industry", None) or lead.target_industry == "Unknown":
                        lead.target_industry = final_target_industry
                        lead.sub_industry = final_sub_industry

                email_record.lead_id = lead.id

        # 9. Lead Pipeline Category Determination
        from app.services.pipeline_service import PipelineClassifier
        pipeline_engine = PipelineClassifier()
        pipe_res = pipeline_engine.assign_pipeline(
            is_business_relevant=True,
            relevance_category=output.relevance_category or "business_conversation",
            relationship=final_relationship,
            intent=final_intent,
            lead_stage=final_lead_stage,
            confidence=confidence,
            has_existing_lead=bool(context and (context.lead_id or context.contact_relationship == "existing_lead")),
            has_proposal=bool("proposal" in email_record.subject.lower() or "quotation" in email_record.subject.lower()),
            is_reply=bool(context and context.is_reply),
            has_thread=bool(context and context.has_context),
            key_signals=output.key_signals,
        )
        final_pipeline_category = pipe_res.pipeline_category

        # 10. Persistence and Audit Trail in Classification & ClassificationHistory
        existing_class = (
            self.db.query(Classification)
            .filter(Classification.email_id == email_record.id)
            .first()
        )

        context_used = output.context_used or context.context_used or "Direct email text evaluation"

        if existing_class:
            # Check if values actually changed to record history
            has_changed = (
                existing_class.relationship != final_relationship
                or existing_class.intent != final_intent
                or existing_class.lead_stage != final_lead_stage
                or getattr(existing_class, "sender_industry", None) != final_sender_industry
                or getattr(existing_class, "target_industry", None) != final_target_industry
            )

            if has_changed and audit_reclassification:
                prev_vals = {
                    "relationship": existing_class.relationship,
                    "intent": existing_class.intent,
                    "lead_stage": existing_class.lead_stage,
                    "confidence": existing_class.confidence,
                    "sender_industry": getattr(existing_class, "sender_industry", "Unknown"),
                    "target_industry": getattr(existing_class, "target_industry", "Unknown"),
                    "sub_industry": getattr(existing_class, "sub_industry", None),
                    "industry_confidence": getattr(existing_class, "industry_confidence", 0.0),
                    "classification_reason": existing_class.classification_reason,
                    "classification_method": existing_class.classification_method,
                }
                new_vals = {
                    "relationship": final_relationship,
                    "intent": final_intent,
                    "lead_stage": final_lead_stage,
                    "confidence": confidence,
                    "sender_industry": final_sender_industry,
                    "target_industry": final_target_industry,
                    "sub_industry": final_sub_industry,
                    "industry_confidence": industry_confidence,
                    "classification_reason": output.classification_reason,
                    "classification_method": output.classification_method,
                }
                history_entry = ClassificationHistory(
                    mailbox_id=email_record.mailbox_id,
                    email_id=email_record.id,
                    classification_id=existing_class.id,
                    previous_values=prev_vals,
                    corrected_values=new_vals,
                    notes="Context-aware reclassification backfill",
                    corrected_by="system_context_engine",
                    corrected_at=datetime.now(timezone.utc),
                )
                self.db.add(history_entry)

            existing_class.relevance_category = output.relevance_category
            existing_class.is_business_relevant = output.is_business_relevant
            existing_class.pipeline_category = final_pipeline_category
            existing_class.supporting_evidence = output.supporting_evidence or output.key_signals
            existing_class.mailbox_id = email_record.mailbox_id
            existing_class.contact_id = contact.id
            existing_class.lead_id = email_record.lead_id
            existing_class.relationship = final_relationship
            existing_class.intent = final_intent
            existing_class.lead_stage = final_lead_stage
            existing_class.confidence = confidence
            existing_class.classification_reason = output.classification_reason
            existing_class.key_signals = output.key_signals
            existing_class.context_used = context_used
            existing_class.suggested_next_action = output.suggested_next_action

            # Industry fields
            existing_class.sender_industry = final_sender_industry
            existing_class.target_industry = final_target_industry
            existing_class.sub_industry = final_sub_industry
            existing_class.business_activity = final_business_activity
            existing_class.industry_confidence = industry_confidence
            existing_class.industry_reason = industry_reason
            existing_class.industry_evidence = industry_evidence
            existing_class.industry_requires_review = industry_requires_review

            existing_class.classification_method = output.classification_method
            existing_class.requires_human_review = requires_review
            existing_class.model_provider = self.settings.LLM_PROVIDER if self.settings.is_llm_configured else "fallback"
            existing_class.model_name = self.settings.LLM_MODEL
            classification_record = existing_class
        else:
            classification_record = Classification(
                mailbox_id=email_record.mailbox_id,
                email_id=email_record.id,
                contact_id=contact.id,
                lead_id=email_record.lead_id,
                relevance_category=output.relevance_category,
                is_business_relevant=output.is_business_relevant,
                pipeline_category=final_pipeline_category,
                supporting_evidence=output.supporting_evidence or output.key_signals,
                relationship=final_relationship,
                intent=final_intent,
                lead_stage=final_lead_stage,
                confidence=confidence,
                classification_reason=output.classification_reason,
                key_signals=output.key_signals,
                context_used=context_used,
                suggested_next_action=output.suggested_next_action,
                sender_industry=final_sender_industry,
                target_industry=final_target_industry,
                sub_industry=final_sub_industry,
                business_activity=final_business_activity,
                industry_confidence=industry_confidence,
                industry_reason=industry_reason,
                industry_evidence=industry_evidence,
                industry_requires_review=industry_requires_review,
                classification_method=output.classification_method,
                requires_human_review=requires_review,
                model_provider=self.settings.LLM_PROVIDER if self.settings.is_llm_configured else "fallback",
                model_name=self.settings.LLM_MODEL,
            )
            self.db.add(classification_record)

        # 10. Update or create Conversation Thread Record
        self._sync_conversation_record(
            email_record=email_record,
            contact=contact,
            lead=lead,
            relationship=final_relationship,
            lead_stage=final_lead_stage,
        )

        self.db.commit()
        self.db.refresh(classification_record)
        return classification_record

    def _sync_conversation_record(
        self,
        email_record: Email,
        contact: Contact,
        lead: Optional[Lead],
        relationship: str,
        lead_stage: str,
    ) -> None:
        """Create or update the conversation thread record in the database."""
        thread_id = email_record.gmail_thread_id or f"msg_{email_record.imap_uid}"

        query = self.db.query(Conversation).filter(Conversation.gmail_thread_id == thread_id)
        if email_record.mailbox_id is not None:
            query = query.filter(Conversation.mailbox_id == email_record.mailbox_id)
        conv = query.first()

        if not conv:
            conv = Conversation(
                mailbox_id=email_record.mailbox_id,
                contact_id=contact.id,
                lead_id=lead.id if lead else None,
                gmail_thread_id=thread_id,
                primary_contact=email_record.sender,
                subject=email_record.subject,
                message_count=1,
                last_message_at=to_utc_naive(email_record.received_at) or to_utc_naive(datetime.now(timezone.utc)),
                relationship=relationship,
                current_lead_stage=lead_stage,
            )
            self.db.add(conv)
        else:
            conv.contact_id = contact.id
            if lead:
                conv.lead_id = lead.id
            conv.message_count += 1
            if email_record.received_at and (not conv.last_message_at or safe_datetime_gt(email_record.received_at, conv.last_message_at)):
                conv.last_message_at = to_utc_naive(email_record.received_at)

            if relationship != "unknown":
                conv.relationship = relationship
            if lead_stage != "unknown":
                conv.current_lead_stage = lead_stage

    def backfill_reclassify_all(self, mailbox_id: Optional[int] = None) -> Dict[str, Any]:
        """Chronologically review and reclassify existing emails with context awareness."""
        query = self.db.query(Email)
        if mailbox_id is not None:
            query = query.filter(Email.mailbox_id == mailbox_id)

        # Order chronologically so sender relationship & conversation memory accumulates naturally
        emails = query.order_by(Email.received_at.asc().nullslast(), Email.id.asc()).all()

        reclassified_count = 0
        changed_count = 0
        detailed_changes = []

        for email_item in emails:
            # Capture before state
            cls_before = (
                self.db.query(Classification)
                .filter(Classification.email_id == email_item.id)
                .first()
            )
            before_vals = None
            if cls_before:
                before_vals = {
                    "relationship": cls_before.relationship,
                    "intent": cls_before.intent,
                    "lead_stage": cls_before.lead_stage,
                    "confidence": cls_before.confidence,
                }

            # Classify
            new_cls = self.classify_email(email_item, audit_reclassification=True)
            reclassified_count += 1

            if before_vals and (
                before_vals["relationship"] != new_cls.relationship
                or before_vals["intent"] != new_cls.intent
                or before_vals["lead_stage"] != new_cls.lead_stage
            ):
                changed_count += 1
                detailed_changes.append({
                    "email_id": email_item.id,
                    "sender": email_item.sender,
                    "subject": email_item.subject,
                    "before": before_vals,
                    "after": {
                        "relationship": new_cls.relationship,
                        "intent": new_cls.intent,
                        "lead_stage": new_cls.lead_stage,
                        "confidence": new_cls.confidence,
                        "context_used": new_cls.context_used,
                    },
                })

        return {
            "total_emails_reviewed": len(emails),
            "reclassified_count": reclassified_count,
            "changed_count": changed_count,
            "detailed_changes": detailed_changes,
        }
