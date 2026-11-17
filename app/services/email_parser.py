"""Robust MIME email parsing and decoding utilities.

Handles:
- MIME header decoding (RFC 2047, Base64, Quoted-Printable, diverse charsets).
- Plain-text and HTML body extraction from single-part and multipart structures.
- Safe attachment detection and metadata extraction without large memory overhead.
- RFC 2822 headers: Message-ID, In-Reply-To, References, Date.
- Gmail-specific headers: X-GM-THRID, X-GM-MSGID.
- Clean snippet generation for inbox listings.
"""

import email
from email.header import decode_header
from email.message import Message
import re
from typing import List, Optional, Tuple

from app.schemas.email_schema import AttachmentMetadata, EmailDetail, EmailSummary


def decode_mime_words(raw_header: Optional[str]) -> str:
    """Safely decode RFC 2047 MIME encoded-word strings into a normalized Unicode string.

    Examples:
        "=?UTF-8?B?VGVzdCBFbcOhaWw=?=" -> "Test Emáil"
        "=?ISO-8859-1?Q?Hello_World?=" -> "Hello World"
    """
    if not raw_header:
        return ""

    try:
        decoded_fragments: List[str] = []
        for fragment, encoding in decode_header(raw_header):
            if isinstance(fragment, bytes):
                # Attempt declared charset, fallback to utf-8, latin-1
                target_charset = encoding.lower() if encoding else "utf-8"
                try:
                    decoded_fragments.append(fragment.decode(target_charset, errors="replace"))
                except (LookupError, UnicodeDecodeError):
                    decoded_fragments.append(fragment.decode("latin-1", errors="replace"))
            elif isinstance(fragment, str):
                decoded_fragments.append(fragment)
            else:
                decoded_fragments.append(str(fragment))

        result = " ".join("".join(decoded_fragments).split())
        return result.strip()
    except Exception:
        # Fallback to string representation if parsing completely fails
        return str(raw_header).strip()


