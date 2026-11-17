"""Diagnostic script to test live Gmail IMAP and SMTP connections using local .env.

Strictly avoids logging passwords or credentials.
Tests:
1. Configuration loading and validation
2. IMAP connection and authentication on imap.gmail.com:993 with SSL
3. SMTP connection and authentication on smtp.gmail.com:587 with STARTTLS
4. Fetching latest 5 emails from INBOX in read-only mode using BODY.PEEK[]
"""

import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.services.imap_service import IMAPService, IMAPServiceError
from app.services.smtp_service import SMTPService, SMTPServiceError


def run_diagnostics():
    settings = get_settings()

    print("==================================================")
    print("      GMAIL INTEGRATION CONNECTIVITY DIAGNOSTICS   ")
    print("==================================================")

    # 1. Config Check
    print(f"\n[1] Configuration Check:")
    print(f"  - Configured: {settings.is_configured}")
    print(f"  - Masked Account: {settings.masked_gmail_address}")
    print(f"  - IMAP Server: {settings.IMAP_HOST}:{settings.IMAP_PORT}")
    print(f"  - SMTP Server: {settings.SMTP_HOST}:{settings.SMTP_PORT}")

    if not settings.is_configured:
        print("ERROR: Gmail address or App Password missing in .env.")
        return False

    # 2. IMAP Test
    print(f"\n[2] Testing IMAP Authentication (SSL port {settings.IMAP_PORT})...")
    imap_service = IMAPService(settings=settings)
    imap_success = False
    try:
        imap_res = imap_service.test_connection()
        print("  -> IMAP Connection: SUCCESS")
        print(f"  -> Total INBOX Messages: {imap_res.get('inbox_total_messages')}")
        print(f"  -> Mailbox UIDVALIDITY: {imap_res.get('uid_validity')}")
        imap_success = True
    except IMAPServiceError as err:
        print(f"  -> IMAP Connection: FAILED")
        print(f"  -> Error: {str(err)}")
    except Exception as err:
        print(f"  -> Unexpected IMAP Exception: {type(err).__name__}: {str(err)}")

    # 3. SMTP Test
    print(f"\n[3] Testing SMTP Authentication (STARTTLS port {settings.SMTP_PORT})...")
    print("  (Note: Testing authentication only; NO email will be sent)")
    smtp_service = SMTPService(settings=settings)
    smtp_success = False
    try:
        smtp_res = smtp_service.test_connection()
        print("  -> SMTP Connection: SUCCESS")
        print(f"  -> Server Handshake: OK (Noop status: {smtp_res.get('details', {}).get('noop_status')})")
        smtp_success = True
    except SMTPServiceError as err:
        print(f"  -> SMTP Connection: FAILED")
        print(f"  -> Error: {str(err)}")
    except Exception as err:
        print(f"  -> Unexpected SMTP Exception: {type(err).__name__}: {str(err)}")

    # 4. Fetch 5 Inbox Emails
    if imap_success:
        print(f"\n[4] Fetching Latest 5 Inbox Emails (Read-Only / BODY.PEEK[])...")
        try:
            emails, total, uid_validity = imap_service.fetch_inbox_emails(limit=5, offset=0)
            print(f"  -> Total Available Messages: {total}")
            print(f"  -> Retrieved Count: {len(emails)}")
            print(f"  -> Mailbox UIDVALIDITY: {uid_validity}")

            if not emails:
                print("  -> INBOX is currently empty.")
            else:
                for idx, email_item in enumerate(emails, 1):
                    print(f"\n  --- Email #{idx} ---")
                    print(f"  UID: {email_item.uid}")
                    print(f"  Date: {email_item.date}")
                    print(f"  From: {email_item.sender}")
                    print(f"  Subject: {email_item.subject}")
                    print(f"  Message-ID: {email_item.message_id}")
                    print(f"  Thread ID (X-GM-THRID): {email_item.thread_id}")
                    print(f"  Has Attachments: {email_item.has_attachments}")
                    print(f"  Snippet: {email_item.snippet[:120]}...")
        except Exception as err:
            print(f"  -> Failed to fetch emails: {type(err).__name__}: {str(err)}")

    print("\n==================================================")
    print(f"Summary: IMAP {'PASS' if imap_success else 'FAIL'} | SMTP {'PASS' if smtp_success else 'FAIL'}")
    print("==================================================")
    return imap_success and smtp_success


if __name__ == "__main__":
    success = run_diagnostics()
    sys.exit(0 if success else 1)

