"""Strict Lead Pipeline Classifier for FlowShark.

Assigns business emails to one of the 8 core lead pipelines:
1. new_leads
2. negotiations
3. follow_ups
4. clarifications
5. existing_leads
6. purchase_orders
7. invoices
8. needs_review

Non-business emails receive pipeline_category = None.
"""

from dataclasses import dataclass
import re
from typing import Any, List, Optional


@dataclass
class PipelineAssignmentResult:
    """Result of lead pipeline classification."""
    pipeline_category: Optional[str]
    relationship: Optional[str]
    intent: Optional[str]
    lead_stage: Optional[str]
    confidence: float
    reason: str
    needs_review: bool


class PipelineClassifier:
    """Resolves strict pipeline assignment using business intent, relationship, and conversation context."""

    def assign_pipeline(
        self,
        is_business_relevant: bool,
        relevance_category: str,
        relationship: Optional[str],
        intent: Optional[str],
        lead_stage: Optional[str],
        confidence: float,
        has_existing_lead: bool = False,
        has_proposal: bool = False,
        is_reply: bool = False,
        has_thread: bool = False,
        key_signals: Optional[List[str]] = None,
    ) -> PipelineAssignmentResult:
        """Deterministically determine pipeline category ensuring no false pipeline assignments."""

        # Rule 1: Non-business emails NEVER enter lead pipelines
        if not is_business_relevant:
            return PipelineAssignmentResult(
                pipeline_category=None,
                relationship="not_applicable",
                intent="not_applicable",
                lead_stage="not_applicable",
                confidence=confidence,
                reason=f"Non-business email ({relevance_category}); excluded from sales lead pipelines.",
                needs_review=False,
            )

        signals = key_signals or []

        # Rule 2: Purchase Orders
        if intent == "purchase_order":
            return PipelineAssignmentResult(
                pipeline_category="purchase_orders",
                relationship=relationship or "existing_customer",
                intent="purchase_order",
                lead_stage="won",
                confidence=max(confidence, 0.90),
                reason="Formal purchase order or commercial order confirmation.",
                needs_review=False,
            )

        # Rule 3: Invoices
        if intent == "invoice":
            return PipelineAssignmentResult(
                pipeline_category="invoices",
                relationship=relationship or "existing_customer",
                intent="invoice",
                lead_stage=lead_stage if lead_stage != "unknown" else "won",
                confidence=max(confidence, 0.90),
                reason="Commercial invoice, billing statement, or payment receipt.",
                needs_review=False,
            )

        # Rule 4: Negotiations
        if intent == "negotiation":
            return PipelineAssignmentResult(
                pipeline_category="negotiations",
                relationship="existing_lead" if relationship != "existing_customer" else "existing_customer",
                intent="negotiation",
                lead_stage="negotiation",
                confidence=max(confidence, 0.88),
                reason="Commercial negotiation, discount, or pricing terms discussion on opportunity.",
                needs_review=False,
            )

        # Rule 5: Follow-ups
        if intent == "follow_up":
            return PipelineAssignmentResult(
                pipeline_category="follow_ups",
                relationship=relationship if relationship in ["existing_lead", "existing_customer"] else "existing_lead",
                intent="follow_up",
                lead_stage=lead_stage if lead_stage not in ["unknown", None] else "qualified",
                confidence=max(confidence, 0.88),
                reason="Status, progress, or reminder follow-up on project or proposal.",
                needs_review=False,
            )

        # Rule 6: Clarifications
        if intent == "business_clarification":
            return PipelineAssignmentResult(
                pipeline_category="clarifications",
                relationship=relationship if relationship in ["existing_lead", "existing_customer"] else "existing_lead",
                intent="business_clarification",
                lead_stage=lead_stage if lead_stage not in ["unknown", None] else "qualified",
                confidence=max(confidence, 0.88),
                reason="Scope, technical requirements, or deliverable clarification.",
                needs_review=False,
            )

        # Rule 7: New Leads
        if intent == "new_enquiry":
            return PipelineAssignmentResult(
                pipeline_category="new_leads",
                relationship="new_contact" if relationship in ["new_contact", "unknown", None] else relationship,
                intent="new_enquiry",
                lead_stage=lead_stage if lead_stage in ["new", "qualified"] else "new",
                confidence=max(confidence, 0.88),
                reason="Prospective customer inquiring about services, quotes, or new project.",
                needs_review=False,
            )

        # Rule 8: Existing Leads
        # A known sender with an active opportunity who is sending a business communication
        # not specifically negotiations, follow_ups, or clarifications
        if relationship == "existing_lead" and is_business_relevant:
            # If confidence is good, assign to existing_leads
            if confidence >= 0.75:
                return PipelineAssignmentResult(
                    pipeline_category="existing_leads",
                    relationship="existing_lead",
                    intent=intent or "business_clarification",
                    lead_stage=lead_stage if lead_stage not in ["unknown", None] else "qualified",
                    confidence=confidence,
                    reason="Active business opportunity communication from known lead.",
                    needs_review=confidence < 0.85,
                )

        # Rule 9: Needs Review
        # Used when confidence is genuinely insufficient or signals conflict
        if confidence < 0.85 or intent in ["other", "unknown", None]:
            return PipelineAssignmentResult(
                pipeline_category="needs_review",
                relationship=relationship or "unknown",
                intent=intent or "other",
                lead_stage=lead_stage or "unknown",
                confidence=confidence,
                reason="Ambiguous business context or low confidence; manual review needed.",
                needs_review=True,
            )

        # Fallback to new_leads if new contact with business relevance
        if relationship == "new_contact":
            return PipelineAssignmentResult(
                pipeline_category="new_leads",
                relationship="new_contact",
                intent="new_enquiry",
                lead_stage="new",
                confidence=confidence,
                reason="Business inquiry from new contact.",
                needs_review=confidence < 0.85,
            )

        return PipelineAssignmentResult(
            pipeline_category="needs_review",
            relationship=relationship or "unknown",
            intent=intent or "other",
            lead_stage=lead_stage or "unknown",
            confidence=confidence,
            reason="Unresolved pipeline classification.",
            needs_review=True,
        )
