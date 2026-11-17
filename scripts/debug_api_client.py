import json
from app.config import get_settings
from app.db.session import SessionLocal
from app.models.email_model import Email
from app.models.classification_model import Classification
from app.schemas.dashboard_schema import EmailRead, PaginatedEmailsResponse
from app.routes.email_inbox_routes import get_email_detail, list_emails

settings = get_settings()
db = SessionLocal()

try:
    print(f"DATABASE_URL: {settings.DATABASE_URL}")

    # 1. Query Email 29 in DB
    email_29 = db.query(Email).filter(Email.id == 29).first()
    if not email_29:
        print("CRITICAL: Email 29 not found in DB!")
    else:
        print(f"\n--- Persisted DB Email 29 ---")
        print(f"ID: {email_29.id}")
        print(f"Subject: {email_29.subject}")
        print(f"Sender: {email_29.sender}")
        print(f"Mailbox ID: {email_29.mailbox_id}")
        print(f"Contact ID: {email_29.contact_id}")
        print(f"Lead ID: {email_29.lead_id}")
        
        c_rel = email_29.classification
        if c_rel:
            print(f"\n--- Attached classification via email_29.classification relationship ---")
            print(f"Classification ID: {c_rel.id}")
            print(f"Relationship: {c_rel.relationship}")
            print(f"Intent: {c_rel.intent}")
            print(f"Lead Stage: {c_rel.lead_stage}")
            print(f"Confidence: {c_rel.confidence}")
            print(f"Reason: {c_rel.classification_reason}")
            print(f"Updated at: {c_rel.updated_at}")
        else:
            print("No classification attached to email_29.classification!")

        all_c = db.query(Classification).filter(Classification.email_id == 29).all()
        print(f"\nAll classifications for email_id 29 in DB: count = {len(all_c)}")
        for ac in all_c:
            print(f"  ID {ac.id}: rel={ac.relationship}, intent={ac.intent}, stage={ac.lead_stage}, conf={ac.confidence}, mailbox={ac.mailbox_id}")

    # 2. Call route get_email_detail(29)
    print("\n--- Route: get_email_detail(29) ---")
    detail_orm = get_email_detail(email_id=29, db=db, settings=settings)
    detail_pydantic = EmailRead.model_validate(detail_orm)
    print("Email detail Pydantic serialization:")
    print(f"  id: {detail_pydantic.id}")
    print(f"  subject: {detail_pydantic.subject}")
    print(f"  classification: {detail_pydantic.classification.model_dump_json(indent=2) if detail_pydantic.classification else None}")

    # 3. Call route list_emails(page=1, size=50)
    print("\n--- Route: list_emails(page=1, size=50) ---")
    listing = list_emails(page=1, size=50, db=db, settings=settings)
    print(f"Total emails returned in listing: {listing.total}")
    found = [it for it in listing.items if it.id == 29]
    if found:
        f = EmailRead.model_validate(found[0])
        print(f"Email 29 in list_emails():")
        print(f"  id: {f.id}")
        print(f"  subject: {f.subject}")
        print(f"  classification: {f.classification.model_dump_json(indent=2) if f.classification else None}")
    else:
        print("Email 29 NOT FOUND in list_emails()!")

finally:
    db.close()
