import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import anthropic

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/ai", tags=["ai"])

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    draft = "".join(block.text for block in message.content if block.type == "text")
    return schemas.AIContentResponse(draft=draft)
