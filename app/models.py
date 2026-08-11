import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, Integer, Numeric, ForeignKey, DateTime,
    Enum, Text, ARRAY, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


class ContactType(str, enum.Enum):
    buyer = "buyer"
    seller = "seller"
    both = "both"


class ContactStatus(str, enum.Enum):
    new_lead = "new_lead"
    active = "active"
    showing = "showing"
    under_contract = "under_contract"
    past_client = "past_client"


class DealStage(str, enum.Enum):
    lead = "lead"
    nurture = "nurture"
    showing = "showing"
    offer = "offer"
    under_contract = "under_contract"
    closed = "closed"
    lost = "lost"


class DealType(str, enum.Enum):
    buy = "buy"
    sell = "sell"


class PropertyStatus(str, enum.Enum):
    active = "active"
    pending = "pending"
    closed = "closed"
    withdrawn = "withdrawn"


class DocStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    signed = "signed"


class ActivityType(str, enum.Enum):
    note = "note"
    call = "call"
    showing = "showing"
    doc_sent = "doc_sent"
    email = "email"
    sms = "sms"
    reminder = "reminder"


class Agent(Base):
    __tablename__ = "agents"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String)
    brokerage = Column(String)
    license_no = Column(String)
    role = Column(String, default="agent")  # agent | admin
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    contacts = relationship("Contact", back_populates="agent")


class Contact(Base):
    __tablename__ = "contacts"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    agent_id = Column(UUID(as_uuid=False), ForeignKey("agents.id"), nullable=False, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, index=True)
    phone = Column(String)
    contact_type = Column(Enum(ContactType), nullable=False)
    lead_source = Column(String)
    status = Column(Enum(ContactStatus), default=ContactStatus.new_lead)
    portal_password_hash = Column(String)  # client-portal login
    created_at = Column(DateTime, default=datetime.utcnow)
    last_contacted_at = Column(DateTime)

    agent = relationship("Agent", back_populates="contacts")
    buyer_profile = relationship("BuyerProfile", uselist=False, back_populates="contact")
    seller_profile = relationship("SellerProfile", uselist=False, back_populates="contact")
    deals = relationship("Deal", back_populates="contact")
    activities = relationship("Activity", back_populates="contact")


class BuyerProfile(Base):
    __tablename__ = "buyer_profiles"
    contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"), primary_key=True)
    budget_min = Column(Numeric)
    budget_max = Column(Numeric)
    preferred_locations = Column(ARRAY(String))
    preferred_beds = Column(Integer)
    preferred_baths = Column(Integer)
    preapproval_status = Column(String)
    preapproval_amount = Column(Numeric)
    lender_name = Column(String)

    contact = relationship("Contact", back_populates="buyer_profile")


class SellerProfile(Base):
    __tablename__ = "seller_profiles"
    contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"), primary_key=True)
    property_address = Column(String)
    listing_timeline = Column(String)
    expected_price = Column(Numeric)
    mortgage_payoff = Column(Numeric)
    reason_for_selling = Column(Text)

    contact = relationship("Contact", back_populates="seller_profile")


class Property(Base):
    __tablename__ = "properties"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    agent_id = Column(UUID(as_uuid=False), ForeignKey("agents.id"), nullable=False)
    seller_contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"), nullable=True)
    address = Column(String, nullable=False)
    mls_number = Column(String)
    list_price = Column(Numeric)
    status = Column(Enum(PropertyStatus), default=PropertyStatus.active)
    days_on_market = Column(Integer, default=0)
    beds = Column(Integer)
    baths = Column(Integer)
    sqft = Column(Integer)
    photos = Column(ARRAY(String))

    showings = relationship("Showing", back_populates="property")
    saved_by = relationship("SavedListing", back_populates="property")


