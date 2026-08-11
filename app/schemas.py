from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class AgentLogin(BaseModel):
    email: EmailStr
    password: str


class AgentSignup(BaseModel):
    name: str
    email: EmailStr
    password: str
    brokerage: Optional[str] = None


class ClientLogin(BaseModel):
    email: EmailStr
    password: str


class ClientSetPassword(BaseModel):
    contact_id: str
    password: str


# ---- Contacts ----

class BuyerProfileIn(BaseModel):
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    preferred_locations: Optional[List[str]] = None
    preferred_beds: Optional[int] = None
    preferred_baths: Optional[int] = None
    preapproval_status: Optional[str] = None
    preapproval_amount: Optional[float] = None
    lender_name: Optional[str] = None


class SellerProfileIn(BaseModel):
    property_address: Optional[str] = None
    listing_timeline: Optional[str] = None
    expected_price: Optional[float] = None
    mortgage_payoff: Optional[float] = None
    reason_for_selling: Optional[str] = None


class ContactCreate(BaseModel):
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    contact_type: str  # buyer | seller | both
    lead_source: Optional[str] = None
    buyer_profile: Optional[BuyerProfileIn] = None
    seller_profile: Optional[SellerProfileIn] = None


class ContactOut(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    contact_type: str
    status: str
    created_at: datetime
    last_contacted_at: Optional[datetime]

    class Config:
        from_attributes = True


# ---- Deals ----

class DealCreate(BaseModel):
    contact_id: str
    deal_type: str  # buy | sell
    property_id: Optional[str] = None
    list_price: Optional[float] = None


class DealStageUpdate(BaseModel):
    stage: str


class DealOut(BaseModel):
    id: str
    contact_id: str
    deal_type: str
    stage: str
    list_price: Optional[float]
    offer_price: Optional[float]
    close_date: Optional[datetime]

    class Config:
        from_attributes = True


# ---- Activities (the ledger) ----

class ActivityCreate(BaseModel):
    contact_id: str
    deal_id: Optional[str] = None
    type: str  # note|call|showing|doc_sent|email|sms|reminder
    content: Optional[str] = None


class ActivityOut(BaseModel):
    id: str
    contact_id: str
    type: str
    content: Optional[str]
    created_at: datetime
    is_automated: bool

    class Config:
        from_attributes = True


# ---- Documents ----

class DocumentUploadURLRequest(BaseModel):
    contact_id: str
    deal_id: Optional[str] = None
    doc_type: str
    filename: str
    content_type: str = "application/pdf"


class DocumentUploadURLResponse(BaseModel):
    key: str
    upload_url: str


class DocumentConfirm(BaseModel):
    contact_id: str
    deal_id: Optional[str] = None
    doc_type: str
    key: str  # the storage key returned by /documents/upload-url


class DocumentStatusUpdate(BaseModel):
    status: str  # draft|sent|signed


class DocumentOut(BaseModel):
    id: str
    contact_id: str
    doc_type: str
    status: str
    download_url: Optional[str] = None
    esign_provider_ref: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Workflows ----

class WorkflowStep(BaseModel):
    delay_days: int
    channel: str  # email|sms
    template_id: str


class WorkflowCreate(BaseModel):
    name: str
    trigger_event: str
    steps: List[WorkflowStep]


class WorkflowEnroll(BaseModel):
    contact_id: str
    workflow_id: str


# ---- CMA ----

class CMAGenerate(BaseModel):
    subject_property: dict  # {address, beds, baths, sqft, ...}
    comparables: List[dict]  # [{address, sale_price, sqft, sold_date}, ...]
    deal_id: Optional[str] = None


class CMAOut(BaseModel):
    id: str
    suggested_price: Optional[float]
    generated_at: datetime

    class Config:
        from_attributes = True


# ---- E-signature ----

class ESignSendRequest(BaseModel):
    signer_email: EmailStr
    signer_name: str


class ESignSendResponse(BaseModel):
    envelope_id: str
    signing_url: str


# ---- AI content ----

class AIContentRequest(BaseModel):
    contact_id: Optional[str] = None
    content_type: str  # follow_up_email | follow_up_sms | listing_description | social_post
    context: Optional[str] = None  # free-text hints, e.g. "just showed the property, no response yet"


class AIContentResponse(BaseModel):
    draft: str
