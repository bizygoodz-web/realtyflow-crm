import os
import uuid
import boto3
from botocore.config import Config
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

# Import your database models and session dependency
from ..database import get_db
from .. import models, auth

router = APIRouter(prefix="/documents", tags=["documents"])

# --- S3 Configuration ---
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    config=Config(signature_version="s3v4"),
)


# --- Schemas ---
class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str


class DocumentCreate(BaseModel):
    doc_type: str
    s3_key: str
    contact_id: Optional[int] = None
    status: Optional[str] = "draft"


# --- Endpoints ---

@router.get("/")
def get_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Fetch all documents for the authenticated user and attach presigned download URLs."""
    docs = (
        db.query(models.Document)
        .filter(models.Document.user_id == current_user.id)
        .order_by(models.Document.created_at.desc())
        .all()
    )

    result = []
    for doc in docs:
        download_url = None
        if doc.s3_key and S3_BUCKET:
            try:
                download_url = s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": S3_BUCKET, "Key": doc.s3_key},
                    ExpiresIn=3600,
                )
            except Exception:
                download_url = None

        result.append({
            "id": doc.id,
            "doc_type": doc.doc_type,
            "contact_id": doc.contact_id,
            "status": doc.status,
            "s3_key": doc.s3_key,
            "download_url": download_url,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        })

    return result


@router.post("/upload-url")
def generate_upload_url(
    payload: UploadUrlRequest,
    current_user: models.User = Depends(auth.get_current_user),
):
    """Generate a presigned S3 URL so the frontend can upload directly to S3."""
    if not S3_BUCKET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="S3 bucket is not configured on the server",
        )

    file_extension = payload.filename.split(".")[-1] if "." in payload.filename else ""
    key = f"uploads/{current_user.id}/{uuid.uuid4()}-{payload.filename}"

    try:
        presigned_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": key,
                "ContentType": payload.content_type,
            },
            ExpiresIn=900,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate upload URL: {str(e)}",
        )

    return {"upload_url": presigned_url, "key": key}


@router.post("/")
def create_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Save the document record in the database after S3 upload succeeds."""
    doc = models.Document(
        user_id=current_user.id,
        contact_id=payload.contact_id,
        doc_type=payload.doc_type,
        s3_key=payload.s3_key,
        status=payload.status or "draft",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    download_url = None
    if doc.s3_key and S3_BUCKET:
        try:
            download_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": S3_BUCKET, "Key": doc.s3_key},
                ExpiresIn=3600,
            )
        except Exception:
            download_url = None

    return {
        "id": doc.id,
        "doc_type": doc.doc_type,
        "contact_id": doc.contact_id,
        "status": doc.status,
        "s3_key": doc.s3_key,
        "download_url": download_url,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }
