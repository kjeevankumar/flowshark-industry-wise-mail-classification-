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
        subject: Optional[str] = None,
        body: Optional[str] = None,
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
        # CRITICAL: Do NOT mark the opportunity Won solely because a PO keyword or number appears!
        if intent == "purchase_order":
            resolved_stage = lead_stage if lead_stage not in ["unknown", None, "won"] else "negotiation"
            if relationship == "existing_customer" and lead_stage == "won":
                resolved_stage = "won"
            return PipelineAssignmentResult(
                pipeline_category="purchase_orders",
                relationship=relationship or "existing_lead",
                intent="purchase_order",
                lead_stage=resolved_stage,
                confidence=max(confidence, 0.90),
                reason="Formal purchase order or commercial order confirmation received.",
                needs_review=False,
            )

        # Rule 3A: Invoice Request (Customer asks for tax invoice against PO, agreed project, or duplicate copy)
        if intent == "invoice_request":
            return PipelineAssignmentResult(
                pipeline_category="invoice_request",
                relationship=relationship or "existing_lead",
                intent="invoice_request",
                lead_stage=lead_stage if lead_stage not in ["unknown", None] else "qualified",
                confidence=max(confidence, 0.90),
                reason="Customer request for tax invoice, project invoice, or duplicate invoice copy.",
                needs_review=False,
            )

        # Rule 3B: Invoice Update (GSTIN correction, billing address change, revised invoice)
        if intent == "invoice_update":
            return PipelineAssignmentResult(
                pipeline_category="invoice_update",
                relationship=relationship or "existing_customer",
                intent="invoice_update",
                lead_stage=lead_stage if lead_stage not in ["unknown", None] else "qualified",
                confidence=max(confidence, 0.90),
                reason="Customer request for invoice update (GSTIN correction, billing address, or revised details).",
                needs_review=False,
            )

        # Rule 3C: Payment Remittance (Transfer advice, wire confirmation, UTR number)
        # CRITICAL: Remittance is NOT verified payment confirmation; do NOT mark Won!
        if intent == "payment_remittance":
            return PipelineAssignmentResult(
                pipeline_category="payment_remittance",
                relationship=relationship or "existing_customer",
                intent="payment_remittance",
                lead_stage=lead_stage if lead_stage not in ["unknown", None] else "qualified",
                confidence=max(confidence, 0.90),
                reason="Customer payment remittance advice or wire transfer notification (pending accounting reconciliation).",
                needs_review=False,
            )

        # Rule 3D: Payment Follow-up (Payment status check, expected release date)
        if intent == "payment_follow_up":
            return PipelineAssignmentResult(
                pipeline_category="payment_follow_up",
                relationship=relationship or "existing_customer",
                intent="payment_follow_up",
                lead_stage=lead_stage if lead_stage not in ["unknown", None] else "qualified",
                confidence=max(confidence, 0.88),
                reason="Customer inquiry regarding payment status or scheduled release date.",
                needs_review=False,
            )

        # Rule 3E: Payment Dispute (Discrepancy, duplicate billing, incorrect tax)
        if intent == "payment_dispute":
            return PipelineAssignmentResult(
                pipeline_category="payment_dispute",
                relationship=relationship or "existing_customer",
                intent="payment_dispute",
                lead_stage="negotiation",
                confidence=max(confidence, 0.90),
                reason="Customer dispute challenging invoice amount, duplicate billing, or tax calculation.",
                needs_review=False,
            )

        # Rule 3F: Legacy Invoices (fallback)
        if intent == "invoice":
            return PipelineAssignmentResult(
                pipeline_category="invoices",
                relationship=relationship or "existing_customer",
                intent="invoice",
                lead_stage=lead_stage if lead_stage not in ["unknown", None] else "qualified",
                confidence=max(confidence, 0.88),
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

        # Rule 5: Existing Leads (Ongoing project deployment, Phase 2 expansion, weekly syncs, addendums)
        existing_lead_keywords = [
            "weekly sync", "ongoing deployment", "initial rollout", "phase 2",
            "scope phase 2", "phase 2 feature additions", "phase 2 additions", "phase 2 rollout",
            "addendum to our existing agreement", "addendum to our agreement",
            "addendum to the agreement", "additional hours needed", "additional hours",
            "scope expansion", "existing agreement", "existing contract", "existing engagement",
            "existing account", "existing client", "project update & phase 2",
            "status of our ongoing", "progress of our ongoing",
            "account review", "quarterly business review", "qbr", "current deployment", "current rollout"
        ]
        has_existing_lead_signals = any(
            any(phrase in s.lower() for phrase in existing_lead_keywords)
            for s in signals
        )
        combined_text = f"{subject or ''} {body or ''}".lower()
        if any(phrase in combined_text for phrase in existing_lead_keywords):
            has_existing_lead_signals = True

        if intent == "existing_lead" or (has_existing_lead_signals and intent not in ["follow_up", "business_clarification", "negotiation", "purchase_order", "invoice_request", "invoice_update", "payment_remittance", "payment_follow_up", "payment_dispute"]):
            return PipelineAssignmentResult(
                pipeline_category="existing_leads",
                relationship="existing_lead",
                intent="existing_lead",
                lead_stage=lead_stage if lead_stage not in ["unknown", None] else "qualified",
                confidence=max(confidence, 0.90),
                reason="Ongoing project deployment, phase 2 expansion, or active account communication.",
                needs_review=False,
            )

        # Rule 6: Follow-ups
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

        # Rule 7: Clarifications
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

        # Rule 8: New Leads
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

        # Fallback for known contacts with active lead
        if relationship == "existing_lead" and is_business_relevant:
            if confidence >= 0.75:
                return PipelineAssignmentResult(
                    pipeline_category="existing_leads",
                    relationship="existing_lead",
                    intent=intent or "existing_lead",
                    lead_stage=lead_stage if lead_stage not in ["unknown", None] else "qualified",
                    confidence=confidence,
                    reason="Active business opportunity communication from known lead.",
                    needs_review=confidence < 0.85,
                )

        # Rule 9: Needs Review
        # Used when confidence is genuinely insufficient or signals conflict
        if confidence < 0.85 or intent in ["other", "unknown", "needs_review", None]:
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
