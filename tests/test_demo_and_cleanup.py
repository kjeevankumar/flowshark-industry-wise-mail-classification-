"""Tests for Demo Email Testing, Simulation, Executive Explanations, and Non-Business Cleanup."""

from app.config import get_settings
from app.db.session import SessionLocal
from app.models.email_model import Email
from app.models.classification_model import Classification
from app.models.mailbox_model import Mailbox
from app.routes.classification_routes import (
    get_demo_presets,
    simulate_or_test_demo_email as run_demo_email,
    DemoEmailTestRequest,
)
from app.routes.email_inbox_routes import (
    delete_email,
    cleanup_non_business,
)


def test_get_demo_presets():
    """Verify demo presets endpoint returns all 5 presets."""
    data = get_demo_presets()
    assert "presets" in data
    presets = data["presets"]
    assert "qualified_lead" in presets
    assert "negotiation" in presets
    assert "new_lead" in presets
    assert "existing_lead" in presets
    assert "security_alert" in presets


def test_simulate_qualified_lead_demo():
    """Test demo simulation of a qualified lead and verify 'Why Qualified' explanation."""
    db = SessionLocal()
    settings = get_settings()
    try:
        req = DemoEmailTestRequest(
            preset_key="qualified_lead",
            inject_into_inbox=False,
        )
        data = run_demo_email(req, db=db, settings=settings)
        assert data["is_injected"] is False

        cls = data["classification"]
        assert cls["is_business_relevant"] is True
        assert cls["lead_stage"] == "qualified"
        assert cls["pipeline_category"] in ("new_leads", "clarifications", "purchase_orders")

        breakdown = data["executive_breakdown"]
        assert "Why Qualified" in breakdown["why_lead_stage"]
        assert "Manufacturing" in breakdown["why_industry"] or "Software" in breakdown["why_industry"]
    finally:
        db.close()


def test_simulate_security_alert_demo():
    """Test demo simulation of Google security alert and verify 'Why Unknown' explanation."""
    db = SessionLocal()
    settings = get_settings()
    try:
        req = DemoEmailTestRequest(
            preset_key="security_alert",
            inject_into_inbox=False,
        )
        data = run_demo_email(req, db=db, settings=settings)

        cls = data["classification"]
        assert cls["is_business_relevant"] is False
        assert cls["lead_stage"] in ("not_applicable", "unknown")
        assert cls["pipeline_category"] is None

        breakdown = data["executive_breakdown"]
        assert "Why Unknown" in breakdown["why_lead_stage"] or "Non-Business" in breakdown["why_relevance"]
    finally:
        db.close()


def test_delete_email_and_cleanup_endpoints():
    """Test deleting single email and bulk purging non-business notifications."""
    db = SessionLocal()
    settings = get_settings()
    try:
        # Create a test email with non-business classification
        mb = db.query(Mailbox).first()
        mb_id = mb.id if mb else 1
        account_email = mb.email_address if mb else "test@flowshark.local"

        test_email = Email(
            mailbox_id=mb_id,
            account_email=account_email,
            imap_uid="test_purge_999",
            uid_validity=1,
            sender="Google <no-reply@accounts.google.com>",
            subject="Security Alert - Purge Test",
            snippet="Test snippet",
            body_text="Security notification test",
        )
        db.add(test_email)
        db.commit()
        db.refresh(test_email)

        test_cls = Classification(
            mailbox_id=mb_id,
            email_id=test_email.id,
            relevance_category="account_security_notification",
            is_business_relevant=False,
            pipeline_category=None,
            relationship="unknown",
            intent="other",
            lead_stage="unknown",
            confidence=0.98,
            classification_method="rule_based",
        )
        db.add(test_cls)
        db.commit()
        email_id = test_email.id

        # Test single delete
        del_res = delete_email(email_id, db=db, settings=settings)
        assert del_res["success"] is True

        # Test bulk cleanup non-business
        cleanup_res = cleanup_non_business(db=db, settings=settings)
        assert cleanup_res["success"] is True
    finally:
        db.close()
