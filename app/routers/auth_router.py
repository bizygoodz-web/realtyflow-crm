from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/agent/signup", response_model=schemas.Token, status_code=201)
def agent_signup(payload: schemas.AgentSignup, db: Session = Depends(get_db)):
    existing = db.query(models.Agent).filter(models.Agent.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    agent = models.Agent(
        name=payload.name,
        email=payload.email,
        brokerage=payload.brokerage,
        hashed_password=auth.hash_password(payload.password),
        role="agent",
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    token = auth.create_access_token({"sub": agent.id, "role": agent.role, "agent_id": agent.id})
    return schemas.Token(access_token=token, role=agent.role)


@router.post("/agent/login", response_model=schemas.Token)
def agent_login(payload: schemas.AgentLogin, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.email == payload.email).first()
    if not agent or not auth.verify_password(payload.password, agent.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = auth.create_access_token({"sub": agent.id, "role": agent.role, "agent_id": agent.id})
    return schemas.Token(access_token=token, role=agent.role)


@router.post("/client/login", response_model=schemas.Token)
def client_login(payload: schemas.ClientLogin, db: Session = Depends(get_db)):
    contact = db.query(models.Contact).filter(models.Contact.email == payload.email).first()
    if not contact or not contact.portal_password_hash or not auth.verify_password(
        payload.password, contact.portal_password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = auth.create_access_token(
        {"sub": contact.id, "role": "client", "agent_id": contact.agent_id}
    )
    return schemas.Token(access_token=token, role="client")


@router.post("/client/set-password")
def set_client_password(
    payload: schemas.ClientSetPassword,
    db: Session = Depends(get_db),
    current: auth.TokenData = Depends(auth.require_agent),
):
    """Agent-triggered: sets/resets a client's portal password after inviting
    them. There is no client self-service signup - clients are always
    created by their agent first (via POST /contacts), then given portal
    access. A real invite flow would email a one-time setup link instead of
    letting the agent choose the password directly; this is the minimal
    version to unblock testing the portal end-to-end."""
    contact = (
        db.query(models.Contact)
        .filter(models.Contact.id == payload.contact_id, models.Contact.agent_id == current.agent_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.portal_password_hash = auth.hash_password(payload.password)
    db.commit()
    return {"updated": True}
