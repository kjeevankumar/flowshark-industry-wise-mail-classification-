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
    commercial_intent: str = "none"
    commercial_metadata: Optional[Dict[str, Any]] = None


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


def extract_po_metadata(text: str, subject: str = "") -> Dict[str, Any]:
    """Extract PO reference number, approved amount, terms, and dates from order communications."""
    full_text = f"{subject}\n{text}"
    meta: Dict[str, Any] = {}

    # PO Number pattern
    po_match = re.search(
        r"(?:purchase\s*order(?:\s*number|\s*no|\s*#)?|p\.?o\.?(?:\s*number|\s*no|\s*#)?|po[-#\s:]+)\s*([A-Za-z0-9\-_/]+)",
        full_text,
        re.IGNORECASE,
    )
    if po_match:
        meta["po_number"] = po_match.group(1).strip()

    # Amount extraction
    amt_match = re.search(r"(?:\$|USD|EUR|GBP|₹|INR)\s*([\d,]+(?:\.\d{2})?)", full_text, re.IGNORECASE)
    if not amt_match:
        amt_match = re.search(r"([\d,]+(?:\.\d{2})?)\s*(?:USD|dollars|EUR|euros|INR|rupees)", full_text, re.IGNORECASE)
    if amt_match:
        try:
            meta["amount"] = float(amt_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Payment terms
    terms_match = re.search(
        r"\b(net\s*(?:15|30|45|60|90)|due on receipt|due upon receipt|50%\s*advance|advance payment|milestone[- ]based)\b",
        full_text,
        re.IGNORECASE,
    )
    if terms_match:
        meta["payment_terms"] = terms_match.group(1).strip()

    # Delivery / Effective Date
    date_match = re.search(
        r"(?:delivery\s*date|required\s*by|start\s*date|valid\s*until|date)[:\s]+([A-Za-z0-9,\s\-/]+)",
        full_text,
        re.IGNORECASE,
    )
    if date_match:
        meta["date"] = date_match.group(1).strip()[:30]

    return meta


def extract_payment_metadata(text: str, subject: str = "") -> Dict[str, Any]:
    """Extract UTR/wire transfer number, transaction date, and remitted amount."""
    full_text = f"{subject}\n{text}"
    meta: Dict[str, Any] = {}

    utr_match = re.search(
        r"\b(?:utr(?:\s*number|\s*no|\s*#)?|reference(?:\s*number|\s*no|\s*#)?|ref(?:\s*#)?|txn(?:\s*id|\s*#)?|wire\s*ref(?:\s*#)?|transfer\s*id)[:\s]*([A-Za-z0-9\-_]+)",
        full_text,
        re.IGNORECASE,
    )
    if utr_match:
        ref_val = utr_match.group(1).strip()
        meta["reference_number"] = ref_val
        meta["utr_number"] = ref_val

    amt_match = re.search(r"(?:\$|USD|EUR|GBP|₹|INR)\s*([\d,]+(?:\.\d{2})?)", full_text, re.IGNORECASE)
    if not amt_match:
        amt_match = re.search(r"([\d,]+(?:\.\d{2})?)\s*(?:USD|dollars|EUR|euros|INR|rupees)", full_text, re.IGNORECASE)
    if amt_match:
        try:
            meta["amount"] = float(amt_match.group(1).replace(",", ""))
        except ValueError:
            pass

    date_match = re.search(
        r"(?:transferred\s*on|payment\s*date|dated|transaction\s*date)[:\s]+([A-Za-z0-9,\s\-/]+)",
        full_text,
        re.IGNORECASE,
    )
    if date_match:
        meta["transaction_date"] = date_match.group(1).strip()[:30]

    return meta


def extract_invoice_metadata(text: str, subject: str = "") -> Dict[str, Any]:
    """Extract invoice reference number, PO number, amount, GSTIN, and requested update details."""
    full_text = f"{subject}\n{text}"
    meta: Dict[str, Any] = {}

    inv_match = re.search(
        r"\b(?:invoice(?:\s*number|\s*no|\s*#)?|inv[-#\s:]+|bill(?:\s*no|\s*#)?)\s*([A-Za-z0-9\-_/]+)",
        full_text,
        re.IGNORECASE,
    )
    if inv_match:
        meta["invoice_number"] = inv_match.group(1).strip()

    po_match = re.search(
        r"(?:purchase\s*order(?:\s*number|\s*no|\s*#)?|p\.?o\.?(?:\s*number|\s*no|\s*#)?|po[-#\s:]+)\s*([A-Za-z0-9\-_/]+)",
        full_text,
        re.IGNORECASE,
    )
    if po_match:
        meta["po_number"] = po_match.group(1).strip()

    amt_match = re.search(r"(?:\$|USD|EUR|GBP|₹|INR)\s*([\d,]+(?:\.\d{2})?)", full_text, re.IGNORECASE)
    if not amt_match:
        amt_match = re.search(r"([\d,]+(?:\.\d{2})?)\s*(?:USD|dollars|EUR|euros|INR|rupees)", full_text, re.IGNORECASE)
    if amt_match:
        try:
            meta["amount"] = float(amt_match.group(1).replace(",", ""))
        except ValueError:
            pass

    gst_match = re.search(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z0-9]{1}Z[A-Z0-9]{1}\b", full_text)
    if gst_match:
        meta["gst_number"] = gst_match.group(0)

    if "address" in full_text.lower():
        meta["update_type"] = "billing_address"
    elif gst_match or "gst" in full_text.lower():
        meta["update_type"] = "gst_correction"
    elif "amount" in full_text.lower() or "dispute" in full_text.lower():
        meta["update_type"] = "amount_correction"

    return meta

# Configurable phrase signals mapped to intents
DEFAULT_INTENT_SIGNALS: Dict[str, List[str]] = {
    "new_enquiry": [
        "interested in your services",
        "came across your services",
        "came across your company",
        "came across your profile",
        "researching enterprise",
        "evaluating service providers",
        "evaluating providers",
        "evaluating vendors",
        "evaluating partners",
        "evaluating solutions",
        "standard service deck",
        "service deck",
        "company deck",
        "case studies of similar",
        "case studies",
        "discovery call",
        "30-minute discovery call",
        "30 minute discovery call",
        "availability for a discovery call",
        "availability for a",
        "availability for a call",
        "schedule a discovery call",
        "schedule a call",
        "schedule a demo",
        "schedule a meeting",
        "book a call",
        "book a demo",
        "introductory call",
        "intro call",
        "demo call",
        "looking forward to hearing from you",
        "looking forward to hearing",
        "migrate our legacy",
        "migrate our",
        "migrate to aws",
        "migration partner",
        "cloud infrastructure partners",
        "devops automation",
        "looking for a website",
        "need a website",
        "i need a website",
        "need a quotation",
        "need a quote",
        "quotation for a",
        "quotation for",
        "rfp",
        "rfq",
        "request for proposal",
        "requesting a quotation",
        "request for quotation",
        "request a quote",
        "new project",
        "service enquiry",
        "service inquiry",
        "looking for a vendor",
        "looking for a developer",
        "looking for a partner",
        "looking for an agency",
        "looking for a provider",
        "hire your team",
        "explore collaboration",
        "inquire about your",
        "quote for our",
        "want to build a",
        "seeking a partner for",
        "seeking a partner",
        "interested in developing",
        "development enquiry",
        "website development enquiry",
        "new business",
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
        "commercial terms",
        "finalize commercial terms",
        "finalize terms",
        "commercial proposal",
        "proposal review",
        "commercial proposal review",
        "review commercial terms",
        "revised commercial proposal",
        "commercial terms discussion",
        "commercial terms are feasible",
        "exceeds our allocated",
        "exceeds our budget",
        "exceeds budget",
        "15% discount",
        "discount on the",
        "quarterly milestones",
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
        "flexible on pricing",
        "can you reduce the price",
        "cost is high",
        "finalize the contract",
        "move forward with the agreement",
    ],
    "follow_up": [
        "any update",
        "following up",
        "follow up on",
        "follow up on the",
        "follow up on our",
        "wanted to quickly follow up",
        "quickly follow up",
        "checking on",
        "checking in on",
        "checking in regarding",
        "gentle reminder",
        "awaiting your response",
        "status update",
        "checking the proposal",
        "touching base",
        "did you get a chance",
        "did you get a chance to review",
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
        "solution demo",
        "pricing estimate",
        "review session",
        "piloting your software",
        "pilot rollout",
        "30-day pilot",
        "next onboarding steps",
        "looking forward to your update",
        "latest status",
        "share the latest status",
        "please share the latest status",
        "share the status",
        "please share status",
        "progressing well",
        "project development is progressing",
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
        "clarification needed",
        "requested clarification",
        "could you confirm whether",
        "confirm whether",
        "compliance board",
        "master services agreement",
        "msa",
        "sla guarantee",
        "uptime sla",
        "resolution sla",
        "soc2",
        "aes-256",
        "data residency",
        "technical clarifications",
        "security team has requested",
    ],
    "purchase_order": [
        "purchase order",
        "po attached",
        "order confirmation",
        "po number",
        "po-",
        "po#",
        "enclosed po",
        "attached purchase order",
        "formal purchase order",
        "official purchase order",
        "purchase order issued",
        "issuing the purchase order",
        "please accept our po",
        "approved the quote",
        "approved your quote",
        "approved quote",
        "approved the proposal",
        "selected your proposal",
        "quoting the po number",
        "issuing po",
    ],
    "invoice_request": [
        "send us the invoice",
        "share the invoice",
        "requesting an invoice",
        "requesting the invoice",
        "send the invoice for",
        "send invoice for",
        "share tax invoice",
        "share the tax invoice",
        "please share the tax invoice",
        "please share the invoice",
        "kindly share the tax invoice",
        "kindly share the invoice",
        "request for tax invoice",
        "request for invoice",
        "requesting tax invoice",
        "tax invoice against",
        "tax invoice against po",
        "tax invoice against purchase order",
        "tax invoice for the project",
        "duplicate invoice copy",
        "resend invoice copy",
        "duplicate invoice",
        "invoice for completed work",
        "post-completion billing",
        "raise the invoice",
        "bill us for",
        "send invoice",
        "please invoice us",
        "kindly share the invoice",
        "share the invoice copy",
        "need the invoice",
        "send across the invoice",
        "forward the invoice copy",
        "include our po number on the invoice",
        "include our po on the invoice",
        "kindly include our po number",
    ],
    "invoice_update": [
        "correct the invoice",
        "update the invoice",
        "revised invoice",
        "revision of invoice",
        "gst number correction",
        "gst correction",
        "gst correction on invoice",
        "gst number on invoice is incorrect",
        "gst number is incorrect",
        "gst number on invoice",
        "gst is incorrect",
        "on invoice is incorrect",
        "invoice is incorrect",
        "gstin correction",
        "tax id correction",
        "update gst",
        "correct gst",
        "change billing address",
        "billing address update",
        "billing address change",
        "update billing entity",
        "incorrect invoice amount",
        "wrong amount on invoice",
        "invoice amount is incorrect",
        "missing po number on invoice",
        "missing po on the invoice",
        "update invoice #",
        "reissue the invoice",
        "re-issue the invoice",
        "modify the invoice",
        "amended invoice",
    ],
    "payment_remittance": [
        "remittance advice",
        "payment remittance",
        "remittance",
        "payment advice",
        "we transferred",
        "transferred",
        "utr",
        "utr number",
        "payment has been processed",
        "payment transferred",
        "transferred via wire",
        "transferred to your account",
        "wire transfer was processed",
        "wire transfer confirmation",
        "funds have been transferred",
        "neft/rtgs",
        "neft ref",
        "rtgs ref",
        "bank reference number",
        "payment receipt attached",
        "proof of payment",
        "payment confirmation receipt",
        "attached remittance",
        "remittance advice attached",
        "payment transfer reference",
    ],
    "payment_follow_up": [
        "confirm receipt of payment",
        "confirm payment receipt",
        "status of pending payment",
        "pending payment status",
        "payment status update",
        "when will payment be credited",
        "expected payment date",
        "payment will be released",
        "payment scheduled for",
        "accounts will release payment",
        "confirm if payment was received",
        "did you receive the payment",
        "status of payment release",
        "payment release update",
        "payment follow-up",
        "payment follow up",
        "pending payment will be processed",
        "when will payment be processed",
        "when will our payment be processed",
        "when our pending payment will be processed",
        "payment will be processed",
        "pending payment",
        "status of our payment",
        "status of payment",
    ],
    "payment_dispute": [
        "dispute the invoice",
        "disputing invoice",
        "dispute charge",
        "dispute on invoice",
        "dispute on invoice amount",
        "invoice amount dispute",
        "invoice amount does not match",
        "amount does not match",
        "does not match our agreed quotation",
        "does not match agreed quotation",
        "does not match quotation",
        "does not match our quote",
        "does not match quote",
        "incorrect charge",
        "duplicate bill",
        "duplicate billing",
        "duplicate invoice charge",
        "we were overcharged",
        "tax calculation is incorrect",
        "tax discrepancy",
        "tax rate is wrong",
        "withholding payment until",
        "disputed amount",
        "billing discrepancy",
        "billed incorrectly",
        "discrepancy on invoice",
        "erroneous charge",
    ],
    "invoice": [
        "invoice attached",
        "bill for services",
        "payment receipt",
        "statement of account",
        "quarterly audit records",
        "attached invoice",
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
    "existing_lead": [
        "weekly sync",
        "following up on our weekly sync",
        "our weekly sync",
        "ongoing deployment",
        "ongoing project",
        "ongoing engagement",
        "current engagement",
        "initial rollout",
        "initial rollout is progressing",
        "phase 2",
        "scope phase 2",
        "phase 2 feature additions",
        "phase 2 additions",
        "phase 2 rollout",
        "addendum to our existing agreement",
        "addendum to our agreement",
        "addendum to the agreement",
        "additional hours needed",
        "additional hours",
        "scope expansion",
        "existing agreement",
        "existing contract",
        "existing account",
        "existing client",
        "project update & phase 2",
        "project update",
        "sprint update",
        "status of our ongoing",
        "progress of our ongoing",
        "account review",
        "quarterly business review",
        "qbr",
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

        # Disambiguate Quotation Request vs Invoice Request:
        # Quotation requests ("need a quote", "pricing estimate", "how much does it cost") must NEVER be classified as invoice_request
        quotation_signals = [
            "need a quote", "need a quotation", "quotation for", "quote for",
            "pricing estimate", "how much does it cost", "how much will it cost",
            "request for quote", "request for quotation", "requesting a quote", "rates for"
        ]
        has_quote_request = any(qs in full_text for qs in quotation_signals)
        explicit_invoice_words = [
            "send invoice", "share invoice", "tax invoice against", "tax invoice for",
            "invoice copy", "duplicate invoice", "raise invoice", "post-completion billing"
        ]
        has_explicit_invoice = any(iw in full_text for iw in explicit_invoice_words)

        if best_category in ["invoice_request", "invoice"] and has_quote_request and not has_explicit_invoice:
            best_category = "new_enquiry"
            detected_signals.setdefault("new_enquiry", []).append("quotation request (disambiguated from invoice)")

        # Disambiguate Purchase Order vs Invoice Request against existing PO:
        # When customer asks to send/share tax invoice against an existing PO, this is an Invoice Request, NOT a new PO!
        invoice_request_phrases = [
            "tax invoice against", "share the tax invoice", "share tax invoice",
            "request for tax invoice", "request for invoice", "send us the tax invoice",
            "send the tax invoice", "send invoice against", "include our po number on the invoice",
            "kindly include our po number", "tax invoice against po", "invoice against po"
        ]
        if (best_category == "purchase_order" or "purchase_order" in detected_signals) and any(p in full_text for p in invoice_request_phrases):
            best_category = "invoice_request"
            detected_signals.setdefault("invoice_request", []).append("invoice request against po (disambiguated)")

        # Commercial metadata and intent resolution
        commercial_intent = "none"
        commercial_meta: Dict[str, Any] = {}

        if best_category == "purchase_order":
            commercial_intent = "purchase_order"
            commercial_meta = extract_po_metadata(cleaned_body, subject)
        elif best_category == "invoice_request":
            commercial_intent = "invoice_request"
            commercial_meta = extract_invoice_metadata(cleaned_body, subject)
        elif best_category == "invoice_update":
            commercial_intent = "invoice_update"
            commercial_meta = extract_invoice_metadata(cleaned_body, subject)
        elif best_category == "payment_remittance":
            commercial_intent = "payment_remittance"
            commercial_meta = extract_payment_metadata(cleaned_body, subject)
        elif best_category == "payment_follow_up":
            commercial_intent = "payment_follow_up"
            commercial_meta = extract_payment_metadata(cleaned_body, subject)
        elif best_category == "payment_dispute":
            commercial_intent = "payment_dispute"
            commercial_meta = extract_invoice_metadata(cleaned_body, subject)
        elif best_category == "invoice":
            # Inbound invoices default to invoice_request or payment_remittance; NEVER invoice_issued
            if any(term in full_text for term in ["utr", "wire", "remittance", "transferred", "paid"]):
                commercial_intent = "payment_remittance"
                best_category = "payment_remittance"
                commercial_meta = extract_payment_metadata(cleaned_body, subject)
            else:
                commercial_intent = "invoice_request"
                best_category = "invoice_request"
                commercial_meta = extract_invoice_metadata(cleaned_body, subject)

        # Map to relationship and lead stage using multi-dimensional rules
        # 1. Determine Relationship
        if contact_relationship == "existing_customer":
            relationship = "existing_customer"
        elif contact_relationship == "existing_lead" or has_prior_lead or has_thread_history or is_reply:
            if best_category == "purchase_order":
                relationship = "existing_customer" if contact_relationship == "existing_customer" else "existing_lead"
            else:
                relationship = "existing_lead"
        elif best_category in ["new_enquiry", "business_clarification", "negotiation"]:
            relationship = "new_contact"
        elif best_category == "existing_lead":
            relationship = "existing_lead"
        elif best_category in ["purchase_order", "invoice_request", "invoice_update", "payment_remittance", "payment_follow_up", "payment_dispute", "complaint"]:
            relationship = "existing_customer" if contact_relationship == "existing_customer" else "existing_lead"
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
        # CRITICAL RULE: Neither PO keywords nor payment remittances should automatically mark an opportunity WON!
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
            # Do NOT mark Won solely because of a PO keyword or number!
            if prior_lead_stage in ["negotiation", "proposal_sent", "qualified"]:
                lead_stage = prior_lead_stage
            elif relationship == "existing_customer":
                lead_stage = "won"
            else:
                lead_stage = "negotiation"
        elif best_category in ["invoice_request", "invoice_update", "payment_remittance", "payment_follow_up", "payment_dispute"]:
            # Remittances and billing requests do NOT mark Won!
            if prior_lead_stage in ["qualified", "proposal_sent", "negotiation", "won"]:
                lead_stage = prior_lead_stage
            elif relationship == "existing_customer":
                lead_stage = "won"
            else:
                lead_stage = "qualified"
        elif best_category == "complaint":
            lead_stage = prior_lead_stage if prior_lead_stage != "unknown" else "won"
        elif best_category == "existing_lead":
            lead_stage = prior_lead_stage if prior_lead_stage not in ["unknown", "lost"] else "qualified"
        else:
            # "other" (unrelated, noise, ambiguous)
            if relationship == "existing_customer":
                lead_stage = "won"
            elif has_prior_lead and prior_lead_stage in ["qualified", "proposal_sent", "negotiation"]:
                lead_stage = prior_lead_stage
            else:
                lead_stage = "unknown"

        # 3. Calculate Confidence Score
        if highest_score >= 3:
            confidence = 0.90
        elif highest_score == 2:
            confidence = 0.86
        elif highest_score == 1:
            if (has_thread_history or has_prior_lead) and best_category in ["follow_up", "business_clarification", "negotiation", "payment_follow_up"]:
                confidence = 0.88
            else:
                confidence = 0.75
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
            commercial_intent=commercial_intent,
            commercial_metadata=commercial_meta,
        )
