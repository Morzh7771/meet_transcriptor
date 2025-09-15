from sqlalchemy import ForeignKey, Integer, String, DateTime, PrimaryKeyConstraint, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import List
from datetime import datetime
import uuid


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "company"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    email_domen: Mapped[str] = mapped_column(String(100), nullable=True)
    subscription: Mapped[str] = mapped_column(String(50), nullable=False)
    subscription_term: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    registration_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self):
        return f"Company(id={self.id}, title={self.title}, email_domen={self.email_domen})"

class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("company.id"), nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    password: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[str] = mapped_column(String(50), nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)

    def __repr__(self):
        return f"User(id={self.id}, email={self.email}, username={self.username}, company_id={self.company_id})"

# class SoloUser(Base):
#     __tablename__ = "solo_user"

#     id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
#     email: Mapped[str] = mapped_column(String(50), nullable=False)
#     subscription: Mapped[str] = mapped_column(String(50), nullable=False)
#     username: Mapped[str] = mapped_column(String(50), nullable=False)
#     password: Mapped[str] = mapped_column(String(50), nullable=False)
#     role: Mapped[str] = mapped_column(String(100), nullable=False)
#     gender: Mapped[str] = mapped_column(String(50), nullable=False)
#     language: Mapped[str] = mapped_column(String(50), nullable=False)
#     subscription_term: Mapped[datetime] = mapped_column(DateTime, nullable=False)
#     registration_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
#     company_name: Mapped[str] = mapped_column(String(50), nullable=False)

#     __table_args__ = (
#         PrimaryKeyConstraint("id", "email"),
#     )

#     def __repr__(self):
#         return f"CropUser(id={self.id}, email={self.email}, username={self.username}, password={self.password}, role={self.role}, gender={self.gender}, language={self.language}, subscription={self.subscription}, subscription_term={self.subscription_term}, registration_date={self.registration_date}, company_name={self.company_name})"

class Meet(Base):
    __tablename__ = "meet"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id: Mapped[str] = mapped_column(ForeignKey("user.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=True)
    overview: Mapped[str] = mapped_column(Text, nullable=True)
    meet_code: Mapped[str] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    participants: Mapped[List[str]] = mapped_column(JSON, nullable=True)
    action_items: Mapped[str] = mapped_column(Text, nullable=True)
    transcript: Mapped[str] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    tags: Mapped[str] = mapped_column(String(200), nullable=True)

    def __repr__(self):
        return f"Meet(id={self.id}, user_id={self.user_id}, title={self.title}, date={self.date})"

class MeetingMessage(Base):
    __tablename__ = "meeting_message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    meet_id: Mapped[str] = mapped_column(ForeignKey("meet.id"), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self):
        return f"MeetingMessage(id={self.id}, meet_id={self.meet_id}, email={self.email}, time={self.time})"

class MeetingChatMessage(Base):
    __tablename__ = "meeting_chat_message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    meet_id: Mapped[str] = mapped_column(ForeignKey("meet.id"), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self):
        return f"MeetingChatMessage(id={self.id}, meet_id={self.meet_id}, role={self.role}, time={self.time})"
    
    
class FrontMessage(Base):
    __tablename__ = "front_message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    meet_id: Mapped[str] = mapped_column(ForeignKey("meet.id"), nullable=False)
    chat_id: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    def __repr__(self):
        return f"MeetingChatMessage(id={self.id}, meet_id={self.meet_id}, role={self.chat_id}, time={self.time})"

class Participant(Base):
    __tablename__ = "participant"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    meet_id: Mapped[str] = mapped_column(ForeignKey("meet.id"), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self):
        return f"Participant(id={self.id}, meet_id={self.meet_id}, email={self.email}, time={self.time})"
