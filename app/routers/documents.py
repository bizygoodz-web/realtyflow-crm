from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db
from ..services import storage, esign

router = APIRouter(prefix="/documents", tags=["documents"])


def _to_out(doc: models.Document) -> schemas.DocumentOut:
    """file_url holds the S3 key, never a public link - mint a short-lived
    signed download url per response instead of persisting one."""
    return schemas.DocumentOut(
        id=doc.id,
        contact_id=doc.contact_id,
        doc_type=doc.doc_type,
        status=doc.status,
        download_url=storage.get_download_url(doc.file_url) if doc.file_url else None,
        esign_provider_ref=doc.esign_provider_ref,
        created_at=doc.created_at,
    )


@router.get("", response_model=List[schemas.DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    docs = (
        db.query(models.Document)
        .join(models.Contact, models.Document.contact_id == models.Contact.id)
        .filter(models.Contact.agent_id == current.agent_id)
        .order_by(models.Document.created_at.desc())
        .all()
    )
    return [_to_out(d) for d in docs]


@router.post("/upload-url", response_model=schemas.DocumentUploadURLResponse)
def get_upload_url(
    payload: schemas.DocumentUploadURLRequest,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    """Step 1 of upload: mint a presigned S3 PUT url. The file goes straight
    from the browser to S3 - it never passes through this API."""
    contact = (
        db.query(models.Contact)
        .filter(models.Contact.id == payload.contact_id, models.Contact.agent_id == current.agent_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    key = storage.build_key(current.agent_id, payload.contact_id, payload.filename)
    url = storage.get_upload_url(key, payload.content_type)
    return schemas.DocumentUploadURLResponse(key=key, upload_url=url)


@router.post("", response_model=schemas.DocumentOut, status_code=201)
def confirm_upload(
    payload: schemas.DocumentConfirm,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    """Step 2 of upload: after the browser PUTs the file to S3 using the
    presigned url, call this with the same key to create the Document row."""
    contact = (
        db.query(models.Contact)
        .filter(models.Contact.id == payload.contact_id, models.Contact.agent_id == current.agent_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    doc = models.Document(
        contact_id=payload.contact_id,
        deal_id=payload.deal_id,
        uploaded_by=current.agent_id,
        doc_type=payload.doc_type,
        file_url=payload.key,
        status=models.DocStatus.draft,
    )
    db.add(doc)
    db.add(models.Activity(
        contact_id=payload.contact_id,
        deal_id=payload.deal_id,
        agent_id=current.agent_id,
        type=models.ActivityType.doc_sent,
        content=f"{payload.doc_type} uploaded",
        is_automated=True,
    ))
    db.commit()
    db.refresh(doc)
    return _to_out(doc)


def _owned_document(db: Session, document_id: str, agent_id: str) -> models.Document:
    doc = (
        db.query(models.Document)
        .join(models.Contact, models.Document.contact_id == models.Contact.id)
        .filter(models.Document.id == document_id, models.Contact.agent_id == agent_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.patch("/{document_id}/status", response_model=schemas.DocumentOut)
def update_document_status(
    document_id: str,
    payload: schemas.DocumentStatusUpdate,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    doc = _owned_document(db, document_id, current.agent_id)
    doc.status = payload.status
    db.commit()
    db.refresh(doc)
    return _to_out(doc)


@router.post("/{document_id}/send-for-signature", response_model=schemas.ESignSendResponse)
def send_for_signature(
    document_id: str,
    payload: schemas.ESignSendRequest,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    doc = _owned_document(db, document_id, current.agent_id)

    result = esign.create_envelope(doc.id, payload.signer_email, payload.signer_name)
    doc.esign_provider_ref = result["envelope_id"]
    doc.status = models.DocStatus.sent

    db.add(models.Activity(
        contact_id=doc.contact_id,
        deal_id=doc.deal_id,
        agent_id=current.agent_id,
        type=models.ActivityType.doc_sent,
        content=f"Sent for signature: {doc.doc_type} -> {payload.signer_email}",
        is_automated=True,
    ))
    db.commit()
    return schemas.ESignSendResponse(**result)


@router.post("/esign-webhook", include_in_schema=False)
async def esign_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_esign_signature: str = Header(default=""),
):
    """Public endpoint the e-signature provider calls when a document's
    status changes. No auth.require_agent here - the caller is the
    provider, not a logged-in user - so the signature check IS the auth."""
    raw_body = await request.body()
    if not esign.verify_webhook_signature(raw_body, x_esign_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    envelope_id = payload.get("envelope_id")
    provider_status = payload.get("status", "")

    doc = db.query(models.Document).filter(models.Document.esign_provider_ref == envelope_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="No matching document for this envelope")

    doc.status = esign.normalize_status(provider_status)
    db.add(models.Activity(
        contact_id=doc.contact_id,
        deal_id=doc.deal_id,
        agent_id=doc.uploaded_by,
        type=models.ActivityType.doc_sent,
        content=f"{doc.doc_type} status updated to {doc.status} via e-signature webhook",
        is_automated=True,
    ))
    db.commit()
    return {"received": True}
