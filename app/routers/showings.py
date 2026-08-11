from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, auth
from ..database import get_db
from ..services.enrollment import auto_enroll

router = APIRouter(prefix="/showings", tags=["showings"])


class ShowingCreate(BaseModel):
    property_id: str
    buyer_contact_id: Optional[str] = None
    scheduled_at: datetime
    type: str = "private"


class ShowingFeedback(BaseModel):
    feedback_text: str
    feedback_rating: int


@router.post("", status_code=201)
def schedule_showing(
    payload: ShowingCreate,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    showing = models.Showing(
        property_id=payload.property_id,
        buyer_contact_id=payload.buyer_contact_id,
        agent_id=current.agent_id,
        scheduled_at=payload.scheduled_at,
        type=payload.type,
    )
    db.add(showing)
    db.commit()
    db.refresh(showing)
    return showing


@router.patch("/{showing_id}/feedback")
def log_feedback(
    showing_id: str,
    payload: ShowingFeedback,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    showing = (
        db.query(models.Showing)
        .filter(models.Showing.id == showing_id, models.Showing.agent_id == current.agent_id)
        .first()
    )
    if not showing:
        raise HTTPException(status_code=404, detail="Showing not found")

    showing.feedback_text = payload.feedback_text
    showing.feedback_rating = payload.feedback_rating

    db.add(models.Activity(
        contact_id=showing.buyer_contact_id,
        agent_id=current.agent_id,
        type=models.ActivityType.showing,
        content=f"Showing feedback: {payload.feedback_text} ({payload.feedback_rating}/5)",
        is_automated=False,
    ))

    # Fire any "post_showing" drip campaign this agent has configured
    if showing.buyer_contact_id:
        contact = db.query(models.Contact).get(showing.buyer_contact_id)
        if contact:
            auto_enroll(db, contact, trigger_event="post_showing")

    db.commit()
    db.refresh(showing)
    return showing
