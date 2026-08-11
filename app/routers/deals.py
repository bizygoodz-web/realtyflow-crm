from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/deals", tags=["deals"])


def _owned_deal(db: Session, deal_id: str, agent_id: str) -> models.Deal:
    deal = (
        db.query(models.Deal)
        .filter(models.Deal.id == deal_id, models.Deal.agent_id == agent_id)
        .first()
    )
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal


@router.get("", response_model=List[schemas.DealOut])
def list_deals(
    stage: Optional[str] = None,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    q = db.query(models.Deal).filter(models.Deal.agent_id == current.agent_id)
    if stage:
        q = q.filter(models.Deal.stage == stage)
    return q.order_by(models.Deal.created_at.desc()).all()


@router.post("", response_model=schemas.DealOut, status_code=201)
def create_deal(
    payload: schemas.DealCreate,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    # verify contact belongs to this agent before attaching a deal to it
    contact = (
        db.query(models.Contact)
        .filter(models.Contact.id == payload.contact_id, models.Contact.agent_id == current.agent_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    deal = models.Deal(
        contact_id=payload.contact_id,
        agent_id=current.agent_id,
        deal_type=payload.deal_type,
        property_id=payload.property_id,
        list_price=payload.list_price,
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


@router.patch("/{deal_id}/stage", response_model=schemas.DealOut)
def move_stage(
    deal_id: str,
    payload: schemas.DealStageUpdate,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    """Drag-and-drop pipeline move. Also drops a ledger entry automatically."""
    deal = _owned_deal(db, deal_id, current.agent_id)
    old_stage = deal.stage
    deal.stage = payload.stage

    db.add(models.Activity(
        contact_id=deal.contact_id,
        deal_id=deal.id,
        agent_id=current.agent_id,
        type=models.ActivityType.note,
        content=f"Stage moved from {old_stage} to {payload.stage}",
        is_automated=True,
    ))

    db.commit()
    db.refresh(deal)
    return deal
