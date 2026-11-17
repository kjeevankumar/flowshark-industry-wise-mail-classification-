"""Rule-based email signal detection with negation awareness and conversation context.

Implements:
- Configurable dictionary of phrase signals per intent category.
- Proximity-based negation detection.
- Context-aware intent, relationship, and lead stage resolution.
- Lifecycle preservation: prevents valid stages from resetting to unknown.
- Calibrated confidence scoring with human review triggers.
"""

import re
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple


class RuleSignalResult(NamedTuple):
    """Result of rule-based signal evaluation."""
    intent: str
    relationship: str
    lead_stage: str
    confidence: float
    key_signals: List[str]
    negations: List[str]
    reason: str
    context_used: str = ""


# Negation trigger words
NEGATION_WORDS = {
    "not", "no", "never", "cannot", "can't", "won't", "don't", "doesn't",
    "neither", "nor", "hardly", "scarcely", "barely", "stop", "uninterested"
}

# Automated system senders and broadcast patterns
AUTOMATED_PATTERNS = [
    r"mailer-daemon@",
    r"postmaster@",
    r"no-?reply@",
    r"donotreply@",
    r"notifications?@",
    r"jobmessenger@",
    r"jobnotification@",
    r"alert[s]?@",
    r"newsletter@",
    r"@substack\.com",
    r"@.*\.beehiiv\.com",
    r"delivery status notification",
    r"security alert",
    r"transaction alert",
    r"your job digest",
]


def is_automated_or_broadcast(sender: str = "", subject: str = "") -> bool:
    """Detect whether email is an automated system notification, delivery report, or broadcast newsletter."""
    check_str = f"{sender} {subject}".lower()
    return any(re.search(pat, check_str) for pat in AUTOMATED_PATTERNS)

# Configurable phrase signals mapped to intents
DEFAULT_INTENT_SIGNALS: Dict[str, List[str]] = {
    "new_enquiry": [
        "interested in your services",
        "looking for a website",
        "need a website",
        "i need a website",
        "need a quotation",
        "need a quote",
        "quotation for a",
        "quotation for",
        "rfp",
        "request for proposal",
        "requesting a quotation",
        "request for quotation",
        "request a quote",
        "new project",
        "service enquiry",
        "service inquiry",
        "looking for a vendor",
        "looking for a developer",
        "hire your team",
        "explore collaboration",
        "inquire about your",
        "quote for our",
        "want to build a",
        "seeking a partner for",
        "interested in developing",
        "development enquiry",
        "website development enquiry",
        "new business",
        "service enquiry",
        "service inquiry",
        "how much does it cost",
        "how much will it cost",
        "how much is the cost",
        "what will be the cost",
        "what is the cost",
        "what would be the cost",
        "what is the price",
        "what will be the price",
        "can you do this for us",
        "can you do this",
        "can you help us with",
        "can you help us",
        "can you build this",
        "can you develop this",
        "can you provide this",
        "saw your post",
        "saw your profile",
        "saw your listing",
        "let me know the cost",
        "let me know the price",
        "cost to build",
        "quote for building",
        "pricing for",
        "rates for",
        "price for",
        "enquiry for",
        "inquiry for",
        "need your help",
        "cost?",
        "pricing?",
        "quote?",
    ],
    "negotiation": [
        "reduce the price",
        "discount",
        "budget constraint",
        "tight budget",
        "payment terms",
        "can you offer",
        "final price",
        "negotiate the",
        "lower quotation",
        "best price",
        "reconsider the cost",
        "rate is too high",
        "out of our budget",
        "above our budget",
        "above budget",
        "over our budget",
        "flexible on the price",
        "can you reduce the price",
        "cost is high",
    ],
    "follow_up": [
        "any update",
        "following up",
        "follow up on",
        "checking on",
        "gentle reminder",
        "awaiting your response",
        "status update",
        "checking the proposal",
        "touching base",
        "did you get a chance",
        "waiting to hear back",
        "hope you had time to review",
        "need a update",
        "need an update",
        "need update",
        "i need a update",
        "i need an update",
        "website progress",
        "project progress",
        "work progress",
        "what is my website progress",
        "what is the progress",
        "what is the status",
        "any progress",
        "checking status",
        "checking in",
    ],
    "business_clarification": [
        "please clarify",
        "explain the scope",
        "what is included",
        "delivery timeline",
        "technical requirements",
        "additional features",
        "maintenance details",
        "clarification on",
        "could you clarify",
        "how does it work",
        "scope of work",
        "deliverables and milestones",
        "make some changes",
        "changes to the website",
        "modify the website",
        "website modification",
        "change request",
        "modifications",
    ],
    "purchase_order": [
        "purchase order",
        "po attached",
        "order confirmation",
        "po number",
        "enclosed po",
        "attached purchase order",
        "formal purchase order",
        "approved the quote",
        "approved the proposal",
        "proceed with the project",
        "signing the agreement",
        "master services agreement",
        "selected your proposal",
        "selected flowshark",
        "begin implementation",
        "finalize the agreement",
        "finalize the contract",
    ],
    "invoice": [
        "invoice attached",
        "payment pending",
        "payment confirmation",
        "outstanding amount",
        "bill for services",
        "payment receipt",
        "remittance advice",
        "wire transfer confirmation",
    ],
    "complaint": [
        "not working",
        "dissatisfied with",
        "formal complaint",
        "failed to deliver",
        "unacceptable delay",
        "critical bug",
        "disappointed with the service",
    ],
}


