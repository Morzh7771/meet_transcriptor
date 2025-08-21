from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class CompanyCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="Company name")
    email_domen: str = Field(..., min_length=1, max_length=100, description="Company email domain")
    subscription: str = Field(..., min_length=1, max_length=50, description="Subscription type")
    subscription_term: datetime = Field(..., description="Subscription expiration date")
    registration_date: datetime = Field(..., description="Company registration date")


class CompanyUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="Company name")
    email_domen: Optional[str] = Field(None, min_length=1, max_length=100, description="Company email domain")
    subscription: Optional[str] = Field(None, min_length=1, max_length=50, description="Subscription type")
    subscription_term: Optional[datetime] = Field(None, description="Subscription expiration date")


class CompanyResponse(BaseModel):
    id: str
    title: str
    email_domen: str
    subscription: str
    subscription_term: datetime
    registration_date: datetime

    model_config = ConfigDict(
        from_attributes=True
    )

class UserCreate(BaseModel):
    email: str = Field(..., min_length=1, max_length=100, description="User email address")
    company_id: str = Field(..., min_length=1, max_length=36, description="User email address")
    username: str
    password: str
    role: str
    gender: str
    language: str

class UserUpdate(BaseModel):
    email: Optional[str]
    username: Optional[str]
    password: Optional[str]
    role: Optional[str]
    gender: Optional[str]
    language: Optional[str]

class UserResponse(BaseModel):
    id: str
    email: str
    company_id: str
    username: str
    role: str
    gender: str
    language: str

    model_config = ConfigDict(from_attributes=True)

class MeetCreate(BaseModel):
    user_id: str
    title: str
    summary: Optional[str] = "No summary provided"
    date: datetime
    duration: Optional[int] = 0
    overview: Optional[str] = "No overview provided"
    notes: Optional[str] = "No notes provided"
    action_items: Optional[str] = "No action items provided"
    transcript: Optional[str] = "No transcript provided"
    language: str
    tags: Optional[str] = "No tags provided"

class MeetUpdate(BaseModel):
    user_id: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    date: Optional[datetime] = None
    duration: Optional[int] = None
    overview: Optional[str] = None
    notes: Optional[str] = None
    action_items: Optional[str] = None
    transcript: Optional[str] = None
    language: Optional[str] = None
    tags: Optional[str] = None

class MeetResponse(BaseModel):
    id: str
    user_id: str
    title: str
    summary: str
    date: datetime
    duration: int
    overview: str
    notes: str
    action_items: str
    transcript: str
    language: str
    tags: str

    model_config = ConfigDict(from_attributes=True)

class MeetingMessageCreate(BaseModel):
    meet_id: str
    time: datetime
    email: str
    content: str

class MeetingMessageUpdate(BaseModel):
    meet_id: Optional[str] = None
    time: Optional[datetime] = None
    email: Optional[str] = None
    content: Optional[str] = None

class MeetingMessageResponse(BaseModel):
    id: str
    meet_id: str
    time: datetime
    email: str
    content: str

    model_config = ConfigDict(from_attributes=True)

class MeetingChatMessageCreate(BaseModel):
    meet_id: str
    time: datetime
    role: str
    content: str

class MeetingChatMessageUpdate(BaseModel):
    meet_id: Optional[str] = None
    time: Optional[datetime] = None
    role: Optional[str] = None
    content: Optional[str] = None

class MeetingChatMessageResponse(BaseModel):
    id: str
    meet_id: str
    time: datetime
    role: str
    content: str

    model_config = ConfigDict(from_attributes=True)

class ParticipantCreate(BaseModel):
    meet_id: str
    time: datetime
    email: str

class ParticipantUpdate(BaseModel):
    meet_id: Optional[str] = None
    time: Optional[datetime] = None
    email: Optional[str] = None

class ParticipantResponse(BaseModel):
    id: str
    meet_id: str
    time: datetime
    email: str

    model_config = ConfigDict(from_attributes=True)
