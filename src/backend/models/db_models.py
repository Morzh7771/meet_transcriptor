from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
import uuid


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
