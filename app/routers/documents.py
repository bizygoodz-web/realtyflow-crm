import React, { useEffect, useRef, useState } from "react";
import { FileText, Upload, Download, PenLine, Loader2 } from "lucide-react";
import { apiFetch } from "../../api";

const INK = "#132A40";
const SLATE = "#56606B";
const MUTED = "#8B94A0";
const LINE = "#E1E4E2";
const CLAY = "#A5522F";

const STATUS_STYLE = {
  signed: { bg: "#E9EEE7", fg: "#4F6A4A", label: "Signed" },
  sent: { bg: "#EFE7D4", fg: "#8C6A34", label: "Awaiting signature" },
  draft: { bg: "#F5E9E4", fg: "#A5522F", label: "Draft" },
};

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [contactNames, setContactNames] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Upload state
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [uploadContactId, setUploadContactId] = useState("");
  const [uploadError, setUploadError] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const [docsRes, contactsRes] = await Promise.all([
          apiFetch("/documents"),
          apiFetch("/contacts"),
        ]);
        if (!docsRes.ok) {
          const body = await docsRes.json().catch(() => ({}));
          throw new Error(body.detail || `Couldn't load documents (${docsRes.status})`);
        }
        setDocuments(await docsRes.json());

        if (contactsRes.ok) {
          const contacts = await contactsRes.json();
          const lookup = {};
          contacts.forEach((c) => {
            lookup[c.id] = `${c.first_name} ${c.last_name}`;
          });
          setContactNames(lookup);
        }
      } catch (err) {
        setError(err.message || "Couldn't load documents.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleFileChosen(e) {
    const file = e.target.files?.[0];
    e.target.value = ""; // lets the same file be picked again later
    if (!file) return;

    setUploading(true);
    setUploadError("");
    const contentType = file.type || "application/octet-stream";

    try {
      // 1. Ask the backend for a presigned S3 upload URL
      const urlRes = await apiFetch("/documents/upload-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, content_type: contentType }),
      });
      if (!urlRes.ok) {
        const body = await urlRes.json().catch(() => ({}));
        throw new Error(body.detail || `Couldn't start upload (${urlRes.status})`);
      }
      const { upload_url, key } = await urlRes.json();

      // 2. Send the file straight to S3 (plain fetch: no auth header to S3)
      const putRes = await fetch(upload_url, {
        method: "PUT",
        headers: { "Content-Type": contentType },
        body: file,
      });
      if (!putRes.ok) throw new Error(`Upload to storage failed (${putRes.status})`);

      // 3. Save the document record
      const createRes = await apiFetch("/documents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doc_type: file.name.replace(/\.[^.]+$/, ""),
          contact_id: uploadContactId ? Number(uploadContactId) || uploadContactId : null,
          s3_key: key,
          status: "draft",
        }),
      });
      if (!createRes.ok) {
        const body = await createRes.json().catch(() => ({}));
        throw new Error(body.detail || `Couldn't save document (${createRes.status})`);
      }
      const created = await createRes.json();
      setDocuments((prev) => [created, ...prev]);
    } catch (err) {
      setUploadError(err.message || "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <style>{`.spin { animation: spin 0.8s linear infinite; } @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>

      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <select
          value={uploadContactId}
          onChange={(e) => setUploadContactId(e.target.value)}
          disabled={uploading}
          aria-label="Contact for uploaded document"
          style={{ border: `1px solid ${LINE}`, borderRadius: 8, padding: "8px 10px", fontSize: 13, color: SLATE, background: "#fff" }}
        >
          <option value="">No contact</option>
          {Object.entries(contactNames).map(([id, name]) => (
            <option key={id} value={id}>{name}</option>
          ))}
        </select>

        <input ref={fileInputRef} type="file" hidden onChange={handleFileChosen} />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          style={{
            display: "flex", alignItems: "center", gap: 7, background: "#14304A", color: "#F6F7F5",
            border: "none", borderRadius: 8, padding: "9px 16px", fontSize: 13, fontWeight: 500,
            cursor: uploading ? "wait" : "pointer", opacity: uploading ? 0.6 : 1,
          }}
        >
          {uploading ? <Loader2 size={15} className="spin" /> : <Upload size={15} />}
          {uploading ? "Uploading..." : "Upload document"}
        </button>
      </div>

      {uploadError && (
        <div style={{ background: "#F5E9E4", color: CLAY, fontSize: 13, padding: "12px 16px", borderRadius: 10, marginBottom: 14 }}>
          {uploadError}
        </div>
      )}

      {loading && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "32px 0", justifyContent: "center", color: MUTED, fontSize: 13 }}>
          <Loader2 size={16} className="spin" />
          Loading documents...
        </div>
      )}

      {!loading && error && (
        <div style={{ background: "#F5E9E4", color: CLAY, fontSize: 13, padding: "14px 16px", borderRadius: 10, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {!loading && !error && (
        <div style={{ background: "#FFFFFF", border: `1px solid ${LINE}`, borderRadius: 12, overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1.4fr 1fr 1.2fr 90px", padding: "12px 18px", borderBottom: `1px solid ${LINE}`, fontSize: 11.5, fontWeight: 600, color: MUTED, letterSpacing: "-0.3px" }}>
            <span>Document</span>
            <span>Contact</span>
            <span>Status</span>
            <span>Date</span>
            <span />
          </div>
          {documents.map((d) => {
            const style = STATUS_STYLE[d.status] || STATUS_STYLE.draft;
            return (
              <div
                key={d.id}
                style={{ display: "grid", gridTemplateColumns: "2fr 1.4fr 1fr 1.2fr 90px", alignItems: "center", padding: "14px 18px", borderBottom: `1px solid ${LINE}` }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 32, height: 32, borderRadius: 8, background: "#F6F7F5", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <FileText size={15} color={INK} />
                  </div>
                  <span style={{ fontSize: 13.5, fontWeight: 500, color: INK }}>{d.doc_type}</span>
                </div>
                <span style={{ fontSize: 12.5, color: SLATE }}>{contactNames[d.contact_id] || "—"}</span>
                <span style={{ fontSize: 11, fontWeight: 600, color: style.fg, background: style.bg, borderRadius: 20, padding: "4px 10px", width: "fit-content" }}>
                  {style.label}
                </span>
                <span style={{ fontSize: 12, color: MUTED }}>{formatDate(d.created_at)}</span>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {d.download_url && (
                    <a href={d.download_url} target="_blank" rel="noopener noreferrer" title="Download" style={{ padding: 4, display: "inline-flex" }}>
                      <Download size={15} color={MUTED} />
                    </a>
                  )}
                  {d.status === "draft" && (
                    <button
                      title="Sending for signature isn't wired up yet"
                      style={{ background: "none", border: "none", cursor: "not-allowed", padding: 4, opacity: 0.5 }}
                    >
                      <PenLine size={15} color={MUTED} />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          {documents.length === 0 && (
            <div style={{ padding: "32px 18px", textAlign: "center", fontSize: 13, color: MUTED, fontStyle: "italic" }}>
              No documents yet. Choose a contact and upload your first document.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
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
