"""Business Email Relevance Detection Layer for FlowShark.

Separates incoming emails into business vs non-business categories before
lead classification or CRM pipeline assignment.

Categories:
- business_enquiry
- business_conversation
- customer_support
- purchase_commercial
- internal_communication
- account_security_notification
- system_notification
- automated_notification
- newsletter_marketing
- spam_irrelevant
- unknown_review
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class RelevanceResult:
    """Structured decision of business email relevance detection."""
    relevance_category: str
    is_business_relevant: bool
    confidence: float
    reason: str
    evidence: List[str] = field(default_factory=list)
    needs_review: bool = False


# Known automated non-business sender patterns (supporting signal)
AUTOMATED_NOTIFICATION_SENDERS = [
    re.compile(r"no-?reply[-a-z0-9._]*@", re.IGNORECASE),
    re.compile(r"noreply[-a-z0-9._]*@", re.IGNORECASE),
    re.compile(r"donotreply[-a-z0-9._]*@", re.IGNORECASE),
    re.compile(r"notifications?@", re.IGNORECASE),
    re.compile(r"alert[s]?@", re.IGNORECASE),
    re.compile(r"newsletter@", re.IGNORECASE),
    re.compile(r"updates?@", re.IGNORECASE),
    re.compile(r"recommendations?@", re.IGNORECASE),
    re.compile(r"mailer-daemon@", re.IGNORECASE),
    re.compile(r"postmaster@", re.IGNORECASE),
    re.compile(r"accounts\.google\.com", re.IGNORECASE),
    re.compile(r"@substack\.com", re.IGNORECASE),
    re.compile(r"@mail\.beehiiv\.com", re.IGNORECASE),
    re.compile(r"@medium\.com", re.IGNORECASE),
    re.compile(r"@mail\.cerebralvalley\.ai", re.IGNORECASE),
    re.compile(r"jobalert|indeed\.com|glassdoor\.com|naukri\.com|jobs2web\.com|talent-community\.com|hireft\.com|thesmartbridge\.com|pinterest\.com|wellfound\.com|alignerr\.com|unstop\.news|qemailserver\.com", re.IGNORECASE),
]

# Account Security Notification Patterns
SECURITY_ALERT_SUBJECT_PATTERNS = [
    re.compile(r"\bsecurity alert\b", re.IGNORECASE),
    re.compile(r"\bcritical security alert\b", re.IGNORECASE),
    re.compile(r"\b2-step verification\b", re.IGNORECASE),
    re.compile(r"\btwo-factor authentication\b", re.IGNORECASE),
    re.compile(r"\bapp password created\b", re.IGNORECASE),
    re.compile(r"\bpassword reset\b", re.IGNORECASE),
    re.compile(r"\baccount recovered\b", re.IGNORECASE),
    re.compile(r"\bnew sign-in\b", re.IGNORECASE),
    re.compile(r"\bverify your identity\b", re.IGNORECASE),
    re.compile(r"\bshared some google account data\b", re.IGNORECASE),
    re.compile(r"\bfinish setting up your windows with google\b", re.IGNORECASE),
    re.compile(r"\baccess to ai features\b", re.IGNORECASE),
    re.compile(r"\bterms of service\b", re.IGNORECASE),
    re.compile(r"\bone-time password\b", re.IGNORECASE),
    re.compile(r"\botp\b", re.IGNORECASE),
    re.compile(r"\blogin from new device\b", re.IGNORECASE),
    re.compile(r"\bsuspicious activity\b", re.IGNORECASE),
    re.compile(r"\bunauthorized access\b", re.IGNORECASE),
]

# System & Infrastructure Notification Patterns
SYSTEM_NOTIFICATION_PATTERNS = [
    re.compile(r"\bdelivery status notification\b", re.IGNORECASE),
    re.compile(r"\bundelivered mail\b", re.IGNORECASE),
    re.compile(r"\bmail delivery failure\b", re.IGNORECASE),
    re.compile(r"\bdomain renewal\b", re.IGNORECASE),
    re.compile(r"\bssl certificate\b", re.IGNORECASE),
    re.compile(r"\bstorage quota\b", re.IGNORECASE),
    re.compile(r"\bgmail storage\b", re.IGNORECASE),
    re.compile(r"\baccount storage limit\b", re.IGNORECASE),
    re.compile(r"\bdeployment (?:failed|succeeded|live)\b", re.IGNORECASE),
    re.compile(r"\bbuild (?:failed|succeeded|error)\b", re.IGNORECASE),
    re.compile(r"\brun (?:failed|succeeded)\b", re.IGNORECASE),
    re.compile(r"\b(?:amazon web services|aws|google cloud|stripe|cloudflare|vercel|render|digitalocean|github|atlassian)\s*(?:invoice|bill|receipt|monthly statement|payment receipt)\b", re.IGNORECASE),
    re.compile(r"\b(?:invoice|receipt|billing|statement)\s*(?:is\s*)?available\b", re.IGNORECASE),
    re.compile(r"\bcloud\s*billing\b", re.IGNORECASE),
]

# Automated Transactional & Notification Patterns (Banks, Forms, Calendars)
AUTOMATED_TRANSACTION_PATTERNS = [
    re.compile(r"\btransaction alert\b", re.IGNORECASE),
    re.compile(r"\bupi/imps/mb transaction\b", re.IGNORECASE),
    re.compile(r"\batm cash withdrawal\b", re.IGNORECASE),
    re.compile(r"\bcard transaction\b", re.IGNORECASE),
    re.compile(r"\bthanks for filling out this form\b", re.IGNORECASE),
    re.compile(r"\bgoogle forms\b", re.IGNORECASE),
    re.compile(r"\binvitation:\s*", re.IGNORECASE),
    re.compile(r"\baccepted:\s*", re.IGNORECASE),
    re.compile(r"\bdeclined:\s*", re.IGNORECASE),
]

# Newsletter & Marketing Patterns
NEWSLETTER_PATTERNS = [
    re.compile(r"\bmarket charcha\b", re.IGNORECASE),
    re.compile(r"\bweekly digest\b", re.IGNORECASE),
    re.compile(r"\bdaily digest\b", re.IGNORECASE),
    re.compile(r"\bnewsletter\b", re.IGNORECASE),
    re.compile(r"\bmarket indices\b", re.IGNORECASE),
    re.compile(r"\bunsubscribe\b", re.IGNORECASE),
    re.compile(r"\bview in browser\b", re.IGNORECASE),
    re.compile(r"\bview this post on the web\b", re.IGNORECASE),
    re.compile(r"\bleetcode pattern\b", re.IGNORECASE),
    re.compile(r"\bsensex\b", re.IGNORECASE),
    re.compile(r"\bjob alert\b", re.IGNORECASE),
    re.compile(r"\bjobs in\b", re.IGNORECASE),
    re.compile(r"\bapply now\b", re.IGNORECASE),
    re.compile(r"\bnew opportunity has arrived\b", re.IGNORECASE),
    re.compile(r"\brecommendations\b", re.IGNORECASE),
    re.compile(r"\bopen / forget / repeat\b", re.IGNORECASE),
    re.compile(r"\bthis is peak\b", re.IGNORECASE),
    re.compile(r"\bfor you\. apply now\b", re.IGNORECASE),
]

# Business Intent Signals (To ensure genuine business communications from tech domains are NOT blocked)
BUSINESS_BUYING_SIGNALS = [
    re.compile(r"\b(?:enquiry|inquiry|rfp|request for proposal)\b", re.IGNORECASE),
    re.compile(r"\b(?:looking for|need|want|interested in|seeking)\s+(?:a|an|[a-z0-9-]+\s+){0,4}(?:website|software|app|solution|developer|company|vendor|team|services|system|platform|management|portal|integration|contractor|supplier)\b", re.IGNORECASE),
    re.compile(r"\b(?:request(?:ing)?|need|want|share|require)\s+(?:a|an|the|[a-z0-9-]+\s+){0,3}(?:quotation|quote|proposal|pricing|rate card|estimate|rates|catalog)\b", re.IGNORECASE),
    re.compile(r"\b(?:website|software|mobile app|custom|system)\s+(?:development|design|enquiry|inquiry)\b", re.IGNORECASE),
    re.compile(r"\b(?:quotation|quote|proposal)\s+for\b", re.IGNORECASE),
    re.compile(r"\bnew business enquiry\b", re.IGNORECASE),
    re.compile(r"\bhire your team\b", re.IGNORECASE),
    re.compile(r"\bexplore collaboration\b", re.IGNORECASE),
    re.compile(r"\bdevelop a website for our business\b", re.IGNORECASE),
]

PURCHASE_ORDER_PATTERNS = [
    re.compile(r"\bpurchase order\b", re.IGNORECASE),
    re.compile(r"\bpo\s*(?:#\s*|[-_]\s*|[0-9])[0-9a-z_-]*\b", re.IGNORECASE),
    re.compile(r"\battached\s+(?:is\s+)?(?:our\s+)?purchase order\b", re.IGNORECASE),
    re.compile(r"\bconfirm(?:ing)?\s+(?:the\s+)?order\b", re.IGNORECASE),
]

INVOICE_PATTERNS = [
    re.compile(r"\binvoice\s*#?\s*[a-z0-9-]{3,}\b", re.IGNORECASE),
    re.compile(r"\bpayment due\b", re.IGNORECASE),
    re.compile(r"\bplease find attached invoice\b", re.IGNORECASE),
    re.compile(r"\bbill for services\b", re.IGNORECASE),
]


class BusinessRelevanceDetector:
    """Evaluates incoming email for business relevance and classifies into relevance categories."""

    def evaluate(
        self,
        sender: str,
        subject: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> RelevanceResult:
        """Analyze email metadata, headers, sender, and content to classify relevance."""
        sender_clean = sender.strip().lower() if sender else ""
        subject_clean = subject.strip() if subject else ""
        text_body = (body_text or "").strip()
        combined_text = f"{subject_clean}\n{text_body}"
        evidence: List[str] = []

        # -------------------------------------------------------------------------
        # Priority Check 1: Check for explicit Buying / Business Enquiry signals first
        # (A genuine enquiry from Google, Microsoft, or any domain must NOT be blocked)
        # -------------------------------------------------------------------------
        is_automated_sender = any(s.search(sender_clean) for s in AUTOMATED_NOTIFICATION_SENDERS)

        for idx, pat in enumerate(BUSINESS_BUYING_SIGNALS):
            m = pat.search(combined_text)
            if m:
                # If automated broadcast sender, ignore standalone single word "inquiry" in articles
                if idx == 0 and is_automated_sender:
                    continue
                # Confirm it is NOT a security alert or terms notice
                if not any(sec.search(subject_clean) for sec in SECURITY_ALERT_SUBJECT_PATTERNS):
                    evidence.append(f"Business buying signal: '{m.group(0)}'")
                    return RelevanceResult(
                        relevance_category="business_enquiry",
                        is_business_relevant=True,
                        confidence=0.95,
                        reason="Explicit business inquiry or service quotation request detected.",
                        evidence=evidence,
                        needs_review=False,
                    )

        # Check for formal Purchase Order signals
        for pat in PURCHASE_ORDER_PATTERNS:
            m = pat.search(combined_text)
            if m:
                evidence.append(f"Purchase order indicator: '{m.group(0)}'")
                return RelevanceResult(
                    relevance_category="purchase_commercial",
                    is_business_relevant=True,
                    confidence=0.94,
                    reason="Commercial purchase order or formal order confirmation detected.",
                    evidence=evidence,
                    needs_review=False,
                )

        # Check for formal Invoice signals (only if NOT an automated system/notification sender)
        if not is_automated_sender and not any(sec.search(subject_clean) for sec in SYSTEM_NOTIFICATION_PATTERNS):
            for pat in INVOICE_PATTERNS:
                m = pat.search(combined_text)
                if m and not any(sec.search(subject_clean) for sec in AUTOMATED_TRANSACTION_PATTERNS):
                    evidence.append(f"Invoice indicator: '{m.group(0)}'")
                    return RelevanceResult(
                        relevance_category="purchase_commercial",
                        is_business_relevant=True,
                        confidence=0.92,
                        reason="Commercial invoice or billing statement detected.",
                        evidence=evidence,
                        needs_review=False,
                    )

        # -------------------------------------------------------------------------
        # Priority Check 2: Account Security Notifications
        # -------------------------------------------------------------------------
        for pat in SECURITY_ALERT_SUBJECT_PATTERNS:
            m = pat.search(subject_clean) or pat.search(text_body[:500])
            if m:
                evidence.append(f"Security notification signal: '{m.group(0)}'")
                if any(s.search(sender_clean) for s in AUTOMATED_NOTIFICATION_SENDERS):
                    evidence.append(f"Automated security sender: '{sender_clean}'")
                return RelevanceResult(
                    relevance_category="account_security_notification",
                    is_business_relevant=False,
                    confidence=0.98,
                    reason="Automated account security alert, 2FA, password, or security notification.",
                    evidence=evidence,
                    needs_review=False,
                )

        # -------------------------------------------------------------------------
        # Priority Check 3: System & Infrastructure Notifications
        # -------------------------------------------------------------------------
        for pat in SYSTEM_NOTIFICATION_PATTERNS:
            m = pat.search(subject_clean) or pat.search(text_body[:400])
            if m:
                evidence.append(f"System infrastructure signal: '{m.group(0)}'")
                return RelevanceResult(
                    relevance_category="system_notification",
                    is_business_relevant=False,
                    confidence=0.96,
                    reason="System delivery failure, server alert, or infrastructure notification.",
                    evidence=evidence,
                    needs_review=False,
                )

        # -------------------------------------------------------------------------
        # Priority Check 4: Automated Notifications (Bank alerts, Google Forms, Calendars)
        # -------------------------------------------------------------------------
        for pat in AUTOMATED_TRANSACTION_PATTERNS:
            m = pat.search(subject_clean) or pat.search(text_body[:300])
            if m:
                evidence.append(f"Automated notification signal: '{m.group(0)}'")
                return RelevanceResult(
                    relevance_category="automated_notification",
                    is_business_relevant=False,
                    confidence=0.95,
                    reason="Automated transaction alert, form response receipt, or calendar notification.",
                    evidence=evidence,
                    needs_review=False,
                )

        # -------------------------------------------------------------------------
        # Priority Check 5: Newsletter & Marketing Broadcasts
        # -------------------------------------------------------------------------
        for pat in NEWSLETTER_PATTERNS:
            m = pat.search(subject_clean) or pat.search(text_body[:400])
            if m:
                evidence.append(f"Newsletter signal: '{m.group(0)}'")
                return RelevanceResult(
                    relevance_category="newsletter_marketing",
                    is_business_relevant=False,
                    confidence=0.92,
                    reason="Promotional newsletter, market broadcast, or educational newsletter.",
                    evidence=evidence,
                    needs_review=False,
                )

        # Header-based automation indicators (e.g., Precedence: bulk, List-Unsubscribe)
        if headers:
            if headers.get("list-unsubscribe") or headers.get("precedence", "").lower() in ["bulk", "junk", "list"]:
                evidence.append("Automated mailing list headers (List-Unsubscribe / Precedence: bulk)")
                return RelevanceResult(
                    relevance_category="newsletter_marketing",
                    is_business_relevant=False,
                    confidence=0.90,
                    reason="Automated mass email or newsletter header detected.",
                    evidence=evidence,
                    needs_review=False,
                )

        # Check automated sender domains if body is largely automated
        is_automated_sender = any(s.search(sender_clean) for s in AUTOMATED_NOTIFICATION_SENDERS)
        if is_automated_sender:
            evidence.append(f"Automated broadcast / notification sender domain: '{sender_clean}'")
            return RelevanceResult(
                relevance_category="automated_notification",
                is_business_relevant=False,
                confidence=0.92,
                reason=f"Sent from automated system or broadcast sender ({sender_clean}) without commercial buying signals.",
                evidence=evidence,
                needs_review=False,
            )

        # -------------------------------------------------------------------------
        # Priority Check 6: Business Conversations & Ongoing Discussion
        # -------------------------------------------------------------------------
        is_reply = subject_clean.lower().startswith("re:") or subject_clean.lower().startswith("fwd:")
        has_business_terms = bool(re.search(
            r"\b(proposal|quotation|quote|project|website|software|system|app|agreement|contract|scope|timeline|features|progress|update|status|invoice|discount|budget|payment|enquiry|inquiry|pricing|services|partnership|meeting|call|schedule|demo|client|hospital|clinic|retail|manufacturing|consulting)\b",
            combined_text,
            re.IGNORECASE
        ))

        if is_reply or has_business_terms:
            evidence.append("Business communication discussing project, services, or ongoing conversation")
            return RelevanceResult(
                relevance_category="business_conversation",
                is_business_relevant=True,
                confidence=0.88,
                reason="Ongoing business conversation concerning active project, proposal, or services.",
                evidence=evidence,
                needs_review=False,
            )

        # Check for customer support
        if re.search(r"\b(issue|bug|problem|error|not working|urgent fix|ticket|help needed)\b", combined_text, re.IGNORECASE):
            evidence.append("Customer support or technical issue inquiry")
            return RelevanceResult(
                relevance_category="customer_support",
                is_business_relevant=True,
                confidence=0.88,
                reason="Client support inquiry or technical assistance request.",
                evidence=evidence,
                needs_review=False,
            )

        # Default fallback:
        # If from a human contact (not automated notification sender), treat as business communication
        if not is_automated_sender:
            return RelevanceResult(
                relevance_category="business_conversation",
                is_business_relevant=True,
                confidence=0.75,
                reason="Direct message from business contact without automated indicators.",
                evidence=["Direct non-automated sender"],
                needs_review=True,
            )

        # If from an automated sender lacking commercial intent, classify as non-business
        return RelevanceResult(
            relevance_category="unknown_review",
            is_business_relevant=False,
            confidence=0.60,
            reason="Automated notification lacking commercial business intent.",
            evidence=["Automated notification sender with no commercial keywords"],
            needs_review=True,
        )
