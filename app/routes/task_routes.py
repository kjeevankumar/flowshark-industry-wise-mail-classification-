"""FastAPI routes for actionable business Tasks and Follow-ups."""

from datetime import datetime, timezone
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.models.task_model import Task
from app.schemas.dashboard_schema import TaskRead
from app.services.mailbox_service import MailboxService

logger = logging.getLogger("gmail_fastapi.tasks")

router = APIRouter(prefix="/api/tasks", tags=["Actionable Tasks"])


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=2)
    lead_id: Optional[int] = None
    email_id: Optional[int] = None
    contact_id: Optional[int] = None
    assigned_to: Optional[str] = None
    priority: str = Field(default="medium")
    due_date: Optional[datetime] = None
    description: Optional[str] = None


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None  # pending, completed, cancelled
    priority: Optional[str] = None  # high, medium, low
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    description: Optional[str] = None


@router.get(
    "",
    response_model=List[TaskRead],
    summary="List Tasks",
)
def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    lead_id: Optional[int] = Query(None),
    email_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> List[TaskRead]:
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    query = db.query(Task)
    if active_mb:
        query = query.filter(Task.mailbox_id == active_mb.id)
    if status_filter:
        query = query.filter(Task.status == status_filter.lower())
    if priority_filter:
        query = query.filter(Task.priority == priority_filter.lower())
    if lead_id:
        query = query.filter(Task.lead_id == lead_id)
    if email_id:
        query = query.filter(Task.email_id == email_id)

    return query.order_by(Task.created_at.desc()).all()


@router.post(
    "",
    response_model=TaskRead,
    summary="Create a New Task",
)
def create_task(
    payload: CreateTaskRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TaskRead:
    mailbox_service = MailboxService(db=db, settings=settings)
    active_mb = mailbox_service.get_active_mailbox()

    task = Task(
        tenant_id=1,
        mailbox_id=active_mb.id if active_mb else None,
        lead_id=payload.lead_id,
        email_id=payload.email_id,
        contact_id=payload.contact_id,
        title=payload.title,
        description=payload.description,
        assigned_to=payload.assigned_to,
        priority=payload.priority,
        due_date=payload.due_date,
        status="pending",
        who_owes_response="company",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch(
    "/{task_id}",
    response_model=TaskRead,
    summary="Update Task Status or Assignment",
)
def update_task(
    task_id: int,
    payload: UpdateTaskRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TaskRead:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found.")

    if payload.title:
        task.title = payload.title
    if payload.status:
        task.status = payload.status
        if payload.status == "completed":
            task.completed_at = datetime.now(timezone.utc)
        elif payload.status == "pending":
            task.completed_at = None
    if payload.priority:
        task.priority = payload.priority
    if payload.assigned_to is not None:
        task.assigned_to = payload.assigned_to
    if payload.due_date is not None:
        task.due_date = payload.due_date
    if payload.description is not None:
        task.description = payload.description

    db.commit()
    db.refresh(task)
    return task
