from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

class PlanCreate(BaseModel):
    client_id: str 
    plan_type: str
    provider: str
    plan_code: str
    plan_name: str
    employer_tax_id: str
    roth_first_year: float = Field(..., description="Roth contribution for the first year")

class PlanUpdate(BaseModel):
    plan_type: Optional[str]
    provider: Optional[str]
    plan_code: Optional[str]
    plan_name: Optional[str]
    employer_tax_id: Optional[str]
    roth_first_year: Optional[float]

class PlanResponse(BaseModel):
    id: str
    client_id: str
    plan_type: str
    provider: str
    plan_code: str
    plan_name: str
    employer_tax_id: str
    roth_first_year: float

    model_config = ConfigDict(from_attributes=True)

class PersonAddressCreate(BaseModel):
    person_id: str
    address_type: str
    street: str
    city: str
    state: str
    country: str
    zip_code: str

class PersonAddressUpdate(BaseModel):
    address_type: Optional[str]
    street: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    zip_code: Optional[str]

class PersonAddressResponse(BaseModel):
    id: str
    person_id: str
    address_type: str
    street: str
    city: str
    state: str
    zip_code: str
    country: str

    model_config = ConfigDict(from_attributes=True)

class personCreate(BaseModel):
    client_id: str
    beneficiary_id: str
    first_name: str
    middle_name: str
    last_name: str
    date_of_birth: datetime
    sex: str
    ssn_or_tin: str
    email: str
    phone_number: str
    phone_alt: Optional[str]

class personUpdate(BaseModel):
    first_name: Optional[str]
    middle_name: Optional[str]
    last_name: Optional[str]
    date_of_birth: Optional[datetime]
    sex: Optional[str]
    ssn_or_tin: Optional[str]
    email: Optional[str]
    phone_number: Optional[str]
    phone_alt: Optional[str]

class personResponse(BaseModel):
    id: str
    client_id: str
    beneficiary_id: str
    first_name: str
    middle_name: str
    last_name: str
    date_of_birth: datetime
    sex: str
    ssn_or_tin: str
    email: str
    phone_number: str
    phone_alt: str

    model_config = ConfigDict(from_attributes=True)

class BeneficiaryCreate(BaseModel):
    client_id: str
    beneficiary_type: str
    relation: str
    share_percentage: float

class BeneficiaryUpdate(BaseModel):
    beneficiary_type: Optional[str]
    relation: Optional[str]
    share_percentage: Optional[float]

class BeneficiaryResponse(BaseModel):
    id: str
    client_id: str
    beneficiary_type: str
    relation: str
    share_percentage: float

    model_config = ConfigDict(from_attributes=True)

# class AgreementsCreate(BaseModel):
#     plan_id: str
#     data_privacy_consent_at: datetime
#     erisa_disclosures_ack_at: datetime
#     plan_document_read_at: datetime
#     e_delivery_consent_at: datetime
#     arbitration_accepted_at: datetime
#     participant_signed_at: datetime
#     participant_signature_at: datetime
#     participant_signature_ref: str
#     admin_signed_at: datetime
#     admin_signature_pdf: str
#     admin_name: str
#     admin_email: str
#     admin_phone: str

# class AgreementsUpdate(BaseModel):
#     plan_id: Optional[str]
#     data_privacy_consent_at: Optional[datetime]
#     erisa_disclosures_ack_at: Optional[datetime]
#     plan_document_read_at: Optional[datetime]
#     e_delivery_consent_at: Optional[datetime]
#     arbitration_accepted_at: Optional[datetime]
#     participant_signed_at: Optional[datetime]
#     participant_signature_at: Optional[datetime]
#     participant_signature_ref: Optional[str]
#     admin_signed_at: Optional[datetime]
#     admin_signature_pdf: Optional[str]
#     admin_name: Optional[str]
#     admin_email: Optional[str]
#     admin_phone: Optional[str]

# class AgreementsResponse(BaseModel):
#     id: int
#     plan_id: str
#     data_privacy_consent_at: datetime
#     erisa_disclosures_ack_at: datetime
#     plan_document_read_at: datetime
#     e_delivery_consent_at: datetime
#     arbitration_accepted_at: datetime
#     participant_signed_at: datetime
#     participant_signature_at: datetime
#     participant_signature_ref: str
#     admin_signed_at: datetime
#     admin_signature_pdf: str
#     admin_name: str
#     admin_email: str
#     admin_phone: str

#     model_config = ConfigDict(from_attributes=True)

class ClientEmploymentCreate(BaseModel):
    client_id: str
    company_name: str
    job_title: str
    job_description: str
    hire_date: datetime
    pay_frequency: str
    year_funds: float
    add_funds: float

class ClientEmploymentUpdate(BaseModel):
    company_name: Optional[str]
    job_title: Optional[str]
    job_description: Optional[str]
    hire_date: Optional[datetime]
    pay_frequency: Optional[str]
    year_funds: Optional[float]
    add_funds: Optional[float]

class ClientEmploymentResponse(BaseModel):
    id: str
    client_id: str
    company_name: str
    job_title: str
    job_description: str
    hire_date: datetime
    pay_frequency: str
    year_funds: float
    add_funds: float

    model_config = ConfigDict(from_attributes=True)

class ClientEducationCreate(BaseModel):
    client_id: str
    started_on: datetime
    ended_on: datetime
    field_of_study: str
    degree: str
    university_name: str

class ClientEducationUpdate(BaseModel):
    started_on: Optional[datetime]
    ended_on: Optional[datetime]
    field_of_study: Optional[str]
    degree: Optional[str]
    university_name: Optional[str]

class ClientEducationResponse(BaseModel):
    id: str
    client_id: str
    started_on: datetime
    ended_on: datetime
    field_of_study: str
    degree: str
    university_name: str

    model_config = ConfigDict(from_attributes=True)

