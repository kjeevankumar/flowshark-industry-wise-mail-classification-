"""Automated test suite for AI-Powered Industry-Wise Email Classification in FlowShark.

Covers the 10 core requirements:
1. Hospital enquiry (Sender: Healthcare, Target: Healthcare).
2. Cross-industry service request (IT developing for Healthcare -> Sender: IT & Software, Target: Healthcare).
3. Manufacturing component supplier (Automotive components -> Sender: Manufacturing, Target: Manufacturing, Sub: Automotive).
4. Retail e-commerce request (Online clothing -> Sender: Retail & E-commerce, Target: Retail & E-commerce).
5. Ambiguous email ("Please share the quotation" -> Unknown, review required).
6. Contextual conversation: Email 1 establishes industry, Email 2 follow-up inherits, unrelated email handles fresh signals.
7. Graceful degradation when LLM unavailable (Fallback / Rule engine returns valid industry schema).
8. Mailbox isolation: Cross-mailbox industry data and analytics do not leak.
9. Manual industry correction (PUT /api/classifications/{id}/industry updates DB and audits history).
10. API Filtering & Analytics (GET /api/emails?industry=... and GET /api/analytics/industries).
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.classification_model import Classification, ClassificationHistory
from app.models.contact_model import Contact
from app.models.conversation_model import Conversation
from app.models.email_model import Email
from app.models.lead_model import Lead
from app.models.mailbox_model import Mailbox
from app.routes.classification_routes import get_industries_taxonomy, update_industry_classification
from app.routes.dashboard_routes import get_industry_analytics
from app.routes.email_inbox_routes import list_emails
from app.schemas.dashboard_schema import IndustryCorrectionRequest
from app.services.hybrid_classifier import HybridClassifier
from app.services.industry_rule_classifier import IndustryRuleClassifier
from app.services.industry_taxonomy import INDUSTRY_TAXONOMY, get_all_industries
from app.services.llm_provider import FallbackLLMProvider
from app.services.nlp_preprocessor import NLPPreprocessor


@pytest.fixture
def test_db():
    """Create an isolated in-memory SQLite database for industry classification tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    mb = Mailbox(
        email_address="sales@flowshark.io",
        is_active=True,
    )
    session.add(mb)
    session.commit()
    session.refresh(mb)

    try:
        yield session, mb
    finally:
        session.close()


# ==============================================================================
# Scenario 1: Hospital Enquiry
# ==============================================================================

def test_scenario_1_hospital_enquiry(test_db):
    """Scenario 1:
    'We are a multi-speciality hospital looking for patient management software.'
    Expected:
    - sender_industry: Healthcare
    - target_industry: Healthcare
    """
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="hosp-1",
        uid_validity=1,
        message_id="<hosp-001@cityhospital.org>",
        gmail_thread_id="th-hosp-1",
        sender="City Hospital Admin <admin@cityhospital.org>",
        subject="Enquiry: Patient Management Software System",
        body_text="We are a multi-speciality hospital looking for patient management software.",
        snippet="We are a multi-speciality hospital looking for patient management software.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email)
    db.commit()
    db.refresh(email)

    classification = classifier.classify_email(email)

    assert classification.sender_industry == "Healthcare"
    assert classification.target_industry == "Healthcare"
    assert classification.sub_industry in ["Hospitals", "Healthcare Technology", "Healthcare"]
    assert classification.industry_confidence >= 0.70
    assert classification.intent in ["new_enquiry", "follow_up", "other"]


# ==============================================================================
# Scenario 2: Cross-Industry Service Request (IT developing for Healthcare)
# ==============================================================================

def test_scenario_2_cross_industry_service_request(test_db):
    """Scenario 2:
    'We are an IT services company. We want to develop an enterprise portal for healthcare institutions.'
    Expected:
    - sender_industry: IT & Software
    - target_industry: Healthcare
    """
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="cross-2",
        uid_validity=1,
        message_id="<cross-002@techpartners.com>",
        gmail_thread_id="th-cross-2",
        sender="TechPartners <partner@techpartners.com>",
        subject="Collaboration on Hospital Solutions",
        body_text="We are an IT services company. We want to develop an enterprise portal for healthcare institutions.",
        snippet="We are an IT services company. We want to develop an enterprise portal for healthcare institutions.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email)
    db.commit()
    db.refresh(email)

    classification = classifier.classify_email(email)

    assert classification.sender_industry == "IT & Software"
    assert classification.target_industry == "Healthcare"
    assert classification.sub_industry in ["Healthcare Technology", "Hospitals", "IT Consulting"]
    assert "Healthcare" in classification.business_activity or "hospital" in classification.business_activity.lower()


