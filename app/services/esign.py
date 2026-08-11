"""
E-signature integration point. This is stubbed the same way mailer.py is —
it simulates the provider's API shape so the rest of the app (status
tracking, webhooks, the document hub UI) can be built and tested against a
realistic contract, without needing a live DocuSign/HelloSign account yet.

To go live: swap `_create_envelope_stub` for a real DocuSign eSignature API
call (create envelope from a template + recipient), and point your
provider's webhook at POST /documents/esign-webhook with a shared secret.
"""
import os
import uuid
import hmac
import logging

logger = logging.getLogger("realtyflow.esign")

WEBHOOK_SECRET = os.getenv("ESIGN_WEBHOOK_SECRET", "change-me")

# Provider status strings vary (DocuSign uses "completed", HelloSign uses
# "signed", etc.) - normalize whatever comes in on the webhook to our own
# DocStatus values here, in one place.
STATUS_MAP = {
    "sent": "sent",
    "delivered": "sent",
    "completed": "signed",
    "signed": "signed",
    "declined": "sent",  # stays "sent" (needs re-send), not a terminal failure state in our schema
}


def create_envelope(document_id: str, signer_email: str, signer_name: str) -> dict:
    """Kick off a signature request for a document. Returns provider refs to store."""
    envelope_id = f"stub-{uuid.uuid4().hex[:12]}"
    logger.info(
        "ESIGN create_envelope doc=%s envelope=%s signer=%s <%s>",
        document_id, envelope_id, signer_name, signer_email,
    )
    # Real DocuSign call would look roughly like:
    #   envelope = docusign_client.envelopes.create_envelope(account_id, envelope_definition)
    #   return {"envelope_id": envelope.envelope_id, "signing_url": <embedded signing url>}
    return {
        "envelope_id": envelope_id,
        "signing_url": f"https://example-esign-provider.test/sign/{envelope_id}",
    }


def verify_webhook_signature(raw_body: bytes, provided_signature: str) -> bool:
    """Constant-time comparison so this can't be timing-attacked. Real
    providers each have their own signing scheme (DocuSign uses HMAC-SHA256
    over the payload with your Connect secret) - wire that in here."""
    import hashlib
    expected = hashlib.sha256(WEBHOOK_SECRET.encode() + raw_body).hexdigest()
    return hmac.compare_digest(expected, provided_signature or "")


def normalize_status(provider_status: str) -> str:
    return STATUS_MAP.get(provider_status.lower(), "sent")
