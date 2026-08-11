from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db
from ..services.enrollment import auto_enroll

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=List[schemas.ContactOut])
def list_contacts(
    status: Optional[str] = None,
    contact_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    q = db.query(models.Contact).filter(models.Contact.agent_id == current.agent_id)
    if status:
        q = q.filter(models.Contact.status == status)
    if contact_type:
        q = q.filter(models.Contact.contact_type == contact_type)
    return q.order_by(models.Contact.created_at.desc()).all()


@router.post("", response_model=schemas.ContactOut, status_code=201)
def create_contact(
    payload: schemas.ContactCreate,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    contact = models.Contact(
        agent_id=current.agent_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        contact_type=payload.contact_type,
        lead_source=payload.lead_source,
    )
    db.add(contact)
    db.flush()  # get contact.id before committing

    if payload.buyer_profile:
        db.add(models.BuyerProfile(contact_id=contact.id, **payload.buyer_profile.model_dump()))
    if payload.seller_profile:
        db.add(models.SellerProfile(contact_id=contact.id, **payload.seller_profile.model_dump()))

    # Log the intake as the first ledger entry
    db.add(models.Activity(
        contact_id=contact.id,
        agent_id=current.agent_id,
        type=models.ActivityType.note,
        content="Contact created via intake form",
        is_automated=True,
    ))

    # Drop the new contact into any "new_lead" drip campaigns this agent has configured
    auto_enroll(db, contact, trigger_event="new_lead")

    db.commit()
    db.refresh(contact)
    return contact


def _get_owned_contact(db: Session, contact_id: str, agent_id: str) -> models.Contact:
    contact = (
        db.query(models.Contact)
        .filter(models.Contact.id == contact_id, models.Contact.agent_id == agent_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.get("/{contact_id}", response_model=schemas.ContactOut)
def get_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    return _get_owned_contact(db, contact_id, current.agent_id)


@router.patch("/{contact_id}/status", response_model=schemas.ContactOut)
def update_status(
    contact_id: str,
    status: str,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    contact = _get_owned_contact(db, contact_id, current.agent_id)
    contact.status = status
    db.commit()
    db.refresh(contact)
    return contact


@router.get("/{contact_id}/activities", response_model=List[schemas.ActivityOut])
def contact_activities(
    contact_id: str,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    _get_owned_contact(db, contact_id, current.agent_id)  # ownership check
    return (
        db.query(models.Activity)
        .filter(models.Activity.contact_id == contact_id)
        .order_by(models.Activity.created_at.desc())
        .all()
    )
