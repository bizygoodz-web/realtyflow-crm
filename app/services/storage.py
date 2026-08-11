"""
Document storage via S3-compatible object storage (works with AWS S3,
Cloudflare R2, or Backblaze B2 — anything that speaks the S3 API).

Flow:
  1. Client asks for a presigned PUT url (`get_upload_url`).
  2. Client uploads the file bytes directly to S3 using that url — the file
     never passes through our API server.
  3. Client confirms the upload by calling the documents endpoint with the
     `key` it was given, which creates the Document row.
  4. Whenever the file needs to be read back, `get_download_url` mints a
     short-lived presigned GET url — we never store or serve a public URL.
"""
import os
import uuid
import logging

import boto3
from botocore.client import Config

logger = logging.getLogger("realtyflow.storage")

BUCKET = os.getenv("DOCS_BUCKET", "realtyflow-documents")
REGION = os.getenv("AWS_REGION", "us-east-1")
# For R2/B2/MinIO, set S3_ENDPOINT_URL; leave unset for real AWS S3.
ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")

UPLOAD_URL_TTL_SECONDS = 300      # 5 minutes to complete the upload
DOWNLOAD_URL_TTL_SECONDS = 900    # 15 minutes to view/download

_client = None


def _s3():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            region_name=REGION,
            endpoint_url=ENDPOINT_URL,
            config=Config(signature_version="s3v4"),
        )
    return _client


def build_key(agent_id: str, contact_id: str, filename: str) -> str:
    """Namespaced key so one agent's documents can never collide with or be
    guessed from another's — this key layout is also what makes it cheap to
    later restrict an IAM policy to a prefix per agent if you need to."""
    safe_name = filename.replace("/", "_")
    return f"agents/{agent_id}/contacts/{contact_id}/{uuid.uuid4().hex}_{safe_name}"


def get_upload_url(key: str, content_type: str) -> str:
    return _s3().generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=UPLOAD_URL_TTL_SECONDS,
    )


def get_download_url(key: str) -> str:
    return _s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=DOWNLOAD_URL_TTL_SECONDS,
    )


def delete_object(key: str) -> None:
    try:
        _s3().delete_object(Bucket=BUCKET, Key=key)
    except Exception:
        logger.exception("Failed to delete S3 object %s", key)
