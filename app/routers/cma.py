from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/cma", tags=["cma"])


def _estimate_price(subject: dict, comparables: list) -> float:
    """Simple $/sqft average across comparables, scaled to the subject's sqft.

    This is a starting heuristic, not a valuation model - swap in a real
    comps-adjustment algorithm (or an external AVM API) when ready.
    """
    sqft = subject.get("sqft") or 0
    if not comparables or not sqft:
        return 0.0
    price_per_sqft = [
        c["sale_price"] / c["sqft"] for c in comparables if c.get("sqft") and c.get("sale_price")
    ]
    if not price_per_sqft:
        return 0.0
    avg = sum(price_per_sqft) / len(price_per_sqft)
    return round(avg * sqft, -3)  # round to nearest $1,000


@router.post("", response_model=schemas.CMAOut, status_code=201)
def generate_cma(
    payload: schemas.CMAGenerate,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    suggested = _estimate_price(payload.subject_property, payload.comparables)
    report = models.CMAReport(
        deal_id=payload.deal_id,
        subject_property=payload.subject_property,
        comparables=payload.comparables,
        suggested_price=suggested,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.post("/{report_id}/share")
def share_cma(
    report_id: str,
    contact_id: str,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    report = db.query(models.CMAReport).filter(models.CMAReport.id == report_id).first()
    if report:
        report.shared_with_contact_id = contact_id
        db.commit()
    return {"shared": True}
