from app.db.session import SessionLocal
from app.models.email_model import Email
from app.services.hybrid_classifier import HybridClassifier
from app.services.mailbox_service import MailboxService
from app.config import get_settings

db = SessionLocal()
settings = get_settings()

try:
    mb_service = MailboxService(db=db, settings=settings)
    active_mb = mb_service.get_active_mailbox()
    mid = active_mb.id if active_mb else 1
    print(f"Running Industry Backfill for Mailbox ID: {mid}")

    classifier = HybridClassifier(db=db, settings=settings)
    emails = db.query(Email).filter(Email.mailbox_id == mid).order_by(Email.id.asc()).all()
    print(f"Total emails to classify: {len(emails)}")

    classified_count = 0
    for em in emails:
        res = classifier.classify_email(em, audit_reclassification=False)
        classified_count += 1
        print(f"Email {em.id} ({em.subject[:35]}...): Sender={res.sender_industry} | Target={res.target_industry} | Sub={res.sub_industry}")

    print(f"\nBackfill completed: {classified_count} emails processed.")
finally:
    db.close()