# ==============================================================================
# Scenario 3: Manufacturing Component Supplier
# ==============================================================================

def test_scenario_3_manufacturing_component_supplier(test_db):
    """Scenario 3:
    'We manufacture automotive components and want to supply precision parts.'
    Expected:
    - sender_industry: Manufacturing
    - target_industry: Manufacturing
    - sub_industry: Automotive
    """
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="mfg-3",
        uid_validity=1,
        message_id="<mfg-003@autoparts.com>",
        gmail_thread_id="th-mfg-3",
        sender="Precision Auto <info@autoparts.com>",
        subject="Supply of automotive components",
        body_text="We manufacture automotive components and want to supply precision parts.",
        snippet="We manufacture automotive components and want to supply precision parts.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email)
    db.commit()
    db.refresh(email)

    classification = classifier.classify_email(email)

    assert classification.sender_industry == "Manufacturing"
    assert classification.target_industry == "Manufacturing"
    assert classification.sub_industry == "Automotive"
    assert classification.industry_confidence >= 0.75


# ==============================================================================
# Scenario 4: Retail E-Commerce Request
# ==============================================================================

def test_scenario_4_retail_ecommerce_request(test_db):
    """Scenario 4:
    'We run an online clothing store and need a custom Shopify web app.'
    Expected:
    - sender_industry: Retail & E-commerce
    - target_industry: Retail & E-commerce
    - sub_industry: Online Retail or Fashion
    """
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="ret-4",
        uid_validity=1,
        message_id="<ret-004@stylishwear.com>",
        gmail_thread_id="th-ret-4",
        sender="Stylish Wear <team@stylishwear.com>",
        subject="Shopify custom store development",
        body_text="We run an online clothing store and need a custom Shopify web app.",
        snippet="We run an online clothing store and need a custom Shopify web app.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email)
    db.commit()
    db.refresh(email)

    classification = classifier.classify_email(email)

    assert classification.sender_industry == "Retail & E-commerce"
    assert classification.target_industry == "Retail & E-commerce"
    assert classification.sub_industry in ["Online Retail", "Fashion", "Retail Stores"]


# ==============================================================================
# Scenario 5: Ambiguous Email Without Sufficient Evidence
# ==============================================================================

def test_scenario_5_ambiguous_email_yields_unknown(test_db):
    """Scenario 5:
    'Please share the quotation.'
    Expected:
    - sender_industry: Unknown
    - target_industry: Unknown
    - industry_requires_review: True
    - Does NOT hallucinate or guess a random industry.
    """
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="amb-5",
        uid_validity=1,
        message_id="<amb-005@generic.com>",
        gmail_thread_id="th-amb-5",
        sender="Generic Person <person@generic.com>",
        subject="Quotation",
        body_text="Please share the quotation.",
        snippet="Please share the quotation.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email)
    db.commit()
    db.refresh(email)

    classification = classifier.classify_email(email)

    assert classification.sender_industry == "Unknown"
    assert classification.target_industry == "Unknown"
    assert classification.industry_requires_review is True
    assert classification.industry_confidence <= 0.40


# ==============================================================================
# Scenario 6: Contextual Conversation & Unrelated Email Behavior
# ==============================================================================

def test_scenario_6_contextual_conversation_and_unrelated_signals(test_db):
    """Scenario 6:
    Email 1: Fitness studio asks for website -> Target: Hospitality & Tourism | Fitness & Gyms.
    Email 2: 'i need a update / progress' -> inherits Target: Hospitality & Tourism from lead context.
    Email 3: A completely different project enquiry from the same contact with explicit Banking signals
             does NOT blindly reuse Hospitality & Tourism.
    """
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    # Email 1: Fitness studio setup
    email_1 = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="fit-1",
        uid_validity=1,
        message_id="<fit-001@apexfitness.com>",
        gmail_thread_id="th-fit-10",
        sender="Apex Fitness <owner@apexfitness.com>",
        subject="Website for our fitness and gym center",
        body_text="Hi, we operate a fitness and gym center and need an online booking website.",
        snippet="Hi, we operate a fitness and gym center and need an online booking website.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email_1)
    db.commit()
    db.refresh(email_1)

    c1 = classifier.classify_email(email_1)
    assert c1.target_industry == "Hospitality & Tourism"

    # Email 2: Short follow-up in same thread/contact
    email_2 = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="fit-2",
        uid_validity=1,
        message_id="<fit-002@apexfitness.com>",
        in_reply_to="<fit-001@apexfitness.com>",
        gmail_thread_id="th-fit-10",
        sender="Apex Fitness <owner@apexfitness.com>",
        subject="Re: Website for our fitness and gym center",
        body_text="Hello, what is my website progress? I need an update.",
        snippet="Hello, what is my website progress? I need an update.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email_2)
    db.commit()
    db.refresh(email_2)

    c2 = classifier.classify_email(email_2)
    assert c2.relationship == "existing_lead"
    assert c2.intent == "follow_up"
    assert c2.target_industry == "Hospitality & Tourism"

    # Email 3: Same contact, but new distinct project with explicit Banking signals
    email_3 = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="fit-3",
        uid_validity=1,
        message_id="<fit-003@apexfitness.com>",
        gmail_thread_id="th-fit-99-new",
        sender="Apex Fitness <owner@apexfitness.com>",
        subject="New project: Fintech loan calculation gateway for our banking partner",
        body_text="We have a separate venture: building a fintech banking and taxation calculation gateway.",
        snippet="We have a separate venture: building a fintech banking and taxation calculation gateway.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email_3)
    db.commit()
    db.refresh(email_3)

    c3 = classifier.classify_email(email_3)
    # Does NOT blindly stick to Hospitality & Tourism because explicit Banking signals are present
    assert c3.target_industry == "Banking & Finance"


