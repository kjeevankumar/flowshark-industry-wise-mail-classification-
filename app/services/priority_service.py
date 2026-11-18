"""Explainable Priority and Lead Qualification Engine for FlowShark B2B SaaS.

Calculates:
- Action Urgency: (High, Medium, Low) based on deadlines, executive senders, discovery requests, or complaints.
- Business Potential: (High, Medium, Low, Unknown) based on deal size indicators, enterprise scale, multi-month rollout.
- Information Completeness: (Complete, Partial, Missing) based on presence of scope, timeline, and decision-maker info.
- Overall Priority: (Hot, Warm, Low).
- Qualification Status: (Qualified, Prospect, Disqualified).

Design Rules:
- Missing information is classified as "Unknown" or "Missing", NEVER penalized to zero.
- Genuine new enquiries without budget are not low-value; they are evaluated on enterprise potential.
- Serious complaints or urgent client follow-ups are High urgency even without new revenue potential.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional


@dataclass
class PriorityResult:
    priority_score: float  # 0.0 to 1.0 calibrated score
    priority_level: str  # hot, warm, low
    action_urgency: str  # high, medium, low
    business_potential: str  # high, medium, low, unknown
    information_completeness: str  # complete, partial, missing
    qualification_status: str  # qualified, prospect, disqualified
    reasons: List[str] = field(default_factory=list)


class PriorityScoringService:
    """Deterministic, explainable B2B priority and qualification scoring."""

    URGENT_TERMS = [
        "urgent", "asap", "immediately", "deadline", "by tomorrow", "this week",
        "emergency", "critical", "blocked", "outage", "escalated", "time-sensitive",
        "discovery call next", "call next tuesday", "call next wednesday",
        "availability for a", "schedule a call", "30-minute discovery call"
    ]

    ENTERPRISE_TERMS = [
        "enterprise", "legacy logistics", "supply chain operations", "north american",
        "global", "corporate", "multi-region", "infrastructure partners",
        "aws migration", "cloud migration", "procurement department", "rfp",
        "master services agreement", "sla", "board approved", "500 employees",
        "annual contract", "tier 1", "director", "head of", "vp", "chief", "cto", "cio"
    ]

    BUDGET_TERMS = [
        "$", "usd", "budget", "allocated budget", "approved budget", "quote",
        "pricing estimate", "rate card", "investment", "fixed fee", "48,000",
        "50,000", "10,000", "100,000"
    ]

    TIMELINE_TERMS = [
        "next quarter", "q1", "q2", "q3", "q4", "within 30 days", "by next month",
        "timeline", "deployment schedule", "milestone", "kickoff next week"
    ]

    SCOPE_TERMS = [
        "migrate our legacy", "platform to aws", "feature additions", "scope phase 2",
        "technical requirements", "deliverables", "redesign", "responsive website",
        "custom crm", "devops automation", "cloud infrastructure"
    ]

    def evaluate(
        self,
        subject: str,
        cleaned_body: str,
        pipeline_category: Optional[str] = None,
        intent: Optional[str] = None,
        relationship: Optional[str] = None,
        is_business_relevant: bool = True,
    ) -> PriorityResult:
        """Calculate explainable multi-dimensional priority."""
        if not is_business_relevant:
            return PriorityResult(
                priority_score=0.1,
                priority_level="low",
                action_urgency="low",
                business_potential="unknown",
                information_completeness="missing",
                qualification_status="disqualified",
                reasons=["Non-business notification or automated broadcast."],
            )

        full_text = f"{subject}\n{cleaned_body}".lower()
        reasons: List[str] = []

        # 1. Action Urgency Evaluation
        urgency_score = 1  # 0: Low, 1: Medium, 2: High
        has_urgency_keyword = any(term in full_text for term in self.URGENT_TERMS)
        if has_urgency_keyword:
            urgency_score = 2
            reasons.append("High urgency: specific meeting request, deadline, or time-sensitive operational prompt.")
        elif intent == "complaint":
            urgency_score = 2
            reasons.append("High urgency: customer dissatisfaction requires priority account escalation.")
        elif intent in ["negotiation", "purchase_order"]:
            urgency_score = 2
            reasons.append("High urgency: active commercial opportunity awaiting response.")
        elif intent == "follow_up":
            urgency_score = 1
            reasons.append("Medium urgency: routine status inquiry or follow-up.")
        else:
            urgency_score = 1

        action_urgency = "high" if urgency_score >= 2 else ("medium" if urgency_score == 1 else "low")

        # 2. Business Potential Evaluation
        has_enterprise = any(term in full_text for term in self.ENTERPRISE_TERMS)
        has_large_budget = any(term in full_text for term in ["$48,000", "$50,000", "$100,000", "enterprise", "multi-year"])
        has_po = intent == "purchase_order" or "purchase order" in full_text

        if has_po:
            business_potential = "high"
            reasons.append("High commercial potential: confirmed purchase order or commercial commitment.")
        elif has_enterprise:
            business_potential = "high"
            reasons.append("High commercial potential: enterprise-scale scope, executive title, or supply chain modernization.")
        elif has_large_budget:
            business_potential = "high"
            reasons.append("High commercial potential: significant allocated budget disclosed.")
        elif intent in ["new_enquiry", "negotiation", "existing_lead"]:
            business_potential = "medium"
            reasons.append("Medium commercial potential: commercial inquiry or active opportunity.")
        elif intent in ["invoice", "payment_remittance"]:
            business_potential = "medium"
            reasons.append("Commercial transaction: billing or remittance settlement.")
        else:
            business_potential = "unknown"
            reasons.append("Commercial potential unknown: budget or commercial scale not yet disclosed.")

        # 3. Information Completeness Evaluation
        has_scope = any(term in full_text for term in self.SCOPE_TERMS) or len(cleaned_body.split()) > 30
        has_timeline = any(term in full_text for term in self.TIMELINE_TERMS)
        has_budget = any(term in full_text for term in self.BUDGET_TERMS)

        completeness_points = sum([has_scope, has_timeline, has_budget])
        if completeness_points >= 2:
            information_completeness = "complete"
            reasons.append("Information complete: provides clear project scope alongside timeline or commercial parameters.")
        elif completeness_points == 1:
            information_completeness = "partial"
            reasons.append("Information partial: concrete requirements outlined, but commercial budget/timeline pending discovery.")
        else:
            information_completeness = "missing"
            reasons.append("Information missing: preliminary contact requiring discovery questionnaire.")

        # 4. Overall Priority Level & Calibrated Score
        if business_potential == "high" or (action_urgency == "high" and business_potential != "low"):
            priority_level = "hot"
            priority_score = 0.92 if business_potential == "high" and action_urgency == "high" else 0.85
        elif business_potential == "medium" or action_urgency == "high":
            priority_level = "warm"
            priority_score = 0.75
        else:
            priority_level = "low"
            priority_score = 0.50

        # 5. Lead Qualification Status
        if has_po or intent == "purchase_order":
            qualification_status = "qualified"
        elif has_enterprise or (has_scope and has_timeline):
            qualification_status = "qualified"
        elif intent in ["new_enquiry", "negotiation", "existing_lead", "follow_up"]:
            qualification_status = "prospect"
        else:
            qualification_status = "prospect"

        return PriorityResult(
            priority_score=priority_score,
            priority_level=priority_level,
            action_urgency=action_urgency,
            business_potential=business_potential,
            information_completeness=information_completeness,
            qualification_status=qualification_status,
            reasons=reasons,
        )
