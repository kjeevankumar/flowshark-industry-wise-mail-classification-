"""Rule-based Industry Detection Engine for FlowShark.

Accurately distinguishes:
1. Sender Industry: Which industry does the sender belong to?
2. Target Industry: Which industry or domain does the current project / service target?
3. Sub-industry: Specific niche under the target or sender industry.
4. Business Activity: Concise summary of the relevant commercial engagement.
5. Calibrated Confidence and Evidence Extraction.
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.industry_taxonomy import (
    INDUSTRY_SIGNALS,
    INDUSTRY_TAXONOMY,
    get_all_industries,
    get_sub_industries,
    normalize_industry,
)

logger = logging.getLogger("gmail_fastapi.industry_rule_classifier")


@dataclass
class IndustryRuleResult:
    """Structured result from rule-based industry detection."""
    sender_industry: str = "Unknown"
    target_industry: str = "Unknown"
    sub_industry: Optional[str] = None
    business_activity: Optional[str] = None
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    reason: str = ""
    requires_review: bool = True


# Explicit Self-Identification Patterns (Sender Industry)
SENDER_IDENTITY_PATTERNS = [
    # "We are an IT company / software agency / hospital / manufacturer..."
    re.compile(r"\bwe\s+are\s+(?:a|an)\s+([a-z0-9\s&-]+?)(?:\.|\,|\;|\band\b|\bdeveloping\b|\blooking\b|\bwant\b|\bneed\b|\bspecializ|\brunning\b)", re.IGNORECASE),
    # "We operate a hospital / clinic / hotel / school..."
    re.compile(r"\bwe\s+operate\s+(?:a|an|the)?\s*([a-z0-9\s&-]+?)(?:\.|\,|\;|\band\b|\bneed\b|\blooking\b|\bwant\b)", re.IGNORECASE),
    # "We run a..."
    re.compile(r"\bwe\s+run\s+(?:a|an|the)?\s*([a-z0-9\s&-]+?)(?:\.|\,|\;|\band\b|\bneed\b|\blooking\b|\bwant\b)", re.IGNORECASE),
    # "We provide..."
    re.compile(r"\bwe\s+provide\s+([a-z0-9\s&-]+?)(?:\.|\,|\;|\band\b|\bto\b|\bfor\b)", re.IGNORECASE),
    # "We manufacture..."
    re.compile(r"\bwe\s+manufacture\s+([a-z0-9\s&-]+?)(?:\.|\,|\;|\band\b|\bfor\b)", re.IGNORECASE),
    # "We produce / build..."
    re.compile(r"\bwe\s+produce\s+([a-z0-9\s&-]+?)(?:\.|\,|\;|\band\b|\bfor\b)", re.IGNORECASE),
    # "As a hospital / As an IT vendor..."
    re.compile(r"\bas\s+(?:a|an)\s+([a-z0-9\s&-]+?)(?:\.|\,|\;|\bwe\b)", re.IGNORECASE),
    # "Our company is a..."
    re.compile(r"\bour\s+(?:company|firm|agency|organization|business)\s+is\s+(?:a|an)?\s*([a-z0-9\s&-]+?)(?:\.|\,|\;|\band\b)", re.IGNORECASE),
    # "Our clothing business / our hospital / our school..."
    re.compile(r"\bour\s+([a-z0-9\s&-]+?\s+(?:business|firm|store|shop|practice|clinic|hospital|school|company))", re.IGNORECASE),
]

# Explicit Target / Solution Indicators (Target Industry)
TARGET_PROJECT_PATTERNS = [
    # "software for hospitals / schools / banks..."
    re.compile(r"\b(?:software|application|app|platform|system|solution|website|portal)\s+for\s+([a-z0-9\s&-]+?)(?:\.|\,|\;|\band\b|\bto\b|\bwith\b|$)", re.IGNORECASE),
    # "develop software for..."
    re.compile(r"\b(?:develop|building|build|create|design)\s+(?:software|a\s+website|an\s+app|a\s+solution)\s+for\s+([a-z0-9\s&-]+?)(?:\.|\,|\;|\band\b|\bto\b|$)", re.IGNORECASE),
    # "campaigns / marketing / services for..."
    re.compile(r"\b(?:campaign|campaigns|marketing|advertising|services|advisory|consulting)\s+for\s+([a-z0-9\s&-]+?)(?:\.|\,|\;|\band\b|\bto\b|$)", re.IGNORECASE),
    # "solution for..."
    re.compile(r"\b(?:solution|service|tool|quotation|quote)\s+for\s+(?:our\s+)?([a-z0-9\s&-]+?)(?:\.|\,|\;|\band\b|\bto\b|$)", re.IGNORECASE),
    # "need patient management / core banking / inventory software..."
    re.compile(r"\bneed\s+([a-z0-9\s&-]+?\s+(?:software|system|solution|management|platform|portal|app))", re.IGNORECASE),
    # "e-commerce website for our clothing business"
    re.compile(r"\b(?:e-commerce|ecommerce|website)\s+for\s+(?:our\s+)?([a-z0-9\s&-]+?)(?:\.|\,|\;|\band\b|$)", re.IGNORECASE),
]


class IndustryRuleClassifier:
    """Evaluates lexical, syntactic, and contextual signals to determine sender and target industries."""

    def __init__(self):
        self.signals = INDUSTRY_SIGNALS

    def evaluate(
        self,
        cleaned_body: str,
        subject: Optional[str] = None,
        sender_name: Optional[str] = None,
        sender_email: Optional[str] = None,
        context: Optional[Any] = None,
    ) -> IndustryRuleResult:
        """Execute rule-based industry detection on email text and conversation context."""
        subject_part = f"{subject.strip().rstrip('.')}. " if subject and subject.strip() else ""
        text = f"{subject_part}{cleaned_body or ''}".lower()
        if not text.strip():
            return IndustryRuleResult(
                sender_industry="Unknown",
                target_industry="Unknown",
                confidence=0.0,
                evidence=[],
                reason="Email contains no readable text.",
                requires_review=True,
            )

        evidence: List[str] = []
        sender_industry: Optional[str] = None
        target_industry: Optional[str] = None
        sub_industry: Optional[str] = None
        business_activity: Optional[str] = None
        confidence: float = 0.0

        # Step 1: Detect explicit Sender Identity Patterns
        for pattern in SENDER_IDENTITY_PATTERNS:
            match = pattern.search(text)
            if match:
                matched_phrase = match.group(0).strip()
                extracted_entity = match.group(1).strip()
                detected_ind = self._match_phrase_to_industry(extracted_entity)
                if detected_ind:
                    sender_industry = detected_ind
                    evidence.append(f"Sender identification: '{matched_phrase}'")
                    # Also check for sub-industry from extracted entity
                    sub_ind = self._match_sub_industry(detected_ind, text)
                    if sub_ind:
                        sub_industry = sub_ind
                    break

        # Step 2: Detect explicit Target Project Patterns
        for pattern in TARGET_PROJECT_PATTERNS:
            match = pattern.search(text)
            if match:
                matched_phrase = match.group(0).strip()
                extracted_target = match.group(1).strip()
                detected_ind = self._match_phrase_to_industry(extracted_target)
                if detected_ind:
                    target_industry = detected_ind
                    evidence.append(f"Target project requirement: '{matched_phrase}'")
                    sub_ind = self._match_sub_industry(detected_ind, text)
                    if sub_ind:
                        sub_industry = sub_ind
                    break

        # Step 3: Domain-specific Keyword & Phrase Signal Scoring
        scores: Dict[str, int] = {ind: 0 for ind in self.signals.keys()}
        matched_signals_by_ind: Dict[str, List[str]] = {ind: [] for ind in self.signals.keys()}

        for ind, ind_data in self.signals.items():
            # Check multi-word phrases (higher weight)
            for phrase in ind_data["phrases"]:
                if phrase in text:
                    scores[ind] += 3
                    matched_signals_by_ind[ind].append(phrase)

            # Check individual keywords
            for kw in ind_data["keywords"]:
                # Use word boundary
                if re.search(r"\b" + re.escape(kw) + r"\b", text):
                    scores[ind] += 1
                    matched_signals_by_ind[ind].append(kw)

        # Sort industries by match score
        ranked_industries = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_ind, top_score = ranked_industries[0] if ranked_industries else ("Unknown", 0)
        second_ind, second_score = ranked_industries[1] if len(ranked_industries) > 1 else ("Unknown", 0)

        # Step 4: Resolve Sender Industry and Target Industry Combinations

        # Case A: Both sender and target were explicitly matched via syntactic patterns
        if sender_industry and target_industry:
            confidence = 0.92
            if not sub_industry:
                sub_industry = self._match_sub_industry(target_industry, text)
            business_activity = self._generate_business_activity(sender_industry, target_industry, sub_industry, text)

        # Case B: Only sender was explicitly matched
        elif sender_industry and not target_industry:
            # If top scoring industry differs from sender industry and has strong evidence
            if top_score >= 3 and top_ind != sender_industry:
                target_industry = top_ind
                confidence = 0.88
                evidence.extend(matched_signals_by_ind[top_ind][:3])
            else:
                # Same industry (e.g., "We operate a hospital and need patient management software")
                target_industry = sender_industry
                confidence = 0.89

            if not sub_industry:
                sub_industry = self._match_sub_industry(target_industry, text) or self._match_sub_industry(sender_industry, text)
            business_activity = self._generate_business_activity(sender_industry, target_industry, sub_industry, text)

        # Case C: Only target was explicitly matched
        elif target_industry and not sender_industry:
            # Check sender company or email cues (e.g., "Digitalizing", "Tech", "Hospital")
            sender_cue = self._check_sender_identity_cues(sender_name, sender_email)
            if sender_cue:
                sender_industry = sender_cue
                evidence.append(f"Sender company/email cue: '{sender_name or sender_email}' -> {sender_cue}")
                confidence = 0.88
            elif top_score >= 4 and top_ind != target_industry:
                sender_industry = top_ind
                confidence = 0.82
            else:
                # If target is a direct business activity for the sender (e.g. clothing business)
                if any(p in text for p in ["our clothing", "our shop", "our store", "our firm", "our practice", "our company"]):
                    sender_industry = target_industry
                    confidence = 0.87
                else:
                    sender_industry = "Unknown"
                    confidence = 0.78

            if not sub_industry:
                sub_industry = self._match_sub_industry(target_industry, text)
            business_activity = self._generate_business_activity(sender_industry, target_industry, sub_industry, text)

        # Case D: Neither sender nor target explicitly matched via syntactic patterns
        else:
            if top_score >= 2:
                # We have keyword signals for at least one industry
                target_industry = top_ind
                evidence.extend(matched_signals_by_ind[top_ind][:3])

                # Check if sender company name reveals sender industry
                sender_cue = self._check_sender_identity_cues(sender_name, sender_email)
                if sender_cue:
                    sender_industry = sender_cue
                    evidence.append(f"Sender name cue: '{sender_name or sender_email}'")
                    confidence = 0.85
                elif any(p in text for p in ["our", "we have", "we are"]) and top_score >= 3:
                    sender_industry = top_ind
                    confidence = 0.80
                else:
                    # Insufficient evidence to pinpoint sender organization
                    sender_industry = "Unknown"
                    confidence = 0.65 if top_score >= 3 else 0.50

                sub_industry = self._match_sub_industry(target_industry, text)
                business_activity = self._generate_business_activity(sender_industry, target_industry, sub_industry, text)
            else:
                # Insufficient evidence in latest email: check conversation context
                if context and getattr(context, "has_context", False):
                    # Check if contact or previous lead has verified industry
                    contact_ind = getattr(context, "contact_industry", None)
                    lead_target = getattr(context, "lead_target_industry", None)
                    if contact_ind and contact_ind != "Unknown":
                        sender_industry = contact_ind
                        target_industry = lead_target or contact_ind
                        confidence = 0.85
                        evidence.append(f"Context memory: sender is verified {contact_ind}")
                        sub_industry = getattr(context, "contact_sub_industry", None) or getattr(context, "lead_sub_industry", None)
                        business_activity = f"Continuation of ongoing project in {target_industry}"
                    else:
                        sender_industry = "Unknown"
                        target_industry = "Unknown"
                        confidence = 0.20
                        evidence = []
                        business_activity = None
                else:
                    sender_industry = "Unknown"
                    target_industry = "Unknown"
                    confidence = 0.0
                    evidence = []
                    business_activity = None

        # Step 5: Final Validation & Formatting
        sender_industry = normalize_industry(sender_industry)
        target_industry = normalize_industry(target_industry)

        # Deduplicate evidence
        unique_evidence = list(dict.fromkeys(evidence))

        # Build Explanation Reason
        if sender_industry != "Unknown" and target_industry != "Unknown":
            if sender_industry == target_industry:
                reason = f"Detected {sender_industry} organization discussing {sub_industry or sender_industry} activities ({', '.join(unique_evidence[:2])})."
            else:
                reason = f"Sender identifies with {sender_industry} and target project is focused on {target_industry}."
        elif target_industry != "Unknown":
            reason = f"Identified target domain as {target_industry} based on signals ({', '.join(unique_evidence[:2])}), sender organization industry remains unconfirmed."
        elif sender_industry != "Unknown":
            reason = f"Sender identified as {sender_industry}, but specific target project industry was not specified."
        else:
            reason = "No sufficient industry keywords, project domains, or business activities detected in email content."

        # Human Review rule: confidence < 0.80 or either industry is Unknown on substantive messages
        requires_review = confidence < 0.80 or (sender_industry == "Unknown" and target_industry == "Unknown")

        return IndustryRuleResult(
            sender_industry=sender_industry,
            target_industry=target_industry,
            sub_industry=sub_industry,
            business_activity=business_activity,
            confidence=round(confidence, 2),
            evidence=unique_evidence,
            reason=reason,
            requires_review=requires_review,
        )

    def _match_phrase_to_industry(self, phrase: str) -> Optional[str]:
        """Map extracted text phrase to canonical primary industry."""
        p_clean = phrase.lower().strip()

        # Direct normalization check
        cand = normalize_industry(p_clean)
        if cand not in ["Unknown", "Other"]:
            return cand

        # Specific phrase heuristics
        if any(w in p_clean for w in ["it company", "it agency", "software", "tech firm", "web dev", "developer", "digitalize", "digitalizing"]):
            return "IT & Software"
        if any(w in p_clean for w in ["hospital", "clinic", "health", "medical", "doctor", "pharma"]):
            return "Healthcare"
        if any(w in p_clean for w in ["automotive", "automobile", "manufactur", "machinery", "components", "factory"]):
            return "Manufacturing"
        if any(w in p_clean for w in ["clothing", "apparel", "fashion", "retail", "ecommerce", "e-commerce", "store", "shop"]):
            return "Retail & E-commerce"
        if any(w in p_clean for w in ["bank", "accounting", "finance", "financial", "tax", "fintech"]):
            return "Banking & Finance"
        if any(w in p_clean for w in ["school", "college", "university", "education", "training institute", "elearning", "edtech"]):
            return "Education"
        if any(w in p_clean for w in ["insurance", "policy"]):
            return "Insurance"
        if any(w in p_clean for w in ["real estate", "property", "construction", "builder"]):
            return "Real Estate & Construction"
        if any(w in p_clean for w in ["logistics", "shipping", "freight", "warehouse", "transport"]):
            return "Logistics & Transportation"
        if any(w in p_clean for w in ["hotel", "restaurant", "travel", "tourism", "gym"]):
            return "Hospitality & Tourism"
        if any(w in p_clean for w in ["farm", "agriculture", "agritech"]):
            return "Agriculture"
        if any(w in p_clean for w in ["energy", "solar", "utilities", "electricity"]):
            return "Energy & Utilities"
        if any(w in p_clean for w in ["marketing", "advertising", "seo", "branding"]):
            return "Marketing & Advertising"
        if any(w in p_clean for w in ["legal", "law firm", "consulting", "recruitment"]):
            return "Legal & Professional Services"

        return None

    def _match_sub_industry(self, industry: str, text: str) -> Optional[str]:
        """Identify appropriate sub-industry under the primary industry."""
        canonical = normalize_industry(industry)
        subs = get_sub_industries(canonical)
        text_lower = text.lower()

        # Check for technology-focused sub-industries if software/app/platform is in text
        if any(tech_w in text_lower for tech_w in ["software", "tech", "app", "application", "platform", "system", "portal"]):
            if canonical == "Healthcare" and "Healthcare Technology" in subs:
                return "Healthcare Technology"
            if canonical == "Education" and "Educational Technology" in subs:
                return "Educational Technology"
            if canonical == "Banking & Finance" and "Fintech" in subs:
                return "Fintech"
            if canonical == "Agriculture" and "AgriTech" in subs:
                return "AgriTech"
            if canonical == "Insurance" and "Health Insurance" in subs and "health" in text_lower:
                return "Health Insurance"

        # Check sub-industry keywords mapping in INDUSTRY_SIGNALS
        ind_data = self.signals.get(canonical)
        if ind_data and "sub_industry_map" in ind_data:
            for kw, sub_name in ind_data["sub_industry_map"].items():
                if kw in text_lower:
                    return sub_name

        # Check sub-industry names in text
        for sub in subs:
            if sub.lower() in text_lower:
                return sub

        return subs[0] if subs else None

    def _check_sender_identity_cues(self, sender_name: Optional[str], sender_email: Optional[str]) -> Optional[str]:
        """Extract sender industry cues from sender name or email domain."""
        combined = f"{sender_name or ''} {sender_email or ''}".lower()
        if any(k in combined for k in ["digitalizing", "tech", "technologies", "software", "solutions", "it services"]):
            return "IT & Software"
        if any(k in combined for k in ["hospital", "clinic", "health", "pharma", "medical"]):
            return "Healthcare"
        if any(k in combined for k in ["motors", "automotive", "industries", "manufacturing"]):
            return "Manufacturing"
        if any(k in combined for k in ["retail", "fashion", "clothing", "apparel", "store", "shop"]):
            return "Retail & E-commerce"
        if any(k in combined for k in ["bank", "capital", "finance", "accounting", "advisory"]):
            return "Banking & Finance"
        if any(k in combined for k in ["edu", "school", "academy", "university", "institute"]):
            return "Education"
        if any(k in combined for k in ["realty", "properties", "builders", "construction"]):
            return "Real Estate & Construction"
        if any(k in combined for k in ["logistics", "express", "freight", "courier"]):
            return "Logistics & Transportation"
        if any(k in combined for k in ["hotel", "resort", "travel", "gym", "fitness"]):
            return "Hospitality & Tourism"
        return None

    def _generate_business_activity(
        self,
        sender_ind: Optional[str],
        target_ind: Optional[str],
        sub_ind: Optional[str],
        text: str,
    ) -> Optional[str]:
        """Synthesize concise description of business activity."""
        text_lower = text.lower()
        if "patient management" in text_lower:
            return "Hospital patient management software"
        if "automotive component" in text_lower or "automotive components" in text_lower:
            return "Automotive component manufacturing"
        if "clothing business" in text_lower or "e-commerce website" in text_lower:
            return "E-commerce website for clothing business"
        if sender_ind == "IT & Software" and target_ind == "Healthcare":
            return "Developing software for hospitals and healthcare technology"
        if target_ind and target_ind != "Unknown":
            return f"Business enquiry and solutions targeting {target_ind} ({sub_ind or 'general'})"
        return None
