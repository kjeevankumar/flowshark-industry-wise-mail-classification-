"""FastAPI routes for AI classification, batch inference, manual corrections, and metrics."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.models.classification_model import Classification, ClassificationHistory
from app.models.contact_model import Contact
from app.models.email_model import Email
from app.models.lead_model import Lead, LeadActivityHistory
from app.schemas.dashboard_schema import (
    ClassificationCorrectionRequest,
    ClassificationHistoryRead,
    ClassificationRead,
    ClassifyBatchRequest,
    ClassifyBatchResponse,
    IndustryCorrectionRequest,
    IndustryTaxonomyResponse,
)
from app.services.hybrid_classifier import HybridClassifier
from app.services.industry_taxonomy import (
    get_taxonomy,
    normalize_industry,
    is_valid_industry,
)
from app.services.mailbox_service import MailboxService

logger = logging.getLogger("gmail_fastapi.classification_routes")

router = APIRouter(prefix="/api/classification", tags=["AI Classification"])


@router.post(
    "/classify/{email_id}",
    response_model=ClassificationRead,
    summary="Classify a Single Email (Active Mailbox Only)",
    description="Run the hybrid AI classification pipeline on a specific email and persist the result.",
)
def classify_single_email(
    email_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ClassificationRead:
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    query = db.query(Email).filter(Email.id == email_id)
    if active_mb:
        query = query.filter(Email.mailbox_id == active_mb.id)

    email_record = query.first()
    if not email_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email with ID {email_id} not found in active mailbox.",
        )

    classifier = HybridClassifier(db=db, settings=settings)
    try:
        classification = classifier.classify_email(email_record)
        return classification
    except Exception as err:
        logger.error("Failed to classify email %s: %s", email_id, str(err))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification failed: {str(err)}",
        )


@router.post(
    "/classify-batch",
    response_model=ClassifyBatchResponse,
    summary="Classify a Batch of Emails (Active Mailbox Only)",
    description="Classify multiple emails in batch with user-controlled limits.",
)
def classify_batch(
    request: ClassifyBatchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ClassifyBatchResponse:
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    query = db.query(Email)
    if active_mb:
        query = query.filter(Email.mailbox_id == active_mb.id)

    if request.email_ids:
        query = query.filter(Email.id.in_(request.email_ids))
    elif request.unclassified_only:
        query = query.outerjoin(Email.classification).filter(Classification.id.is_(None))

    emails_to_process = query.order_by(Email.received_at.desc().nullslast()).limit(request.limit).all()

    classifier = HybridClassifier(db=db, settings=settings)
    successful = []
    failed_count = 0

    for email_item in emails_to_process:
        try:
            res = classifier.classify_email(email_item)
            successful.append(res)
        except Exception as err:
            logger.warning("Batch item classification failed for email %s: %s", email_item.id, str(err))
            failed_count += 1

    return ClassifyBatchResponse(
        processed_count=len(emails_to_process),
        successful_count=len(successful),
        failed_count=failed_count,
        results=successful,
    )


@router.get(
    "/results",
    response_model=List[ClassificationRead],
    summary="List Recent Classification Results (Active Mailbox Only)",
)
def list_classification_results(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    requires_review: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> List[ClassificationRead]:
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    limit_val = limit if isinstance(limit, int) else 50
    offset_val = offset if isinstance(offset, int) else 0

    query = db.query(Classification)
    if active_mb:
        query = query.filter(Classification.mailbox_id == active_mb.id)

    if isinstance(requires_review, bool):
        query = query.filter(Classification.requires_human_review == requires_review)
    return query.order_by(Classification.created_at.desc()).offset(offset_val).limit(limit_val).all()


@router.get(
    "/categories",
    summary="Get Supported Classification Taxonomies and Enums",
)
def get_categories() -> Dict[str, Any]:
    return {
        "relationships": ["new_contact", "existing_lead", "existing_customer", "unknown"],
        "intents": [
            "new_enquiry",
            "negotiation",
            "follow_up",
            "business_clarification",
            "purchase_order",
            "invoice",
            "complaint",
            "other",
        ],
        "lead_stages": [
            "new",
            "qualified",
            "proposal_sent",
            "negotiation",
            "won",
            "lost",
            "unknown",
        ],
        "dashboard_filters": [
            "new_leads",
            "negotiations",
            "follow_ups",
            "business_clarifications",
            "existing_leads",
            "purchase_orders",
            "invoices",
            "needs_review",
        ],
    }


@router.get(
    "/industries",
    response_model=IndustryTaxonomyResponse,
    summary="Get Centralized Industry Taxonomy",
    description="Retrieve all supported primary industries and their associated sub-industries.",
)
def get_industries_taxonomy() -> IndustryTaxonomyResponse:
    tax = get_taxonomy()
    return IndustryTaxonomyResponse(
        industries=tax,
        total_industries=len(tax),
    )


@router.patch(
    "/{classification_id}/correct",
    response_model=ClassificationRead,
    summary="Manually Correct a Classification",
    description="Save a corrected classification, archive previous values to history, and mark as manually reviewed.",
)
def correct_classification(
    classification_id: int,
    correction: ClassificationCorrectionRequest,
    db: Session = Depends(get_db),
) -> ClassificationRead:
    record = db.query(Classification).filter(Classification.id == classification_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Classification ID {classification_id} not found.",
        )

    # Save previous state in audit trail
    previous_state = {
        "relationship": record.relationship,
        "intent": record.intent,
        "lead_stage": record.lead_stage,
        "confidence": record.confidence,
        "sender_industry": getattr(record, "sender_industry", "Unknown"),
        "target_industry": getattr(record, "target_industry", "Unknown"),
        "sub_industry": getattr(record, "sub_industry", None),
        "industry_confidence": getattr(record, "industry_confidence", 0.0),
        "classification_method": record.classification_method,
    }

    corrected_state = {}
    if correction.relationship:
        record.relationship = correction.relationship
        corrected_state["relationship"] = correction.relationship
    if correction.intent:
        record.intent = correction.intent
        corrected_state["intent"] = correction.intent
    if correction.lead_stage:
        record.lead_stage = correction.lead_stage
        corrected_state["lead_stage"] = correction.lead_stage

    # Handle Industry corrections
    if correction.sender_industry:
        norm_s = normalize_industry(correction.sender_industry)
        record.sender_industry = norm_s
        corrected_state["sender_industry"] = norm_s
        record.industry_confidence = 1.0
        record.industry_requires_review = False
    if correction.target_industry:
        norm_t = normalize_industry(correction.target_industry)
        record.target_industry = norm_t
        corrected_state["target_industry"] = norm_t
        record.industry_confidence = 1.0
        record.industry_requires_review = False
    if correction.sub_industry:
        record.sub_industry = correction.sub_industry
        corrected_state["sub_industry"] = correction.sub_industry

    # Mark as human corrected
    record.classification_method = "manual_correction"
    record.requires_human_review = False
    record.updated_at = datetime.now(timezone.utc)

    # Sync correction to Contact entity if linked
    if record.contact_id:
        contact = db.query(Contact).filter(Contact.id == record.contact_id).first()
        if contact:
            if correction.relationship:
                contact.relationship_type = correction.relationship
            if correction.lead_stage:
                contact.current_lead_stage = correction.lead_stage
            if correction.sender_industry:
                contact.industry = normalize_industry(correction.sender_industry)
            if correction.sub_industry:
                contact.sub_industry = correction.sub_industry

    # Sync correction to Lead entity if linked
    if record.lead_id:
        lead = db.query(Lead).filter(Lead.id == record.lead_id).first()
        if lead:
            if correction.lead_stage:
                old_lead_stage = lead.status
                lead.status = correction.lead_stage
                lead.updated_at = datetime.now(timezone.utc)
                lead_activity = LeadActivityHistory(
                    mailbox_id=record.mailbox_id,
                    lead_id=lead.id,
                    contact_id=record.contact_id,
                    email_id=record.email_id,
                    activity_type="manual_correction",
                    from_stage=old_lead_stage,
                    to_stage=correction.lead_stage,
                    description=f"Manual correction by user: {correction.notes or 'Stage updated'}",
                )
                db.add(lead_activity)
            if correction.target_industry:
                lead.target_industry = normalize_industry(correction.target_industry)
            if correction.sub_industry:
                lead.sub_industry = correction.sub_industry

    # Record history
    history_entry = ClassificationHistory(
        mailbox_id=record.mailbox_id,
        email_id=record.email_id,
        classification_id=record.id,
        previous_values=previous_state,
        corrected_values=corrected_state,
        notes=correction.notes,
        corrected_by="user",
        corrected_at=datetime.now(timezone.utc),
    )
    db.add(history_entry)
    db.commit()
    db.refresh(record)

    logger.info("Classification %s corrected by user: %s -> %s", classification_id, previous_state, corrected_state)
    return record


@router.put(
    "/{classification_id}/industry",
    response_model=ClassificationRead,
    summary="Update Industry Classification (Section 9)",
    description="Allow authorized users to correct sender industry, target industry, and sub-industry.",
)
def update_industry_classification(
    classification_id: int,
    payload: IndustryCorrectionRequest,
    db: Session = Depends(get_db),
) -> ClassificationRead:
    record = db.query(Classification).filter(Classification.id == classification_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Classification ID {classification_id} not found.",
        )

    # Validate industry taxonomy if provided
    if payload.sender_industry and not is_valid_industry(payload.sender_industry):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid sender industry '{payload.sender_industry}'. Must be a recognized taxonomy value.",
        )
    if payload.target_industry and not is_valid_industry(payload.target_industry):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid target industry '{payload.target_industry}'. Must be a recognized taxonomy value.",
        )

    previous_state = {
        "sender_industry": getattr(record, "sender_industry", "Unknown"),
        "target_industry": getattr(record, "target_industry", "Unknown"),
        "sub_industry": getattr(record, "sub_industry", None),
        "industry_confidence": getattr(record, "industry_confidence", 0.0),
    }

    corrected_state = {}
    if payload.sender_industry:
        norm_s = normalize_industry(payload.sender_industry)
        record.sender_industry = norm_s
        corrected_state["sender_industry"] = norm_s

    if payload.target_industry:
        norm_t = normalize_industry(payload.target_industry)
        record.target_industry = norm_t
        corrected_state["target_industry"] = norm_t

    if payload.sub_industry is not None:
        record.sub_industry = payload.sub_industry
        corrected_state["sub_industry"] = payload.sub_industry

    record.industry_confidence = 1.0  # Manually verified
    record.industry_requires_review = False
    record.classification_method = "manual_correction"
    record.industry_reason = f"Manually verified by user: {payload.notes or 'User industry override.'}"
    record.updated_at = datetime.now(timezone.utc)

    # Update Contact industry memory
    if record.contact_id and payload.sender_industry:
        contact = db.query(Contact).filter(Contact.id == record.contact_id).first()
        if contact:
            contact.industry = normalize_industry(payload.sender_industry)
            if payload.sub_industry:
                contact.sub_industry = payload.sub_industry

    # Update Lead target industry
    if record.lead_id and payload.target_industry:
        lead = db.query(Lead).filter(Lead.id == record.lead_id).first()
        if lead:
            lead.target_industry = normalize_industry(payload.target_industry)
            if payload.sub_industry:
                lead.sub_industry = payload.sub_industry

    # Record history
    history_entry = ClassificationHistory(
        mailbox_id=record.mailbox_id,
        email_id=record.email_id,
        classification_id=record.id,
        previous_values=previous_state,
        corrected_values=corrected_state,
        notes=payload.notes or "Manual industry correction",
        corrected_by="user",
        corrected_at=datetime.now(timezone.utc),
    )
    db.add(history_entry)
    db.commit()
    db.refresh(record)

    logger.info("Industry classification %s updated by user: %s -> %s", classification_id, previous_state, corrected_state)
    return record


@router.post(
    "/backfill",
    summary="Reclassify All Emails Chronologically with Context Awareness",
    description="Chronologically reviews all stored emails, recovers missing conversation context, updates relationships, and records audit history.",
)
def backfill_classifications(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()
    classifier = HybridClassifier(db=db, settings=settings)
    result = classifier.backfill_reclassify_all(mailbox_id=active_mb.id if active_mb else None)
    return result


@router.get(
    "/{email_id}/history",
    response_model=List[ClassificationHistoryRead],
    summary="Get Classification Audit History for an Email",
)
def get_classification_history(
    email_id: int,
    db: Session = Depends(get_db),
) -> List[ClassificationHistoryRead]:
    return (
        db.query(ClassificationHistory)
        .filter(ClassificationHistory.email_id == email_id)
        .order_by(ClassificationHistory.corrected_at.desc())
        .all()
    )


@router.get(
    "/{email_id}/context",
    summary="Get Context and Related Lead for an Email",
)
def get_email_context(
    email_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    from app.services.context_service import ContextService
    cs = ContextService(db=db)
    ctx = cs.build_conversation_context(email)
    return {
        "has_context": ctx.has_context,
        "sender_email": ctx.sender_email,
        "sender_name": ctx.sender_name,
        "contact_id": ctx.contact_id,
        "contact_relationship": ctx.contact_relationship,
        "contact_lead_stage": ctx.contact_lead_stage,
        "contact_company": ctx.contact_company,
        "lead_id": ctx.lead_id,
        "lead_title": ctx.lead_title,
        "lead_stage": ctx.lead_stage,
        "lead_business_context": ctx.lead_business_context,
        "context_summary": ctx.context_summary,
        "context_used": ctx.context_used,
        "prior_emails": ctx.prior_emails,
        "prior_classifications": ctx.prior_classifications,
    }


@router.get(
    "/metrics",
    summary="Get Classification Performance and Distribution Metrics (Active Mailbox Only)",
)
def get_classification_metrics(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    query = db.query(Classification)
    hist_q = db.query(ClassificationHistory)

    if active_mb:
        query = query.filter(Classification.mailbox_id == active_mb.id)
        hist_q = hist_q.filter(ClassificationHistory.mailbox_id == active_mb.id)

    total_classifications = query.count()
    needs_review = query.filter(Classification.requires_human_review == True).count()  # noqa: E712
    human_corrections = hist_q.count()

    # Intent distribution
    from sqlalchemy import func
    intent_counts = (
        query.with_entities(Classification.intent, func.count(Classification.id))
        .group_by(Classification.intent)
        .all()
    )
    relationship_counts = (
        query.with_entities(Classification.relationship, func.count(Classification.id))
        .group_by(Classification.relationship)
        .all()
    )
    stage_counts = (
        query.with_entities(Classification.lead_stage, func.count(Classification.id))
        .group_by(Classification.lead_stage)
        .all()
    )

    return {
        "total_classified": total_classifications,
        "needs_review_count": needs_review,
        "human_corrections_count": human_corrections,
        "human_correction_rate": round(human_corrections / max(1, total_classifications), 3),
        "intents": {row[0]: row[1] for row in intent_counts},
        "relationships": {row[0]: row[1] for row in relationship_counts},
        "lead_stages": {row[0]: row[1] for row in stage_counts},
    }

