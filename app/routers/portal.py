"""
Client Portal endpoints. `current.sub` IS the contact_id from the client's
JWT - there is no contact_id parameter anywhere in this file. A buyer or
seller can only ever see rows where contact_id == current.sub. This is the
enforcement point for "clients can only access their specific deal portal."
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db
from ..services import storage

router = APIRouter(prefix="/portal", tags=["client-portal"])


@router.get("/me", response_model=schemas.ContactOut)
def my_profile(
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_client),
):
    contact = db.query(models.Contact).filter(models.Contact.id == current.sub).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Not found")
    return contact


@router.get("/saved-listings")
def my_saved_listings(
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_client),
):
    """Buyer view: listings the agent has curated for them."""
    return (
        db.query(models.SavedListing)
        .filter(models.SavedListing.buyer_contact_id == current.sub)
        .all()
    )


@router.patch("/saved-listings/{listing_id}/feedback")
def submit_feedback(
    listing_id: str,
    feedback: str,
    rating: int,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_client),
):
    listing = (
        db.query(models.SavedListing)
        .filter(models.SavedListing.id == listing_id, models.SavedListing.buyer_contact_id == current.sub)
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Not found")
    listing.buyer_feedback = feedback
    listing.feedback_rating = rating
    listing.status = "interested" if rating >= 4 else "passed"
    db.commit()
    return {"updated": True}


@router.get("/showings")
def my_showings(
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_client),
):
    """Seller view: scheduled showings + feedback for their listing."""
    contact = db.query(models.Contact).filter(models.Contact.id == current.sub).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Not found")
    properties = db.query(models.Property).filter(models.Property.seller_contact_id == current.sub).all()
    property_ids = [p.id for p in properties]
    return (
        db.query(models.Showing)
        .filter(models.Showing.property_id.in_(property_ids))
        .order_by(models.Showing.scheduled_at.desc())
        .all()
    )


@router.get("/deals", response_model=List[schemas.DealOut])
def my_deals(
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_client),
):
    """Seller view: active offer statuses. Buyer view: their own deal progress."""
    return db.query(models.Deal).filter(models.Deal.contact_id == current.sub).all()


def _doc_to_out(doc: models.Document) -> schemas.DocumentOut:
    return schemas.DocumentOut(
        id=doc.id,
        contact_id=doc.contact_id,
        doc_type=doc.doc_type,
        status=doc.status,
        download_url=storage.get_download_url(doc.file_url) if doc.file_url else None,
        esign_provider_ref=doc.esign_provider_ref,
        created_at=doc.created_at,
    )


@router.get("/documents", response_model=List[schemas.DocumentOut])
def my_documents(
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_client),
):
    """Document signing statuses, e.g. pre-approval letters, disclosures."""
    docs = (
        db.query(models.Document)
        .filter(models.Document.contact_id == current.sub)
        .order_by(models.Document.created_at.desc())
        .all()
    )
    return [_doc_to_out(d) for d in docs]


@router.post("/documents/upload-url", response_model=schemas.DocumentUploadURLResponse)
def my_upload_url(
    doc_type: str,
    filename: str,
    content_type: str = "application/pdf",
    current: auth.TokenData = Depends(auth.require_client),
):
    """Step 1: buyer requests a presigned url to upload e.g. a pre-approval letter."""
    key = storage.build_key(current.agent_id, current.sub, filename)
    url = storage.get_upload_url(key, content_type)
    return schemas.DocumentUploadURLResponse(key=key, upload_url=url)


@router.post("/documents/confirm", response_model=schemas.DocumentOut, status_code=201)
def confirm_my_upload(
    doc_type: str,
    key: str,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_client),
):
    """Step 2: after the browser PUTs the file to S3, confirm it here -
    always tagged to the caller's own contact_id, never a passed-in one."""
    doc = models.Document(
        contact_id=current.sub,
        doc_type=doc_type,
        file_url=key,
        status=models.DocStatus.sent,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _doc_to_out(doc)