class RuleBasedClassifier:
    """Evaluates text against business signal dictionaries with negation detection and context awareness."""

    def __init__(self, signals_dict: Optional[Dict[str, List[str]]] = None):
        self.signals = signals_dict or DEFAULT_INTENT_SIGNALS

    @staticmethod
    def _is_negated(text: str, match_start: int, window_words: int = 4) -> bool:
        """Check if negation word appears within a small window preceding the match."""
        preceding_text = text[:match_start].lower()
        words = preceding_text.split()
        if not words:
            return False
        preceding_window = words[-window_words:]
        return any(w in NEGATION_WORDS for w in preceding_window)

    def evaluate(
        self,
        cleaned_body: str,
        subject: str = "",
        is_reply: bool = False,
        has_thread_history: bool = False,
        context: Optional[Any] = None,
    ) -> RuleSignalResult:
        """Analyze text, subject, and conversation context for intent, relationship, and stage signals."""
        full_text = f"{subject}\n{cleaned_body}".lower()

        detected_signals: Dict[str, List[str]] = {}
        detected_negations: List[str] = []

        # Scan for each category's phrases
        for category, phrases in self.signals.items():
            for phrase in phrases:
                pattern = r"\b" + re.escape(phrase) + r"\b"
                for match in re.finditer(pattern, full_text):
                    if self._is_negated(full_text, match.start()):
                        detected_negations.append(f"negated: {phrase}")
                    else:
                        detected_signals.setdefault(category, []).append(phrase)

        # Remove duplicate signals per category
        for cat in detected_signals:
            detected_signals[cat] = list(set(detected_signals[cat]))

        # Score categories based on match count and specificity
        best_category = "other"
        highest_score = 0

        for cat, matches in detected_signals.items():
            score = len(matches)
            subject_lower = subject.lower()
            for m in matches:
                if m in subject_lower:
                    score += 2  # Subject line matches get double weight
            if score > highest_score:
                highest_score = score
                best_category = cat

        sender = context.sender_email if context else ""
        if is_automated_or_broadcast(sender=sender, subject=subject):
            return RuleSignalResult(
                intent="other",
                relationship="unknown",
                lead_stage="unknown",
                confidence=0.88,
                key_signals=["automated notification", "system broadcast"],
                negations=[],
                reason="Detected automated system notification, delivery status, or broadcast newsletter format.",
                context_used=context.context_used if context else "",
            )

        # Context-aware fallback: if email has short body like "update", "progress", "status"
        # and there is an active ongoing lead or thread history, classify as follow_up
        has_prior_lead = False
        prior_lead_stage = "unknown"
        contact_relationship = "unknown"
        context_used_desc = ""

        if context:
            has_prior_lead = bool(context.lead_id or (context.prior_emails and context.is_same_sender_continuation))
            prior_lead_stage = context.lead_stage if context.lead_stage != "unknown" else context.contact_lead_stage
            contact_relationship = context.contact_relationship
            context_used_desc = context.context_used

        if best_category == "other" and (has_thread_history or has_prior_lead or is_reply):
            # Check for generic progress or update words in short queries (e.g. "what is my website progress")
            short_query_match = re.search(r"\b(update|progress|status|website|project)\b", full_text)
            if short_query_match and len(cleaned_body.split()) < 40:
                best_category = "follow_up"
                detected_signals.setdefault("follow_up", []).append(f"continuation: {short_query_match.group(1)}")
                highest_score = max(highest_score, 1)

        # Map to relationship and lead stage using multi-dimensional rules
        # 1. Determine Relationship
        if contact_relationship == "existing_customer":
            relationship = "existing_customer"
        elif contact_relationship == "existing_lead" or has_prior_lead or has_thread_history or is_reply:
            if best_category == "purchase_order":
                relationship = "existing_customer"
            else:
                relationship = "existing_lead"
        elif best_category in ["new_enquiry", "business_clarification", "negotiation"]:
            relationship = "new_contact"
        elif best_category in ["purchase_order", "invoice", "complaint"]:
            relationship = "existing_customer"
        else:
            relationship = "unknown"

        # 2. Determine Lead Stage
        # Check if email contains explicit qualification indicators (requirements, scope, timeline, budget)
        has_qualification_signals = any(
            re.search(r"\b" + re.escape(sig) + r"\b", full_text)
            for sig in [
                "delivery timeline", "timeline", "scope of work", "features",
                "requirements", "responsive website", "milestones", "scope",
                "approved the budget", "budget approved", "budget is approved",
                "budget of", "approved budget", "allocated budget", "executive committee",
                "board approved", "selected your proposal", "selected flowshark",
                "onboarding agreement", "master services agreement", "msa",
                "ready to proceed", "schedule a kickoff", "kickoff meeting",
                "decision maker", "procurement approved"
            ]
        )

        # IMPORTANT: Maintain lead lifecycle and never blindly reset a valid existing stage to unknown!
        if best_category == "new_enquiry":
            if has_qualification_signals:
                lead_stage = "qualified"
            elif relationship == "existing_lead" and prior_lead_stage in ["qualified", "proposal_sent", "negotiation"]:
                lead_stage = prior_lead_stage  # Preserved active in-flight deal stage
            else:
                lead_stage = "new"
        elif best_category == "negotiation":
            lead_stage = "negotiation"
        elif best_category == "follow_up":
            if prior_lead_stage != "unknown":
                lead_stage = prior_lead_stage  # Preserved from prior conversation
            elif relationship == "existing_customer":
                lead_stage = "won"
            else:
                lead_stage = "qualified" if (is_reply or has_thread_history) else "proposal_sent"
        elif best_category == "business_clarification":
            if prior_lead_stage in ["qualified", "proposal_sent", "negotiation", "won"]:
                lead_stage = prior_lead_stage
            elif relationship == "existing_customer":
                lead_stage = "won"
            else:
                lead_stage = "qualified"
        elif best_category == "purchase_order":
            lead_stage = "won"
        elif best_category == "invoice":
            lead_stage = "won"
        elif best_category == "complaint":
            lead_stage = prior_lead_stage if prior_lead_stage != "unknown" else "won"
        else:
            # "other" (unrelated, noise, ambiguous)
            # If from an existing customer, preserve customer won status; if active lead, preserve active stage
            if relationship == "existing_customer":
                lead_stage = "won"
            elif has_prior_lead and prior_lead_stage in ["qualified", "proposal_sent", "negotiation"]:
                lead_stage = prior_lead_stage
            else:
                lead_stage = "unknown"

        # 3. Calculate Confidence Score
        # Adhering strictly to section 7 thresholds:
        # >= 0.85: eligible for auto classification
        # 0.60 - 0.84: review recommended
        # < 0.60: needs review
        if highest_score >= 3:
            confidence = 0.90
        elif highest_score == 2:
            confidence = 0.86
        elif highest_score == 1:
            if (has_thread_history or has_prior_lead) and best_category in ["follow_up", "business_clarification", "negotiation"]:
                confidence = 0.88  # Boosted by confirmed conversational history
            else:
                confidence = 0.72
        else:
            # No signals matched
            if best_category == "other":
                confidence = 0.85 if not has_prior_lead else 0.50
            else:
                confidence = 0.45

        matched_phrases = detected_signals.get(best_category, [])
        reason_parts = []
        if matched_phrases:
            reason_parts.append(f"Detected signals: {', '.join(matched_phrases)}.")
        if context_used_desc:
            reason_parts.append(f"Context: {context_used_desc}.")
        if not reason_parts:
            reason_parts.append("No strong business intent signals matched rule patterns.")

        reason = " ".join(reason_parts)

        return RuleSignalResult(
            intent=best_category,
            relationship=relationship,
            lead_stage=lead_stage,
            confidence=round(confidence, 2),
            key_signals=matched_phrases,
            negations=detected_negations,
            reason=reason,
            context_used=context_used_desc,
        )
