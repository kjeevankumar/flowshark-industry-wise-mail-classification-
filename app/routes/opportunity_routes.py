"""FastAPI routes for Business Opportunity (Lead) management and tracking."""

from datetime import datetime, timezone
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.models.lead_model import Lead, LeadActivityHistory
from app.schemas.dashboard_schema import LeadRead
from app.services.mailbox_service import MailboxService

logger = logging.getLogger("gmail_fastapi.opportunities")

router = APIRouter(prefix="/api/opportunities", tags=["Business Opportunities"])


class UpdateOpportunityRequest(BaseModel):
    status: Optional[str] = Field(None, description="Stage: new, qualified, proposal_sent, negotiation, won, lost")
    priority: Optional[str] = Field(None, description="Priority: hot, warm, low")
    assigned_to: Optional[str] = Field(None, description="Employee name or email")
    estimated_value: Optional[float] = Field(None, description="Estimated deal value in USD")
    requested_solution_domain: Optional[str] = Field(None, description="Domain of requested solution")
    notes: Optional[str] = Field(None, description="Optional notes on update")


@router.get(
    "",
    response_model=List[LeadRead],
    summary="List Business Opportunities (Leads)",
)
def list_opportunities(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> List[LeadRead]:
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    query = db.query(Lead)
    if active_mb:
        query = query.filter(Lead.mailbox_id == active_mb.id)

    if status_filter:
        query = query.filter(Lead.status == status_filter.lower())
    if priority_filter:
        query = query.filter(Lead.priority == priority_filter.lower())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter((Lead.title.ilike(term)) | (Lead.business_context.ilike(term)))

    return query.order_by(Lead.updated_at.desc()).all()


@router.get(
    "/{lead_id}",
    response_model=LeadRead,
    summary="Get Opportunity Detail by ID",
)
def get_opportunity(
    lead_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LeadRead:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Opportunity {lead_id} not found.")
    return lead


@router.patch(
    "/{lead_id}",
    response_model=LeadRead,
    summary="Update Opportunity Status or Assignment",
)
def update_opportunity(
    lead_id: int,
    payload: UpdateOpportunityRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LeadRead:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Opportunity {lead_id} not found.")

    old_status = lead.status
    if payload.status and payload.status != old_status:
        lead.status = payload.status
        activity = LeadActivityHistory(
            mailbox_id=lead.mailbox_id,
            lead_id=lead.id,
            contact_id=lead.contact_id,
            activity_type="stage_transition",
            from_stage=old_status,
            to_stage=payload.status,
            description=f"Manual stage update from '{old_status}' to '{payload.status}': {payload.notes or 'No notes'}",
        )
        db.add(activity)

    if payload.priority:
        lead.priority = payload.priority
    if payload.assigned_to is not None:
        lead.assigned_to = payload.assigned_to
    if payload.estimated_value is not None:
        lead.estimated_value = payload.estimated_value
    if payload.requested_solution_domain is not None:
        lead.requested_solution_domain = payload.requested_solution_domain

    lead.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lead)
    return lead
