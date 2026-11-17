"""Script to remove g1digitalizing@gmail.com mailbox and backfill remaining mailbox."""

import os
import sys

# Ensure app is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.services.mailbox_service import MailboxService
from app.services.hybrid_classifier import HybridClassifier
from app.models.mailbox_model import Mailbox
from app.models.email_model import Email
from app.models.classification_model import Classification

def main():
    db = SessionLocal()
    try:
        service = MailboxService(db)
        print("Initial mailboxes:")
        for mb in db.query(Mailbox).all():
            cnt = db.query(Email).filter(Email.mailbox_id == mb.id).count()
            print(f"  ID {mb.id}: {mb.email_address} (active={mb.is_active}, emails={cnt})")

        print("\nRemoving mailbox 'g1digitalizing@gmail.com'...")
        res = service.remove_mailbox("g1digitalizing@gmail.com")
        print(f"Removal result: {res}")

        print("\nRemaining mailboxes:")
        for mb in db.query(Mailbox).all():
            cnt = db.query(Email).filter(Email.mailbox_id == mb.id).count()
            print(f"  ID {mb.id}: {mb.email_address} (active={mb.is_active}, emails={cnt})")

        active_mb = service.get_active_mailbox()
        if active_mb:
            print(f"\nActive mailbox is now: ID {active_mb.id} ({active_mb.email_address})")
            print(f"Running backfill reclassification on mailbox {active_mb.id}...")
            classifier = HybridClassifier(db)
            backfill_res = classifier.backfill_reclassify_all(mailbox_id=active_mb.id)
            print(f"Backfill complete: reviewed={backfill_res['total_emails_reviewed']}, reclassified={backfill_res['reclassified_count']}, changed={backfill_res['changed_count']}")

            # Inspect classification breakdown
            print("\nClassification breakdown for active mailbox:")
            classifications = (
                db.query(Classification)
                .join(Email, Email.id == Classification.email_id)
                .filter(Email.mailbox_id == active_mb.id)
                .all()
            )
            print(f"Total classified: {len(classifications)}")
            for c in classifications:
                e = db.query(Email).filter(Email.id == c.email_id).first()
                print(f"  [ID {e.id}] Subj: {e.subject[:35]} | Relevance: {c.relevance_category} (Biz={c.is_business_relevant}) | Pipeline: {c.pipeline_category} | Rel: {c.relationship} | Intent: {c.intent} | Stage: {c.lead_stage} | Ind: {c.sender_industry}->{c.target_industry}")
        else:
            print("\nNo active mailbox remaining.")

    finally:
        db.close()

if __name__ == "__main__":
    main()
