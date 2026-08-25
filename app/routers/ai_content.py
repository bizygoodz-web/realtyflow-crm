import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from openai import OpenAI, OpenAIError

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/ai", tags=["ai"])

# xAI (Grok) exposes an OpenAI-compatible API - same SDK, just a different
# base_url and api_key. Get a key from https://console.x.ai (billing may be
# required depending on current terms - check when you sign up).
XAI_API_KEY = os.getenv("XAI_API_KEY")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4")

client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1") if XAI_API_KEY else None

PROMPTS = {
    "follow_up_email": "Write a short, warm follow-up email from a real estate agent to a client. Client context: {context}. No subject line needed, just the body.",
    "follow_up_sms": "Write a brief, friendly SMS follow-up (under 300 characters) from a real estate agent to a client. Context: {context}.",
    "listing_description": "Write a compelling MLS listing description for this property: {context}. Keep it under 150 words, no cliches like 'must see'.",
    "social_post": "Write a short social media announcement (Instagram-style caption) for this listing or update: {context}.",
}


@router.post("/generate", response_model=schemas.AIContentResponse)
def generate_content(
    payload: schemas.AIContentRequest,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="AI content generation isn't configured yet - XAI_API_KEY is missing on the server.",
        )

    template = PROMPTS.get(payload.content_type)
    if not template:
        raise HTTPException(status_code=400, detail="Unsupported content_type")

    context = payload.context or ""
    if payload.contact_id:
        contact = (
            db.query(models.Contact)
            .filter(models.Contact.id == payload.contact_id, models.Contact.agent_id == current.agent_id)
            .first()
        )
        if contact:
            context = f"{contact.first_name} {contact.last_name}, {contact.contact_type}. {context}"

    prompt = template.format(context=context)

    try:
        completion = client.chat.completions.create(
            model=XAI_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
    except OpenAIError as e:
        # Surface a clean error response instead of letting an unhandled
        # exception skip past the CORS middleware - an unhandled crash here
        # shows up in the browser as a misleading "Failed to fetch" / CORS
        # error rather than the actual problem.
        raise HTTPException(status_code=502, detail=f"xAI API error: {str(e)}")

    draft = completion.choices[0].message.content
    return schemas.AIContentResponse(draft=draft)