class ClientCreate(BaseModel):
    citizenship: str
    marital_status: str
    id_number: str
    id_type: str
    country_of_issuance: str
    id_issuance_date: datetime
    id_expiration_date: datetime

class ClientUpdate(BaseModel):
    citizenship: Optional[str]
    marital_status: Optional[str]
    id_number: Optional[str]
    id_type: Optional[str]
    country_of_issuance: Optional[str]
    id_issuance_date: Optional[datetime]
    id_expiration_date: Optional[datetime]

class ClientResponse(BaseModel):
    id: str
    citizenship: str
    marital_status: str
    id_number: str
    id_type: str
    country_of_issuance: str
    id_issuance_date: datetime
    id_expiration_date: datetime

    model_config = ConfigDict(from_attributes=True)

class ProductCreate(BaseModel):
    company_id: str
    product_name: str
    product_code: str
    product_type: str
    description: str

class ProductUpdate(BaseModel):
    company_id: Optional[str]
    product_name: Optional[str]
    product_code: Optional[str]
    product_type: Optional[str]
    description: Optional[str]

class ProductResponse(BaseModel):
    id: str
    company_id: str
    product_name: str
    product_code: str
    product_type: str
    description: str

    model_config = ConfigDict(from_attributes=True)

class CompanyCreate(BaseModel):
    title: str
    email_domen: str
    subscription: str
    subscription_term: datetime
    registration_date: datetime

class CompanyUpdate(BaseModel):
    title: Optional[str]
    email_domen: Optional[str]
    subscription: Optional[str]
    subscription_term: Optional[datetime]
    registration_date: Optional[datetime]

class CompanyResponse(BaseModel):
    id: str
    title: str
    email_domen: str
    subscription: str
    subscription_term: datetime
    registration_date: datetime

    model_config = ConfigDict(from_attributes=True)

class ConsultantCreate(BaseModel):
    company_id: str
    email: str
    username: str
    password: str
    role: str
    gender: str
    language: str

class ConsultantUpdate(BaseModel):
    company_id: Optional[str]
    email: Optional[str]
    username: Optional[str]
    password: Optional[str]
    role: Optional[str]
    gender: Optional[str]
    language: Optional[str]

class ConsultantResponse(BaseModel):
    id: str
    company_id: str
    email: str
    username: str
    password: str
    role: str
    gender: str
    language: str

    model_config = ConfigDict(from_attributes=True)

class MeetCreate(BaseModel):
    client_id: str
    consultant_id: str
    title: str
    summary: Optional[str] = "No summary provided"
    date: datetime
    duration: Optional[int] = 0
    overview: Optional[str] = "No overview provided"
    notes: Optional[str] = "No notes provided"
    action_items: Optional[str] = "No action items provided"
    trascription: Optional[str] = "No transcript provided"
    language: str
    tags: Optional[str] = "No tags provided"
    participants: Optional[List[str]] = None
    next_meet_scenario: Optional[str] = ""

class MeetUpdate(BaseModel):
    client_id: Optional[str] = None
    consultant_id: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    date: Optional[datetime] = None
    duration: Optional[int] = None
    overview: Optional[str] = None
    notes: Optional[str] = None
    action_items: Optional[str] = None
    trascription: Optional[str] = None
    language: Optional[str] = None
    tags: Optional[str] = None
    participants: Optional[List[str]] = None
    next_meet_scenario: Optional[str] = None

class MeetResponse(BaseModel):
    id: str
    client_id: str
    consultant_id: str
    title: str
    summary: str
    date: datetime
    duration: int
    overview: str
    notes: str
    action_items: str
    trascription: str
    language: str
    tags: str
    participants: List[str]
    next_meet_scenario: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class RealTimeMeetingMessageCreate(BaseModel):
    meet_id: str
    time: datetime
    email: str
    content: str

class RealTimeMeetingMessageUpdate(BaseModel):
    meet_id: Optional[str]
    time: Optional[datetime]
    email: Optional[str]
    content: Optional[str]

class RealTimeMeetingMessageResponse(BaseModel):
    id: str
    meet_id: str
    time: datetime
    email: str
    content: str

    model_config = ConfigDict(from_attributes=True)

class MeetingChatbotMessageCreate(BaseModel):
    meet_id: str
    time: datetime
    role: str
    content: str

class MeetingChatbotMessageUpdate(BaseModel):
    meet_id: Optional[str]
    time: Optional[datetime]
    role: Optional[str]
    content: Optional[str]

class MeetingChatbotMessageResponse(BaseModel):
    id: str
    meet_id: str
    time: datetime
    role: str
    content: str

    model_config = ConfigDict(from_attributes=True)

class AllChatbotMeetingMessageCreate(BaseModel):
    meet_id: str
    time: datetime
    role: str
    content: str

class AllChatbotMeetingMessageUpdate(BaseModel):
    meet_id: Optional[str]
    time: Optional[datetime]
    role: Optional[str]
    content: Optional[str]

class AllChatbotMeetingMessageResponse(BaseModel):
    id: str
    meet_id: str
    time: datetime
    role: str
    content: str

    model_config = ConfigDict(from_attributes=True)

class FrontMessageCreate(BaseModel):
    chat_id: str
    meet_id: str
    content: str
    time: datetime 
    role: str

class FrontMessageUpdate(BaseModel):
    chat_id: Optional[str] = None
    meet_id: Optional[str] = None
    content: Optional[str] = None
    time: Optional[datetime] = None
    role: Optional[str] = None

class FrontMessageResponse(BaseModel):
    id: str
    chat_id: str
    meet_id: str
    content: str
    time: datetime
    role: str
    
    model_config = ConfigDict(from_attributes=True)
