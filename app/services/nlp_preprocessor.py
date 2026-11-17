"""NLP Preprocessing Service for email content normalization and cleaning.

Handles:
- HTML to clean readable text conversion with tag stripping and entity unescaping.
- Whitespace and newline normalization.
- Isolation and removal of quoted reply blocks (e.g. 'On ... wrote:', '> ...').
- Signature detection and separation.
- Heuristic detection of promotional / marketing noise.
- Clean text extraction while preserving the raw original bodies for record keeping.
"""

from html import unescape
import re
from typing import NamedTuple, Optional, Tuple


class PreprocessedEmailText(NamedTuple):
    """Container for preprocessed email content and identified segments."""
    cleaned_body: str
    quoted_history: Optional[str]
    signature: Optional[str]
    is_promotional: bool
    word_count: int


# Patterns identifying reply and quote headers
QUOTE_PATTERNS = [
    re.compile(r"^\s*On\s+.*wrote:\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*-+\s*Original Message\s*-+\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*From:.*Sent:.*To:.*Subject:", re.MULTILINE | re.DOTALL | re.IGNORECASE),
    re.compile(r"^\s*_{10,}\s*$", re.MULTILINE),
]

# Common signature markers
SIGNATURE_STARTERS = [
    re.compile(r"^\s*--\s*$", re.MULTILINE),
    re.compile(r"^\s*Best regards,?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*Warm regards,?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*Thanks & regards,?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*Kind regards,?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*Regards,?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*Thanks,?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*Sincerely,?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*Cheers,?\s*$", re.MULTILINE | re.IGNORECASE),
]

# Promotional indicators
PROMO_KEYWORDS = [
    "unsubscribe",
    "view in browser",
    "view this email in your browser",
    "manage preferences",
    "opt out",
    "privacy policy | terms",
    "discount code",
    "limited time offer",
    "promo code",
    "sale ends",
    "no longer wish to receive these emails",
    "learning deals",
    "deals:",
    "once-a-year savings",
    "special offer",
    "cyber month",
]


class NLPPreprocessor:
    """Provides resilient text extraction, normalization, and segmenting for emails."""

    @classmethod
    def clean_html(cls, html_content: str) -> str:
        """Convert HTML body into readable, clean text."""
        if not html_content:
            return ""

        # Remove scripts and stylesheets
        text = re.sub(r"<(script|style|noscript).*?>.*?</\1>", " ", html_content, flags=re.DOTALL | re.IGNORECASE)
        # Replace line-breaking HTML tags with newlines
        text = re.sub(r"</?(p|br|div|tr|li|h[1-6])\b.*?>", "\n", text, flags=re.IGNORECASE)
        # Remove remaining tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Unescape HTML entities (&nbsp;, &amp;, etc.)
        text = unescape(text)
        return text

    @classmethod
    def normalize_whitespace(cls, text: str) -> str:
        """Collapse redundant blank lines and spaces while preserving paragraph breaks."""
        if not text:
            return ""
        lines = [line.strip() for line in text.splitlines()]
        # Collapse multiple empty lines
        cleaned_lines = []
        consecutive_empty = 0
        for line in lines:
            if not line:
                consecutive_empty += 1
                if consecutive_empty <= 1:
                    cleaned_lines.append("")
            else:
                consecutive_empty = 0
                cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()

    @classmethod
    def separate_quoted_replies(cls, text: str) -> Tuple[str, Optional[str]]:
        """Split modern reply content from historical quoted text."""
        lines = text.splitlines()
        main_lines = []
        quote_lines = []
        is_quote_section = False

        for idx, line in enumerate(lines):
            # Check for lines starting with '>'
            if line.strip().startswith(">"):
                is_quote_section = True
                quote_lines.append(line)
                continue

            # Check for standard quote headers
            matches_quote_header = any(pattern.match(line) for pattern in QUOTE_PATTERNS)
            if matches_quote_header:
                is_quote_section = True
                quote_lines.extend(lines[idx:])
                break

            if is_quote_section:
                quote_lines.append(line)
            else:
                main_lines.append(line)

        main_text = cls.normalize_whitespace("\n".join(main_lines))
        quote_text = cls.normalize_whitespace("\n".join(quote_lines)) if quote_lines else None
        return main_text, quote_text

    @classmethod
    def separate_signature(cls, text: str) -> Tuple[str, Optional[str]]:
        """Identify signature blocks near the end of the text and separate them."""
        lines = text.splitlines()
        if len(lines) <= 2:
            return text, None

        # Search for signature starters in the lower half of the email
        sig_index = None
        for i in range(max(1, len(lines) - 12), len(lines)):
            for pattern in SIGNATURE_STARTERS:
                if pattern.match(lines[i]):
                    sig_index = i
                    break
            if sig_index is not None:
                break

        if sig_index is not None:
            body = cls.normalize_whitespace("\n".join(lines[:sig_index]))
            signature = cls.normalize_whitespace("\n".join(lines[sig_index:]))
            return body, signature

        return text, None

    @classmethod
    def is_promotional_content(cls, text: str, subject: str = "") -> bool:
        """Detect whether email is predominantly promotional or newsletter material."""
        combined = f"{subject}\n{text}".lower()
        promo_matches = sum(1 for kw in PROMO_KEYWORDS if kw in combined)
        return promo_matches >= 2

    @classmethod
    def preprocess(cls, body_plain: Optional[str], body_html: Optional[str], subject: str = "") -> PreprocessedEmailText:
        """Run complete preprocessing pipeline on raw email representations."""
        # Use plain text when present, or clean HTML
        raw_source = body_plain if (body_plain and body_plain.strip()) else cls.clean_html(body_html or "")

        # 1. Whitespace normalization
        normalized = cls.normalize_whitespace(raw_source)

        # 2. Separate quoted historical replies
        body_without_quotes, quoted_history = cls.separate_quoted_replies(normalized)

        # 3. Separate signature
        cleaned_body, signature = cls.separate_signature(body_without_quotes)

        # 4. Check for promotional / marketing signals
        is_promo = cls.is_promotional_content(cleaned_body, subject=subject)

        # 5. Calculate clean word count
        words = cleaned_body.split()
        word_count = len(words)

        return PreprocessedEmailText(
            cleaned_body=cleaned_body,
            quoted_history=quoted_history,
            signature=signature,
            is_promotional=is_promo,
            word_count=word_count,
        )

