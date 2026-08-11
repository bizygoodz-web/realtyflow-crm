from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("")
def list_workflows(
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    return db.query(models.Workflow).filter(models.Workflow.agent_id == current.agent_id).all()


@router.post("", status_code=201)
def create_workflow(
    payload: schemas.WorkflowCreate,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    workflow = models.Workflow(
        agent_id=current.agent_id,
        name=payload.name,
        trigger_event=payload.trigger_event,
        steps=[s.model_dump() for s in payload.steps],
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


@router.post("/enroll", status_code=201)
def enroll_contact(
    payload: schemas.WorkflowEnroll,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    contact = (
        db.query(models.Contact)
        .filter(models.Contact.id == payload.contact_id, models.Contact.agent_id == current.agent_id)
        .first()
    )
    workflow = (
        db.query(models.Workflow)
        .filter(models.Workflow.id == payload.workflow_id, models.Workflow.agent_id == current.agent_id)
        .first()
    )
    if not contact or not workflow:
        raise HTTPException(status_code=404, detail="Contact or workflow not found")

    enrollment = models.WorkflowEnrollment(contact_id=contact.id, workflow_id=workflow.id)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment
