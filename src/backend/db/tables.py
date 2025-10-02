from sqlalchemy import DateTime, String, DateTime, ForeignKey, DECIMAL, Integer, Text, JSON
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
import uuid
from datetime import datetime
from typing import List

class Base(DeclarativeBase):
    pass

class Plan(Base):
    __tablename__ = 'plan'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    client_id: Mapped[str] = mapped_column(ForeignKey("client.id"), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    plan_code: Mapped[str] = mapped_column(String(50), nullable=False)
    plan_name: Mapped[str] = mapped_column(String(50), nullable=False)
    employer_tax_id: Mapped[str] = mapped_column(String(50), nullable=False)
    roth_first_year: Mapped[float] = mapped_column(DECIMAL(10,2), nullable=False)

class PersonAddress(Base):
    __tablename__ = 'person_address'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), nullable=False)
    address_type: Mapped[str] = mapped_column(String(50), nullable=False)
    street: Mapped[str] = mapped_column(String(50), nullable=False)
    city: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    country: Mapped[str] = mapped_column(String(50), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(50), nullable=False)
    
    #persons = relationship("Person", back_populates="address")

class Person(Base):
    __tablename__ = 'person'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    client_id: Mapped[str] = mapped_column(ForeignKey("client.id"), nullable=False)
    beneficiary_id: Mapped[str] = mapped_column(ForeignKey("beneficiary.id"), nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    middle_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    date_of_birth: Mapped[datetime] = mapped_column(DateTime)
    sex: Mapped[str] = mapped_column(String(50), nullable=False)
    ssn_or_tin: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(50), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    phone_alt: Mapped[str] = mapped_column(String(50), nullable=False)

    #address = relationship("PersonAddress", back_populates="persons")
    #beneficiaries = relationship("Beneficiaries", back_populates="person")

class Beneficiary(Base):
    __tablename__ = 'beneficiary'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    client_id: Mapped[str] = mapped_column(ForeignKey("client.id"), nullable=False)
    beneficiary_type: Mapped[str] = mapped_column(String(50), nullable=False)
    relation: Mapped[str] = mapped_column(String(50), nullable=False)
    share_percentage: Mapped[float] = mapped_column(DECIMAL, nullable=False)

    #person = relationship("Person", back_populates="beneficiaries")

# class Agreements(Base):
#     __tablename__ = 'agreements'

#     id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

#     plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), nullable=False)
#     data_privacy_consent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
#     erisa_disclosures_ack_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
#     plan_document_read_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
#     e_delivery_consent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
#     arbitration_accepted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
#     participant_signed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
#     participant_signature_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
#     participant_signature_ref: Mapped[str] = mapped_column(String(50), nullable=False)
#     admin_signed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
#     admin_signature_pdf: Mapped[str] = mapped_column(String(50), nullable=False)
#     admin_name: Mapped[str] = mapped_column(String(50), nullable=False)
#     admin_email: Mapped[str] = mapped_column(String(50), nullable=False)
#     admin_phone: Mapped[str] = mapped_column(String(50), nullable=False)

    #clients = relationship("Client", back_populates="agreements")

class ClientEmployment(Base):
    __tablename__ = 'client_employment'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    client_id: Mapped[str] = mapped_column(ForeignKey("client.id"), nullable=False)
    company_name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_title: Mapped[str] = mapped_column(String(100), nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    hire_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    pay_frequency: Mapped[str] = mapped_column(String(50), nullable=False)
    year_funds: Mapped[float] = mapped_column(DECIMAL, nullable=False)
    add_funds: Mapped[float] = mapped_column(DECIMAL, nullable=False)

    #clients = relationship("Client", back_populates="employment")

class ClientEducation(Base):
    __tablename__ = 'client_education'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    client_id: Mapped[str] = mapped_column(ForeignKey("client.id"), nullable=False)
    started_on: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_on: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    field_of_study: Mapped[str] = mapped_column(String(100), nullable=False)
    degree: Mapped[str] = mapped_column(String(100), nullable=False)
    university_name: Mapped[str] = mapped_column(String(100), nullable=False)

    #clients = relationship("Client", back_populates="education")

class Client(Base):
    __tablename__ = 'client'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    citizenship: Mapped[str] = mapped_column(String(50), nullable=False)
    marital_status: Mapped[str] = mapped_column(String(50), nullable=False)
    id_number: Mapped[str] = mapped_column(String(50), nullable=False)
    id_type: Mapped[str] = mapped_column(String(50), nullable=False)
    country_of_issuance: Mapped[str] = mapped_column(String(50), nullable=False)
    id_issuance_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    id_expiration_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    #agreements = relationship("Agreements", back_populates="clients")
    #employment = relationship("ClientEmployment", back_populates="clients")
    #person = relationship("Person")
    #beneficiary = relationship("Beneficiaries")
    #education = relationship("ClientEducation", back_populates="clients")

class Product(Base):
    __tablename__ = 'product'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    company_id: Mapped[str] = mapped_column(ForeignKey("company.id"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(50), nullable=False)
    product_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    product_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class Company(Base):
    __tablename__ = 'company'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    title: Mapped[str] = mapped_column(String(50), nullable=False)
    email_domen: Mapped[str] = mapped_column(String(50), nullable=False)
    subscription: Mapped[str] = mapped_column(String(50), nullable=False)
    subscription_term: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    registration_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Consultant(Base):
    __tablename__ = 'consultant'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    company_id: Mapped[str] = mapped_column(ForeignKey("company.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(50), nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    password: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    gender: Mapped[str] = mapped_column(String(50), nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)

class Meet(Base):
    __tablename__ = 'meet'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    client_id: Mapped[str] = mapped_column(ForeignKey("client.id"), nullable=False)
    consultant_id: Mapped[str] = mapped_column(ForeignKey("consultant.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    overview: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    action_items: Mapped[str] = mapped_column(Text, nullable=False)
    trascription: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    tags: Mapped[str] = mapped_column(String(200), nullable=False)
    participants: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    next_meet_scenario: Mapped[str] = mapped_column(Text, nullable=False)

class RealTimeMeetingMessage(Base):
    __tablename__ = 'real_time_meeting_message'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    meet_id: Mapped[str] = mapped_column(ForeignKey("meet.id"), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    email: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

class MeetingChatbotMessage(Base):
    __tablename__ = 'meeting_chatbot_message'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    meet_id: Mapped[str] = mapped_column(ForeignKey("meet.id"), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

class AllChatbotMeetingMessage(Base):
    __tablename__ = 'all_chatbot_meeting_message'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    meet_id: Mapped[str] = mapped_column(ForeignKey("meet.id"), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
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
