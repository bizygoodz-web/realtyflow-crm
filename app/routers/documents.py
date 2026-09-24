import React, { useEffect, useState } from "react";
import { FileText, Upload, Download, PenLine, Loader2, X } from "lucide-react";
import { apiFetch } from "../../api";

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";

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

function UploadModal({ isOpen, onClose, onUploaded, contactList }) {
  const [contactId, setContactId] = useState("");
  const [docType, setDocType] = useState("");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stage, setStage] = useState(""); // for a slightly more honest progress message

  if (!isOpen) return null;

  function reset() {
    setContactId(""); setDocType(""); setFile(null); setError(""); setStage("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (!file) throw new Error("Choose a file first.");

      // Step 1: ask our backend for a presigned S3 upload URL
      setStage("Preparing upload...");
      const urlRes = await apiFetch("/documents/upload-url", {
        method: "POST",
        body: JSON.stringify({
          contact_id: contactId,
          doc_type: docType,
          filename: file.name,
          content_type: file.type || "application/octet-stream",
        }),
      });
      if (!urlRes.ok) {
        const body = await urlRes.json().catch(() => ({}));
        throw new Error(body.detail || `Couldn't prepare upload (${urlRes.status})`);
      }
      const { key, upload_url } = await urlRes.json();

      // Step 2: upload the actual file bytes straight to S3, bypassing our
      // backend entirely - this is a plain fetch, not apiFetch, since it's
      // not one of our API calls and doesn't take our auth header.
      setStage("Uploading file...");
      const s3Res = await fetch(upload_url, {
        method: "PUT",
        headers: { "Content-Type": file.type || "application/octet-stream" },
        body: file,
      });
      if (!s3Res.ok) {
        throw new Error(`Upload to storage failed (${s3Res.status}). Check the bucket's CORS policy allows this domain.`);
      }

      // Step 3: confirm the upload so our backend creates the Document record
      setStage("Saving record...");
      const confirmRes = await apiFetch("/documents", {
        method: "POST",
        body: JSON.stringify({ contact_id: contactId, doc_type: docType, key }),
      });
      if (!confirmRes.ok) {
        const body = await confirmRes.json().catch(() => ({}));
        throw new Error(body.detail || `Couldn't save the document record (${confirmRes.status})`);
      }

      reset();
      onUploaded?.();
      onClose();
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
      setStage("");
    }
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(19,42,64,0.45)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }} onClick={onClose}>
      <div style={{ background: "#FFFFFF", borderRadius: 16, width: "100%", maxWidth: 420, padding: "24px 26px 26px" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
          <span style={{ fontFamily: "Fraunces, serif", fontSize: 19, fontWeight: 600, color: INK }}>Upload document</span>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={18} color={MUTED} /></button>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: SLATE, marginBottom: 5 }}>
              Contact{contactList.length === 0 && <span style={{ color: CLAY }}> — create a contact first</span>}
            </label>
            <select
              value={contactId} onChange={(e) => setContactId(e.target.value)} required
              style={{ width: "100%", boxSizing: "border-box", padding: "9px 11px", borderRadius: 8, border: `1px solid ${LINE}`, fontSize: 13, background: "#FFFFFF" }}
            >
              <option value="" disabled>Select a contact...</option>
              {contactList.map(([id, name]) => (
                <option key={id} value={id}>{name}</option>
              ))}
            </select>
          </div>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: SLATE, marginBottom: 5 }}>Document type</label>
            <input
              value={docType} onChange={(e) => setDocType(e.target.value)} required
              placeholder="Disclosure, Agreement, Financing..."
              style={{ width: "100%", boxSizing: "border-box", padding: "9px 11px", borderRadius: 8, border: `1px solid ${LINE}`, fontSize: 13 }}
            />
          </div>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: SLATE, marginBottom: 5 }}>File</label>
            <input
              type="file" required
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              style={{ width: "100%", fontSize: 13 }}
            />
          </div>

          {error && <div style={{ background: "#F5E9E4", color: CLAY, fontSize: 12.5, padding: "10px 12px", borderRadius: 8, marginBottom: 14 }}>{error}</div>}

          <button
            type="submit" disabled={loading || contactList.length === 0}
            style={{
              width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              background: "#14304A", color: "#F6F7F5", border: "none", borderRadius: 10, padding: "12px 0",
              fontSize: 13.5, fontWeight: 500, cursor: loading ? "default" : "pointer",
              opacity: (loading || contactList.length === 0) ? 0.6 : 1,
            }}
          >
            {loading && <Loader2 size={15} className="spin" />}
            {loading ? (stage || "Uploading...") : "Upload"}
          </button>
        </form>
        <style>{`.spin { animation: spin 0.8s linear infinite; } @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  );
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [contactNames, setContactNames] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showUpload, setShowUpload] = useState(false);

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
        contacts.forEach((c) => { lookup[c.id] = `${c.first_name} ${c.last_name}`; });
        setContactNames(lookup);
      }
    } catch (err) {
      setError(err.message || "Couldn't load documents.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const contactList = Object.entries(contactNames);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 14 }}>
        <button
          onClick={() => setShowUpload(true)}
          style={{
            display: "flex", alignItems: "center", gap: 7, background: "#14304A", color: "#F6F7F5",
            border: "none", borderRadius: 8, padding: "9px 16px", fontSize: 13, fontWeight: 500, cursor: "pointer",
          }}
        >
          <Upload size={15} />
          Upload document
        </button>
      </div>

      {loading && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "32px 0", justifyContent: "center", color: MUTED, fontSize: 13 }}>
          <Loader2 size={16} className="spin" />
          Loading documents...
          <style>{`.spin { animation: spin 0.8s linear infinite; } @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {!loading && error && (
        <div style={{ background: "#F5E9E4", color: CLAY, fontSize: 13, padding: "14px 16px", borderRadius: 10, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {!loading && !error && (
        <div style={{ background: "#FFFFFF", border: `1px solid ${LINE}`, borderRadius: 12, overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1.4fr 1fr 1.2fr 90px", padding: "12px 18px", borderBottom: `1px solid ${LINE}`, fontSize: 11.5, fontWeight: 600, color: MUTED, letterSpacing: "0.03em", textTransform: "uppercase" }}>
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
                <div style={{ display: "flex", gap: 8 }}>
                  {d.status === "draft" ? (
                    <button
                      title="Sending for signature isn't wired up yet - needs a DocuSign/HelloSign account"
                      style={{ background: "none", border: "none", cursor: "not-allowed", padding: 4, opacity: 0.5 }}
                    >
                      <PenLine size={15} color={MUTED} />
                    </button>
                  ) : d.download_url ? (
                    <a href={d.download_url} target="_blank" rel="noopener noreferrer" title="Download" style={{ padding: 4, display: "inline-flex" }}>
                      <Download size={15} color={MUTED} />
                    </a>
                  ) : (
                    <span style={{ padding: 4, display: "inline-flex", opacity: 0.4 }}>
                      <Download size={15} color={MUTED} />
                    </span>
                  )}
                </div>
              </div>
            );
          })}
          {documents.length === 0 && (
            <div style={{ padding: "32px 18px", textAlign: "center", fontSize: 13, color: MUTED, fontStyle: "italic" }}>
              No documents yet.
            </div>
          )}
        </div>
      )}

      <UploadModal
        isOpen={showUpload}
        onClose={() => setShowUpload(false)}
        onUploaded={load}
        contactList={contactList}
      />
    </div>
  );
}