# ==============================================================================
# Scenario 7: Fallback Graceful Degradation
# ==============================================================================

def test_scenario_7_graceful_degradation_when_llm_fails(test_db):
    """Scenario 7:
    When LLM is unavailable or fails, FallbackLLMProvider uses IndustryRuleClassifier
    and produces deterministic, compliant structured output without crashing.
    """
    fallback_provider = FallbackLLMProvider()

    # Rule-clear email
    pre_clear = NLPPreprocessor.preprocess(
        body_plain="We run a chemical manufacturing facility and require regulatory compliance software.",
        body_html=None,
        subject="Plant compliance system",
    )
    result_clear = fallback_provider.classify_email(
        subject="Plant compliance system",
        preprocessed=pre_clear,
    )
    assert result_clear.sender_industry == "Manufacturing"
    assert result_clear.target_industry == "Manufacturing"
    assert result_clear.sub_industry in ["Chemical Manufacturing", "Industrial Machinery"]

    # Ambiguous email
    pre_ambiguous = NLPPreprocessor.preprocess(
        body_plain="Hello, thank you.",
        body_html=None,
        subject="Thanks",
    )
    result_ambiguous = fallback_provider.classify_email(
        subject="Thanks",
        preprocessed=pre_ambiguous,
    )
    assert result_ambiguous.sender_industry == "Unknown"
    assert result_ambiguous.target_industry == "Unknown"
    assert result_ambiguous.industry_requires_review is True


# ==============================================================================
# Scenario 8: Mailbox Isolation
# ==============================================================================

