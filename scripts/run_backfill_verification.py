"""Script to run and verify the backfill reclassification on actual database records."""

import json
from app.db.session import SessionLocal, init_db
from app.models.classification_model import Classification, ClassificationHistory
from app.models.contact_model import Contact
from app.models.lead_model import Lead
from app.models.email_model import Email
from app.services.hybrid_classifier import HybridClassifier

def main():
    init_db()
    db = SessionLocal()

    print("=== BEFORE RECLASSIFICATION ===")
    for eid in [13, 16, 29]:
        em = db.query(Email).filter(Email.id == eid).first()
        cl = db.query(Classification).filter(Classification.email_id == eid).first()
        if em and cl:
            print(f"Email {eid}: {em.subject}")
            print(f"  Relationship: {cl.relationship} | Intent: {cl.intent} | Stage: {cl.lead_stage} | Conf: {cl.confidence}")
            print(f"  Reason: {cl.classification_reason}")
            print(f"  Context Used: {cl.context_used}")

    print("\n=== RUNNING BACKFILL ===")
    classifier = HybridClassifier(db=db)
    result = classifier.backfill_reclassify_all()
    print("Total reviewed:", result["total_emails_reviewed"])
    print("Total changed:", result["changed_count"])

    print("\n=== AFTER RECLASSIFICATION ===")
    for eid in [13, 16, 29]:
        em = db.query(Email).filter(Email.id == eid).first()
        cl = db.query(Classification).filter(Classification.email_id == eid).first()
        if em and cl:
            print(f"Email {eid}: {em.subject}")
            print(f"  Relationship: {cl.relationship} | Intent: {cl.intent} | Stage: {cl.lead_stage} | Conf: {cl.confidence}")
            print(f"  Reason: {cl.classification_reason}")
            print(f"  Context Used: {cl.context_used}")
            print(f"  Suggested Next Action: {cl.suggested_next_action}")
            print(f"  Needs Review: {cl.requires_human_review}")

    print("\n=== AUDIT HISTORY ENTRIES RECORDED ===")
    histories = db.query(ClassificationHistory).filter(ClassificationHistory.email_id.in_([13, 16, 29])).all()
    for h in histories:
        print(f"History entry for Email {h.email_id}:")
        print(f"  Previous: {h.previous_values}")
        print(f"  Corrected: {h.corrected_values}")
        print(f"  Notes: {h.notes}")

    print("\n=== BUSINESS CONTACTS IN CRM ===")
    contacts = db.query(Contact).filter(Contact.relationship_type.in_(["new_contact", "existing_lead", "existing_customer"])).all()
    for c in contacts:
        print(f"Contact {c.id}: {c.name} <{c.email_address}> | Rel: {c.relationship_type} | Stage: {c.current_lead_stage}")

    print("\n=== BUSINESS LEADS IN CRM ===")
    leads = db.query(Lead).all()
    for l in leads:
        print(f"Lead {l.id}: '{l.title}' | Status: {l.status} | Contact ID: {l.contact_id}")

    # Verify other emails (like newsletters) remain UNKNOWN / OTHER
    newsletter = db.query(Email).filter(Email.sender.ilike("%pinterest%")).first()
    if newsletter and newsletter.classification:
        print(f"\nNewsletter Check: Email {newsletter.id} ({newsletter.sender})")
        print(f"  Relationship: {newsletter.classification.relationship} | Intent: {newsletter.classification.intent} | Stage: {newsletter.classification.lead_stage}")

    db.close()

if __name__ == "__main__":
    main()
