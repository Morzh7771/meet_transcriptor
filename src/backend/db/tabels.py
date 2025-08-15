from sqlalchemy import ForeignKey, Integer, String, DateTime

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime
import uuid
from typing import Optional


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "company"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    email_domen: Mapped[str] = mapped_column(String(100), nullable=False)
    subscription: Mapped[str] = mapped_column(String(50), nullable=False)
    subscription_term: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    registration_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self):
        return f"Company(id={self.id}, title={self.title}, email_domen={self.email_domen}, subscription={self.subscription}, subscription_term={self.subscription_term}, registration_date={self.registration_date})"