def test_scenario_8_mailbox_isolation(test_db):
    """Scenario 8:
    Verify that Email classifications, contacts, and lead industry memory
    in Mailbox 1 do not leak to Mailbox 2.
    """
    db, mb1 = test_db

    # Create Mailbox 2
    mb2 = Mailbox(
        email_address="support@clientb.com",
        is_active=False,
    )
    db.add(mb2)
    db.commit()
    db.refresh(mb2)

    classifier = HybridClassifier(db=db)

    # Classify in Mailbox 1
    email_mb1 = Email(
        mailbox_id=mb1.id,
        account_email=mb1.email_address,
        imap_uid="mb1-1",
        uid_validity=1,
        message_id="<mb1-001@clinic.com>",
        gmail_thread_id="th-mb1",
        sender="Clinic <clinic@city.com>",
        subject="Clinic booking app",
        body_text="We are a dental clinic needing patient management.",
        snippet="We are a dental clinic needing patient management.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email_mb1)
    db.commit()
    db.refresh(email_mb1)
    classifier.classify_email(email_mb1)

    # Check that Mailbox 2 contact query finds nothing
    mb2_contact = db.query(Contact).filter(
        Contact.mailbox_id == mb2.id,
        Contact.email_address == "clinic@city.com",
    ).first()
    assert mb2_contact is None

    # Classify same sender in Mailbox 2 with different context
    email_mb2 = Email(
        mailbox_id=mb2.id,
        account_email=mb2.email_address,
        imap_uid="mb2-1",
        uid_validity=1,
        message_id="<mb2-001@clinic.com>",
        gmail_thread_id="th-mb2",
        sender="Clinic <clinic@city.com>",
        subject="Quick question",
        body_text="Please send your rate card.",
        snippet="Please send your rate card.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email_mb2)
    db.commit()
    db.refresh(email_mb2)
    c_mb2 = classifier.classify_email(email_mb2)

    # In Mailbox 2, with no previous context, this short email should NOT inherit Mailbox 1's Healthcare industry
    assert c_mb2.target_industry == "Unknown"
    assert c_mb2.mailbox_id == mb2.id


# ==============================================================================
# Scenario 9: Manual Industry Correction & Audit Trail
# ==============================================================================

def test_scenario_9_manual_industry_correction_and_audit(test_db):
    """Scenario 9:
    User manually corrects an email's industry via the API or service.
    Verify:
    - Classification row updated.
    - ClassificationHistory records previous vs corrected values.
    - is_human_corrected is set to True.
    - Contact / Lead memory is updated.
    """
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    email = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="audit-1",
        uid_validity=1,
        message_id="<audit-001@firm.com>",
        gmail_thread_id="th-audit-1",
        sender="Legal Firm <law@firm.com>",
        subject="Website help",
        body_text="Hello, we need a corporate site.",
        snippet="Hello, we need a corporate site.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email)
    db.commit()
    db.refresh(email)

    c = classifier.classify_email(email)
    old_target = c.target_industry

    # Perform manual correction
    payload = IndustryCorrectionRequest(
        target_industry="Legal & Professional Services",
        sender_industry="Legal & Professional Services",
        sub_industry="Legal Services",
        notes="Corrected by account manager to Legal Services",
    )
    corrected = update_industry_classification(
        classification_id=c.id,
        payload=payload,
        db=db,
    )

    assert corrected.target_industry == "Legal & Professional Services"
    assert corrected.sender_industry == "Legal & Professional Services"
    assert corrected.sub_industry == "Legal Services"
    assert corrected.classification_method == "manual_correction"
    assert corrected.industry_requires_review is False

    # Check audit history
    history = db.query(ClassificationHistory).filter(
        ClassificationHistory.classification_id == c.id
    ).all()
    assert len(history) >= 1
    latest_hist = history[-1]
    assert latest_hist.corrected_values.get("target_industry") == "Legal & Professional Services"
    assert latest_hist.previous_values.get("target_industry") == old_target

    # Check contact industry memory
    contact = db.query(Contact).filter(Contact.id == c.contact_id).first()
    assert contact is not None
    assert contact.industry == "Legal & Professional Services"
    assert contact.sub_industry == "Legal Services"


# ==============================================================================
# Scenario 10: API Filtering and Analytics Endpoints
# ==============================================================================

def test_scenario_10_api_filtering_and_analytics(test_db):
    """Scenario 10:
    Verify endpoints:
    - GET /api/industries returns taxonomy.
    - GET /api/emails?industry=Healthcare filters emails correctly.
    - GET /api/analytics/industries returns distribution and intent metrics.
    """
    db, mb = test_db
    classifier = HybridClassifier(db=db)

    # Ingest two emails in different industries
    email_health = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="api-hosp",
        uid_validity=1,
        message_id="<api-hosp@health.com>",
        gmail_thread_id="th-api-hosp",
        sender="St. Jude <info@health.com>",
        subject="Hospital patient portal",
        body_text="We are a hospital looking for a patient portal.",
        snippet="We are a hospital looking for a patient portal.",
        received_at=datetime.now(timezone.utc),
    )
    email_retail = Email(
        mailbox_id=mb.id,
        account_email=mb.email_address,
        imap_uid="api-shop",
        uid_validity=1,
        message_id="<api-shop@retail.com>",
        gmail_thread_id="th-api-shop",
        sender="Fashion Store <sales@retail.com>",
        subject="Online retail boutique store",
        body_text="We run an online clothing store.",
        snippet="We run an online clothing store.",
        received_at=datetime.now(timezone.utc),
    )
    db.add(email_health)
    db.add(email_retail)
    db.commit()

    classifier.classify_email(email_health)
    classifier.classify_email(email_retail)

    # 1. Taxonomy endpoint
    taxonomy_res = get_industries_taxonomy()
    assert "Healthcare" in taxonomy_res.industries
    assert "IT & Software" in taxonomy_res.industries
    assert taxonomy_res.total_industries >= 15

    # 2. Email filtering by industry
    filter_res = list_emails(page=1, size=20, industry="Healthcare", db=db)
    assert filter_res.total >= 1
    for item in filter_res.items:
        c = item.classification
        assert c is not None
        assert c.target_industry == "Healthcare" or c.sender_industry == "Healthcare"

    # 3. Industry analytics aggregation
    analytics_res = get_industry_analytics(db=db)
    assert analytics_res.total_classified >= 2
    assert "Healthcare" in analytics_res.total_by_industry or any(
        d.target_industry == "Healthcare" for d in analytics_res.target_industry_distribution
    )