def strip_html_tags(html_content: str) -> str:
    """Rough strip of HTML tags to generate a clean preview snippet."""
    if not html_content:
        return ""
    # Strip script and style blocks
    cleaned = re.sub(r"<(script|style).*?>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Collapse multiple whitespaces
    return " ".join(cleaned.split()).strip()


def generate_snippet(body_plain: Optional[str], body_html: Optional[str], max_length: int = 160) -> str:
    """Generate a clean 1-2 sentence preview snippet from plain text or HTML."""
    source_text = ""
    if body_plain and body_plain.strip():
        source_text = " ".join(body_plain.split()).strip()
    elif body_html and body_html.strip():
        source_text = strip_html_tags(body_html)

    if not source_text:
        return "(No preview available)"

    if len(source_text) <= max_length:
        return source_text
    return source_text[:max_length].rstrip() + "..."


def extract_attachment_metadata(part: Message) -> Optional[AttachmentMetadata]:
    """Inspect an email message part and extract attachment metadata if present."""
    filename = part.get_filename()
    content_disposition = part.get("Content-Disposition", "")

    # Check whether part is an attachment
    is_attachment = (
        bool(filename)
        or "attachment" in content_disposition.lower()
        or ("inline" in content_disposition.lower() and bool(filename))
    )

    if not is_attachment:
        return None

    # Decode filename if encoded
    cleaned_filename = decode_mime_words(filename) if filename else "untitled_attachment"

    content_type = part.get_content_type() or "application/octet-stream"
    payload = part.get_payload(decode=True)
    size_bytes = len(payload) if payload else 0

    return AttachmentMetadata(
        filename=cleaned_filename,
        content_type=content_type,
        size_bytes=size_bytes,
    )


def decode_body_payload(part: Message) -> str:
    """Decode the payload of a text part using its declared or fallback charset."""
    payload = part.get_payload(decode=True)
    if not payload:
        return ""

    charset = part.get_content_charset()
    if charset:
        charset = charset.lower()

    # Prioritize declared charset, fallback to utf-8, windows-1252, latin-1
    for enc in (charset, "utf-8", "windows-1252", "latin-1"):
        if not enc:
            continue
        try:
            return payload.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue

    return payload.decode("latin-1", errors="replace")


def parse_raw_email(
    raw_content: bytes,
    uid: str,
    uid_validity: Optional[int] = None,
    mailbox: str = "INBOX",
    thread_id: Optional[str] = None,
) -> EmailDetail:
    """Parse raw RFC 822 / MIME bytes into a structured EmailDetail domain object."""
    msg: Message = email.message_from_bytes(raw_content)

    # Decode standard headers
    subject = decode_mime_words(msg.get("Subject")) or "(No Subject)"
    sender = decode_mime_words(msg.get("From")) or "(Unknown Sender)"
    recipient = decode_mime_words(msg.get("To")) or None
    cc = decode_mime_words(msg.get("Cc")) or None
    bcc = decode_mime_words(msg.get("Bcc")) or None
    date = msg.get("Date")

    # Conversation and thread headers
    message_id = msg.get("Message-ID")
    if message_id:
        message_id = message_id.strip()

    in_reply_to = msg.get("In-Reply-To")
    if in_reply_to:
        in_reply_to = in_reply_to.strip()

    references = msg.get("References")
    if references:
        references = references.strip()

    # Gmail-specific thread headers (if returned or passed)
    if not thread_id:
        thread_id = msg.get("X-GM-THRID")
        if thread_id:
            thread_id = thread_id.strip()

    body_plain_parts: List[str] = []
    body_html_parts: List[str] = []
    attachments: List[AttachmentMetadata] = []

    if msg.is_multipart():
        for part in msg.walk():
            # Check for attachments first
            att = extract_attachment_metadata(part)
            if att:
                attachments.append(att)
                continue

            content_type = part.get_content_type()
            if content_type == "text/plain":
                text = decode_body_payload(part)
                if text:
                    body_plain_parts.append(text)
            elif content_type == "text/html":
                html = decode_body_payload(part)
                if html:
                    body_html_parts.append(html)
    else:
        # Non-multipart message
        content_type = msg.get_content_type()
        att = extract_attachment_metadata(msg)
        if att:
            attachments.append(att)
        elif content_type == "text/html":
            body_html_parts.append(decode_body_payload(msg))
        else:
            body_plain_parts.append(decode_body_payload(msg))

    body_plain = "\n\n".join(body_plain_parts).strip() if body_plain_parts else None
    body_html = "\n\n".join(body_html_parts).strip() if body_html_parts else None

    snippet = generate_snippet(body_plain, body_html)

    return EmailDetail(
        uid=str(uid),
        uid_validity=uid_validity,
        mailbox=mailbox,
        message_id=message_id,
        thread_id=thread_id,
        subject=subject,
        sender=sender,
        recipient=recipient,
        cc=cc,
        bcc=bcc,
        date=date,
        snippet=snippet,
        body_plain=body_plain,
        body_html=body_html,
        in_reply_to=in_reply_to,
        references=references,
        has_attachments=len(attachments) > 0,
        attachments=attachments,
    )


def email_detail_to_summary(detail: EmailDetail) -> EmailSummary:
    """Convert an EmailDetail object into a lighter EmailSummary for inbox listings."""
    return EmailSummary(
        uid=detail.uid,
        uid_validity=detail.uid_validity,
        mailbox=detail.mailbox,
        message_id=detail.message_id,
        thread_id=detail.thread_id,
        subject=detail.subject,
        sender=detail.sender,
        recipient=detail.recipient,
        date=detail.date,
        snippet=detail.snippet,
        has_attachments=detail.has_attachments,
        attachment_count=len(detail.attachments),
        in_reply_to=detail.in_reply_to,
        references=detail.references,
    )

