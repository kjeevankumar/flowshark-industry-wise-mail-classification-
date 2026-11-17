"""Run clean backfill on database and display exact results."""

from app.db.session import SessionLocal, init_db
from app.models.contact_model import Contact
from app.models.lead_model import Lead, LeadActivityHistory
from app.models.classification_model import Classification, ClassificationHistory
from app.models.email_model import Email
from app.services.hybrid_classifier import HybridClassifier

def main():
    init_db()
    db = SessionLocal()

    # Clear CRM tables for a pristine backfill
    db.query(LeadActivityHistory).delete()
    db.query(Lead).delete()
    db.query(Contact).delete()
    db.commit()

    classifier = HybridClassifier(db=db)
    result = classifier.backfill_reclassify_all()
    print("=== BACKFILL RESULT ===")
    print("Reviewed:", result["total_emails_reviewed"])
    print("Changed:", result["changed_count"])

    print("\n=== LEADS CREATED ===")
    leads = db.query(Lead).all()
    print("Leads count:", len(leads))
    for l in leads:
        print(f"Lead {l.id}: '{l.title}' | Status: {l.status} | Contact ID: {l.contact_id}")

    print("\n=== BUSINESS CONTACTS ===")
    contacts = db.query(Contact).filter(Contact.relationship_type.in_(["new_contact", "existing_lead", "existing_customer"])).all()
    print("Business contacts count:", len(contacts))
    for c in contacts:
        print(f"Contact {c.id}: {c.name} <{c.email_address}> | Rel: {c.relationship_type} | Stage: {c.current_lead_stage}")

    print("\n=== G1 DIGITALIZING CLASSIFICATIONS ===")
    for eid in [13, 16, 29]:
        em = db.query(Email).filter(Email.id == eid).first()
        cl = db.query(Classification).filter(Classification.email_id == eid).first()
        if em and cl:
            print(f"Email {eid}: {em.subject}")
            print(f"  Relationship: {cl.relationship}")
            print(f"  Intent: {cl.intent}")
            print(f"  Lead Stage: {cl.lead_stage}")
            print(f"  Confidence: {cl.confidence}")
            print(f"  Reason: {cl.classification_reason}")
            print(f"  Context Used: {cl.context_used}")
            print(f"  Suggested Next Action: {cl.suggested_next_action}")
            print(f"  Needs Review: {cl.requires_human_review}")

    print("\n=== NON-LEAD SAMPLES ===")
    for eid in [1, 2, 4, 10, 17, 20]:
        em = db.query(Email).filter(Email.id == eid).first()
        cl = db.query(Classification).filter(Classification.email_id == eid).first()
        if em and cl:
            print(f"Email {eid}: {em.subject[:40]} | From: {em.sender[:35]}")
            print(f"  Relationship: {cl.relationship} | Intent: {cl.intent} | Stage: {cl.lead_stage}")

    print("\n=== AUDIT HISTORIES RECORDED ===")
    hist_count = db.query(ClassificationHistory).count()
    print("Total Classification History entries:", hist_count)
    histories = db.query(ClassificationHistory).filter(ClassificationHistory.email_id.in_([13, 16, 29])).all()
    for h in histories:
        print(f"History entry for Email {h.email_id}:")
        print(f"  Previous: {h.previous_values}")
        print(f"  Corrected: {h.corrected_values}")
        print(f"  Notes: {h.notes}")

    db.close()

if __name__ == "__main__":
    main()
