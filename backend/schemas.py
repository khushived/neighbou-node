from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class UserProfile(BaseModel):
    display_name: str
    photo_url: Optional[str] = None
    bio: Optional[str] = None
    lat: float
    lng: float
    radius_km_default: float = 3.0


class ListingBase(BaseModel):
    title: str
    description: str
    # pydantic v2: use pattern instead of regex
    type: str = Field(pattern="^(offer|request|skill)$")
    is_free: bool = True
    is_trade: bool = False
    category: Optional[str] = None
    lat: float
    lng: float


class ListingCreate(ListingBase):
    pass


class Listing(ListingBase):
    id: str
    owner_uid: str
    created_at: datetime
    status: str = "active"


class UrgentNeedBase(BaseModel):
    title: str
    description: str
    lat: float
    lng: float
    radius_km: float = 2.0


class UrgentNeedCreate(UrgentNeedBase):
    pass


class UrgentNeed(UrgentNeedBase):
    id: str
    user_uid: str
    created_at: datetime
    status: str = "active"


class MessageCreate(BaseModel):
    conversation_id: Optional[str] = None
    urgent_need_id: Optional[str] = None
    content: str


class Message(BaseModel):
    id: str
    conversation_id: str
    sender_uid: str
    content: str
    created_at: datetime


class Conversation(BaseModel):
    id: str
    participant_uids: List[str]
    listing_id: Optional[str] = None
    urgent_need_id: Optional[str] = None


class ReactionCreate(BaseModel):
    reaction_type: str = Field(pattern="^(like|helpful|available|unavailable)$")


class Reaction(BaseModel):
    id: str
    user_uid: str
    reaction_type: str
    created_at: datetime


class ListingUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(active|reserved|completed|expired)$")
    description: Optional[str] = None


class ChatbotQuery(BaseModel):
    query: str
    lat: Optional[float] = None
    lng: Optional[float] = None


class ChatbotResponse(BaseModel):
    response: str
    suggestions: List[dict] = []
    external_links: List[dict] = []


class RespondWithListingRequest(BaseModel):
    listing_id: str