class Deal(Base):
    __tablename__ = "deals"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=False), ForeignKey("agents.id"), nullable=False)
    property_id = Column(UUID(as_uuid=False), ForeignKey("properties.id"), nullable=True)
    deal_type = Column(Enum(DealType), nullable=False)
    stage = Column(Enum(DealStage), default=DealStage.lead)
    list_price = Column(Numeric)
    offer_price = Column(Numeric)
    close_date = Column(DateTime)
    commission_pct = Column(Numeric)
    created_at = Column(DateTime, default=datetime.utcnow)

    contact = relationship("Contact", back_populates="deals")
    offers = relationship("Offer", back_populates="deal")
    documents = relationship("Document", back_populates="deal")


class SavedListing(Base):
    __tablename__ = "saved_listings"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    buyer_contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"), nullable=False, index=True)
    property_id = Column(UUID(as_uuid=False), ForeignKey("properties.id"), nullable=False)
    agent_curated = Column(Boolean, default=True)
    buyer_feedback = Column(Text)
    feedback_rating = Column(Integer)
    status = Column(String, default="new")  # new | viewed | interested | passed

    property = relationship("Property", back_populates="saved_by")


class Showing(Base):
    __tablename__ = "showings"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    property_id = Column(UUID(as_uuid=False), ForeignKey("properties.id"), nullable=False)
    buyer_contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"), nullable=True)
    agent_id = Column(UUID(as_uuid=False), ForeignKey("agents.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    type = Column(String, default="private")  # private | open_house
    feedback_text = Column(Text)
    feedback_rating = Column(Integer)

    property = relationship("Property", back_populates="showings")


class Offer(Base):
    __tablename__ = "offers"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    deal_id = Column(UUID(as_uuid=False), ForeignKey("deals.id"), nullable=False, index=True)
    offer_amount = Column(Numeric, nullable=False)
    buyer_contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"))
    status = Column(String, default="submitted")  # submitted|countered|accepted|rejected
    submitted_at = Column(DateTime, default=datetime.utcnow)
    contingencies = Column(Text)

    deal = relationship("Deal", back_populates="offers")


class Document(Base):
    __tablename__ = "documents"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    deal_id = Column(UUID(as_uuid=False), ForeignKey("deals.id"), nullable=True, index=True)
    contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"), nullable=False, index=True)
    uploaded_by = Column(UUID(as_uuid=False), ForeignKey("agents.id"))
    doc_type = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    status = Column(Enum(DocStatus), default=DocStatus.draft)
    esign_provider_ref = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    deal = relationship("Deal", back_populates="documents")


class Activity(Base):
    __tablename__ = "activities"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"), nullable=False, index=True)
    deal_id = Column(UUID(as_uuid=False), ForeignKey("deals.id"), nullable=True)
    agent_id = Column(UUID(as_uuid=False), ForeignKey("agents.id"), nullable=False)
    type = Column(Enum(ActivityType), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    is_automated = Column(Boolean, default=False)

    contact = relationship("Contact", back_populates="activities")


class Workflow(Base):
    __tablename__ = "workflows"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    agent_id = Column(UUID(as_uuid=False), ForeignKey("agents.id"), nullable=False)
    name = Column(String, nullable=False)
    trigger_event = Column(String, nullable=False)  # new_lead|post_showing|anniversary
    steps = Column(JSON, nullable=False)  # [{delay_days, channel, template_id}]
    is_active = Column(Boolean, default=True)


class WorkflowEnrollment(Base):
    __tablename__ = "workflow_enrollments"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"), nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=False), ForeignKey("workflows.id"), nullable=False)
    current_step = Column(Integer, default=0)
    status = Column(String, default="active")  # active|completed|paused
    enrolled_at = Column(DateTime, default=datetime.utcnow)


class CMAReport(Base):
    __tablename__ = "cma_reports"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    deal_id = Column(UUID(as_uuid=False), ForeignKey("deals.id"), nullable=True)
    subject_property = Column(JSON, nullable=False)
    comparables = Column(JSON, nullable=False)
    suggested_price = Column(Numeric)
    generated_at = Column(DateTime, default=datetime.utcnow)
    shared_with_contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"), nullable=True)
