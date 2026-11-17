"""Executive Classification Explanation Generator for FlowShark AI.

Provides transparent, human-readable explanations answering:
- Why is this email Qualified?
- Why is this email Unknown / Not Applicable?
- Why is this email Negotiation, New Lead, or Existing Lead?
- Why was this Industry assigned?
- Why is it Business Relevant vs Non-Business?
"""

from typing import Any, Dict, List, Optional


def generate_executive_explanation(
    is_business_relevant: bool,
    relevance_category: str,
    pipeline_category: Optional[str],
    relationship: str,
    intent: str,
    lead_stage: str,
    confidence: float,
    sender: str = "",
    subject: str = "",
    sender_industry: str = "Unknown",
    target_industry: str = "Unknown",
    sub_industry: Optional[str] = None,
    key_signals: Optional[List[str]] = None,
    supporting_evidence: Optional[List[str]] = None,
    context_used: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate structured executive explanation points for CRM and management review."""
    signals = list(set((key_signals or []) + (supporting_evidence or [])))

    # 1. Why this Lead Stage?
    stage_lower = (lead_stage or "unknown").lower()
    if stage_lower == "qualified":
        why_stage = (
            "Why Qualified Lead: The communication exhibits verified commercial intent with explicit "
            "project requirements, defined scope (features, technical specs, or deliverables), "
            "budget validation, or decision-maker engagement. It moves past preliminary discovery into "
            "active opportunity evaluation."
        )
    elif stage_lower in ("unknown", "not_applicable"):
        if not is_business_relevant:
            why_stage = (
                f"Why Unknown / Excluded: This email is an automated {relevance_category.replace('_', ' ')} "
                "with zero sales inquiry or commercial opportunity. In FlowShark's B2B CRM intelligence architecture, "
                "sales pipeline stages (Qualified, Negotiation, Won) only apply to genuine business leads and are "
                "intentionally disabled (Unknown) for system notifications."
            )
        else:
            why_stage = (
                "Why Unknown Stage: The message lacks commercial qualification signals (such as budget, timeline, "
                "or requirements) needed to advance the stage, or is a general non-sales communication."
            )
    elif stage_lower == "negotiation":
        why_stage = (
            "Why Negotiation: The contact is actively discussing commercial terms, pricing adjustments, "
            "counter-offers, discount requests, or budget constraints on a proposal or quotation."
        )
    elif stage_lower == "new":
        why_stage = (
            "Why New Lead: First-time inbound inquiry inquiring about services, capabilities, or pricing. "
            "Awaiting initial discovery and requirements qualification."
        )
    elif stage_lower == "proposal_sent":
        why_stage = (
            "Why Proposal Sent: A quotation or scope proposal has been delivered to the prospective client, "
            "and the deal is awaiting formal client review or commercial feedback."
        )
    elif stage_lower == "won":
        why_stage = (
            "Why Won / Closed: Explicit commercial commitment detected via formal purchase order (PO), "
            "signed contract/agreement, or payment confirmation."
        )
    elif stage_lower == "lost":
        why_stage = (
            "Why Lost: The prospect indicated budget cancellation, selection of an alternative competitor, "
            "or non-pursuit of the project."
        )
    else:
        why_stage = f"Stage: {lead_stage.upper()}. Evaluated based on active opportunity signals."

    # 2. Why this Business Relevance?
    if is_business_relevant:
        why_relevance = (
            f"Business Relevant ({relevance_category.replace('_', ' ').title()}): Involves commercial inquiry, "
            "project collaboration, client communication, or procurement discussion."
        )
    else:
        why_relevance = (
            f"Non-Business ({relevance_category.replace('_', ' ').title()}): Automated system notice, security alert, "
            "transaction receipt, or promotional broadcast. Cleanly isolated from sales pipelines."
        )

    # 3. Why this Pipeline Category?
    pipe = pipeline_category or "none"
    if pipe == "new_leads":
        why_pipeline = "Pipeline: New Leads. Inbound inquiry from a prospective client seeking services or quotation."
    elif pipe == "negotiations":
        why_pipeline = "Pipeline: Negotiations. Active commercial negotiation regarding pricing, discounts, or terms."
    elif pipe == "follow_ups":
        why_pipeline = "Pipeline: Follow-ups. Ongoing discussion awaiting proposal feedback, status update, or next meeting."
    elif pipe == "clarifications":
        why_pipeline = "Pipeline: Clarifications. Clarification of project scope, technical specifications, or milestones."
    elif pipe == "existing_leads":
        why_pipeline = "Pipeline: Existing Leads. Active commercial opportunity with a known business contact."
    elif pipe == "purchase_orders":
        why_pipeline = "Pipeline: Purchase Orders. Formal commercial purchase order received."
    elif pipe == "invoices":
        why_pipeline = "Pipeline: Invoices. Billing invoice or payment notification."
    elif pipe == "needs_review":
        why_pipeline = "Pipeline: Needs Review. Ambiguous signals or low confidence requiring human review."
    else:
        why_pipeline = "Pipeline: None. Non-business communication excluded from sales pipelines."

    # 4. Why this Industry?
    if target_industry and target_industry not in ("Unknown", "Not Applicable"):
        why_industry = (
            f"Target Industry: {target_industry}"
            + (f" ({sub_industry})" if sub_industry else "")
            + f" | Sender Industry: {sender_industry}. "
            "Identified from industry domain keywords and commercial project scope."
        )
    else:
        if not is_business_relevant:
            why_industry = "Industry: Not Applicable (Non-business notification)."
        else:
            why_industry = "Industry: Unknown / Cross-Industry (No specific vertical domain detected in message text)."

    return {
        "why_lead_stage": why_stage,
        "why_relevance": why_relevance,
        "why_pipeline": why_pipeline,
        "why_industry": why_industry,
        "confidence_score": f"{round(confidence * 100)}%",
        "key_signals": signals,
        "context_summary": context_used or "Direct email evaluation",
        "quick_summary": f"Classified as {lead_stage.upper()} ({pipe.replace('_', ' ').title()}) with {round(confidence * 100)}% confidence.",
    }
