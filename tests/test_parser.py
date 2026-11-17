"""Automated unit tests for email parser service."""

from app.services.email_parser import (
    decode_mime_words,
    email_detail_to_summary,
    generate_snippet,
    parse_raw_email,
    strip_html_tags,
)


def test_parse_plaintext_email(sample_plaintext_email_bytes: bytes):
    """Verify parsing of a standard RFC 822 plain text email."""
    detail = parse_raw_email(
        raw_content=sample_plaintext_email_bytes,
        uid="101",
        uid_validity=123456,
        mailbox="INBOX",
        thread_id="th-999",
    )

    assert detail.uid == "101"
    assert detail.uid_validity == 123456
    assert detail.mailbox == "INBOX"
    assert detail.thread_id == "th-999"
    assert detail.subject == "Simple Plaintext Test"
    assert "Sender Name" in detail.sender
    assert "sender@example.com" in detail.sender
    assert detail.recipient == "recipient@example.com"
    assert detail.message_id == "<msg-001@example.com>"
    assert detail.in_reply_to == "<parent-000@example.com>"
    assert detail.references == "<thread-root@example.com> <parent-000@example.com>"
    assert detail.body_plain is not None
    assert "Hello world! This is a simple test email." in detail.body_plain
    assert detail.body_html is None
    assert not detail.has_attachments
    assert len(detail.attachments) == 0
    assert "Hello world!" in detail.snippet


def test_parse_multipart_email(sample_multipart_email_bytes: bytes):
    """Verify multipart/alternative email parsing (both text and HTML)."""
    detail = parse_raw_email(
        raw_content=sample_multipart_email_bytes,
        uid="102",
        uid_validity=123456,
        mailbox="INBOX",
    )

    assert detail.uid == "102"
    assert detail.subject == "Multipart Alternative Email"
    assert "marketing@company.com" in detail.sender
    assert detail.body_plain is not None
    assert "Plain version: Welcome to our platform!" in detail.body_plain
    assert detail.body_html is not None
    assert "<h3>Welcome to our platform!</h3>" in detail.body_html
    assert not detail.has_attachments
    assert len(detail.attachments) == 0


def test_parse_email_with_attachment(sample_email_with_attachment_bytes: bytes):
    """Verify attachment detection and metadata extraction without memory overhead."""
    detail = parse_raw_email(
        raw_content=sample_email_with_attachment_bytes,
        uid="103",
        uid_validity=123456,
        mailbox="INBOX",
    )

    assert detail.uid == "103"
    assert detail.subject == "Invoice for November 2026"
    assert detail.has_attachments is True
    assert len(detail.attachments) == 1

    attachment = detail.attachments[0]
    assert attachment.filename == "invoice_nov2026.pdf"
    assert "pdf" in attachment.content_type.lower()
    assert attachment.size_bytes > 0


def test_mime_encoded_subject_decoding(sample_mime_encoded_subject_bytes: bytes):
    """Verify decoding of RFC 2047 MIME encoded words (UTF-8, ISO-8859-1, accents, emojis)."""
    detail = parse_raw_email(
        raw_content=sample_mime_encoded_subject_bytes,
        uid="104",
        uid_validity=123456,
        mailbox="INBOX",
    )

    # Sender decoded from "=?UTF-8?B?Sm/Do28gU2lsdmE=?=" -> "João Silva"
    assert "João Silva" in detail.sender

    # Subject decoded from "=?UTF-8?B?...=? - =?ISO-8859-1?Q?Caf=E9?=" -> "Relatório Felicidade: 😊 - Café"
    assert "Relatório Felicidade" in detail.subject
    assert "Café" in detail.subject


def test_decode_mime_words_direct():
    """Direct tests for decode_mime_words utility."""
    # Plain ascii
    assert decode_mime_words("Hello World") == "Hello World"
    # None or empty
    assert decode_mime_words(None) == ""
    assert decode_mime_words("") == ""
    # Quoted-Printable ISO-8859-1
    assert decode_mime_words("=?ISO-8859-1?Q?Keld_J=F8rn_Simonsen?=") == "Keld Jørn Simonsen"


def test_strip_html_and_snippet():
    """Verify HTML stripping and snippet generation."""
    html = "<div><h2>Greeting Header</h2><p>Hello, this is <b>important</b> content.</p></div>"
    stripped = strip_html_tags(html)
    assert "Greeting Header" in stripped
    assert "<b>" not in stripped
    assert "<div>" not in stripped

    snippet = generate_snippet(None, html, max_length=30)
    assert len(snippet) <= 33  # max_length + "..."
    assert snippet.endswith("...")


def test_email_detail_to_summary_conversion(sample_plaintext_email_bytes: bytes):
    """Verify conversion from detailed representation to summary model."""
    detail = parse_raw_email(
        raw_content=sample_plaintext_email_bytes,
        uid="105",
        uid_validity=123456,
        mailbox="INBOX",
        thread_id="th-105",
    )
    summary = email_detail_to_summary(detail)

    assert summary.uid == "105"
    assert summary.uid_validity == 123456
    assert summary.mailbox == "INBOX"
    assert summary.thread_id == "th-105"
    assert summary.subject == detail.subject
    assert summary.sender == detail.sender
    assert summary.message_id == detail.message_id
    assert summary.has_attachments == detail.has_attachments
    assert summary.attachment_count == len(detail.attachments)

