import os
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth, models
from ..database import get_db
from ..services.storage import build_key, get_upload_url, get_download_url

router = APIRouter(prefix="/documents", tags=["documents"])


class UploadUrlRequest(BaseModel):
    contact_id: str
    doc_type: str
    filename: str
    content_type: str = "application/pdf"


class DocumentCreate(BaseModel):
    contact_id: str
    doc_type: str
    file_url: Optional[str] = None
    key: Optional[str] = None
    status: Optional[str] = "draft"


class DocumentOut(BaseModel):
    id: str
    contact_id: str
    doc_type: str
    status: str
    file_url: Optional[str] = None
    download_url: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


def _get_owned_contact(db: Session, contact_id: str, agent_id: str) -> models.Contact:
    contact = (
        db.query(models.Contact)
        .filter(models.Contact.id == contact_id, models.Contact.agent_id == agent_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.get("/", response_model=List[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    docs = (
        db.query(models.Document)
        .join(models.Contact, models.Contact.id == models.Document.contact_id)
        .filter(models.Contact.agent_id == current.agent_id)
        .order_by(models.Document.created_at.desc())
        .all()
    )

    result = []
    for doc in docs:
        download_url = None
        if doc.file_url:
            try:
                download_url = get_download_url(doc.file_url)
            except Exception:
                download_url = None

        result.append(
            DocumentOut(
                id=str(doc.id),
                contact_id=str(doc.contact_id),
                doc_type=doc.doc_type,
                status=doc.status.value if hasattr(doc.status, "value") else str(doc.status),
                file_url=doc.file_url,
                download_url=download_url,
                created_at=doc.created_at.isoformat() if doc.created_at else None,
            )
        )
    return result


@router.post("/upload-url")
def generate_upload_url(
    payload: UploadUrlRequest,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    _get_owned_contact(db, payload.contact_id, current.agent_id)

    key = build_key(current.agent_id, payload.contact_id, payload.filename)
    try:
        upload_url = get_upload_url(key, payload.content_type)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate upload URL: {exc}",
        )
    return {"key": key, "upload_url": upload_url}


@router.post("/", response_model=DocumentOut)
def create_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    _get_owned_contact(db, payload.contact_id, current.agent_id)

    if payload.key:
        file_url = payload.key
    elif payload.file_url:
        file_url = payload.file_url
    else:
        raise HTTPException(status_code=400, detail="Either file_url or key is required")

    doc = models.Document(
        contact_id=payload.contact_id,
        uploaded_by=current.agent_id,
        doc_type=payload.doc_type,
        file_url=file_url,
        status=payload.status or "draft",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    download_url = None
    if doc.file_url:
        try:
            download_url = get_download_url(doc.file_url)
        except Exception:
            download_url = None

    return DocumentOut(
        id=str(doc.id),
        contact_id=str(doc.contact_id),
        doc_type=doc.doc_type,
        status=doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        file_url=doc.file_url,
        download_url=download_url,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
    )
