from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/activities", tags=["activities"])


@router.post("", response_model=schemas.ActivityOut, status_code=201)
def log_activity(
    payload: schemas.ActivityCreate,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    contact = (
        db.query(models.Contact)
        .filter(models.Contact.id == payload.contact_id, models.Contact.agent_id == current.agent_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    activity = models.Activity(
        contact_id=payload.contact_id,
        deal_id=payload.deal_id,
        agent_id=current.agent_id,
        type=payload.type,
        content=payload.content,
        is_automated=False,
    )
    db.add(activity)
    contact.last_contacted_at = activity.created_at
    db.commit()
    db.refresh(activity)
    return activity
