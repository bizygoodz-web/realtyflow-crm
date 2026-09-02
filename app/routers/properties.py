from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=List[schemas.PropertyOut])
def list_properties(
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    return (
        db.query(models.Property)
        .filter(models.Property.agent_id == current.agent_id)
        .order_by(models.Property.id.desc())
        .all()
    )


@router.post("", response_model=schemas.PropertyOut, status_code=201)
def create_property(
    payload: schemas.PropertyCreate,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    prop = models.Property(
        agent_id=current.agent_id,
        seller_contact_id=payload.seller_contact_id,
        address=payload.address,
        mls_number=payload.mls_number,
        list_price=payload.list_price,
        status=payload.status or "active",
        days_on_market=0,
        beds=payload.beds,
        baths=payload.baths,
        sqft=payload.sqft,
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop
