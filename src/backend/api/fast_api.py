import asyncio
from typing import List,Dict
from fastapi import FastAPI, HTTPException, Body,status
from fastapi.middleware.cors import CORSMiddleware
from src.backend.models.api_models import *
from src.backend.core.Facade import Facade
from contextlib import asynccontextmanager
from datetime import datetime
from pydantic import BaseModel
from src.backend.db.dbFacade import DBFacade
from src.backend.models.db_models import *
from src.backend.scenario_generator.scenarioFacade import ScenarioFacade
from src.backend.parser.linkedin_parser import LinkedInParser
from src.backend.vector_db.qdrant_Facade import VectorDBFacade

scenario_facade = ScenarioFacade()
db_facade = DBFacade()
facade = Facade()
vector_db = VectorDBFacade()
@asynccontextmanager
async def lifespan(app: FastAPI):
    
    await db_facade.create_tables()
    await vector_db.ensure_client_profiles_initialized()
    yield
    
app = FastAPI(
    title="Database Management API",
    description="Complete CRUD API for managing all database entities",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# One Facade for the whole service.
facade = Facade()
db = DBFacade()
vector_db = VectorDBFacade()
# Keep track of recorder coroutines keyed by meet-code (or any session ID you prefer).
_session_tasks: Dict[str, asyncio.Task] = {}


@app.post("/start")
async def start(request: StartMeetingRequest):
    """
    Launch recording for *meet_code*.
    """
    try:
        print(request)
        meet_code = request.meet_code.strip()
        ws_port = await facade.find_free_port()
        chat_port = await facade.find_free_port()
        
        while chat_port == ws_port:
            chat_port = await facade.find_free_port()
            
        if not meet_code:
            raise HTTPException(400, detail="Body must contain a non-empty meet code")

        #if meet_code in _session_tasks:
            #raise HTTPException(409, detail=f"Recording for {meet_code} is already running")

        # fire-and-forget recorder; store task so we can await / cancel later
        _session_tasks[meet_code] = asyncio.create_task(
            facade.run_google_meet_recording_api(request.client_id, meet_code, request.meeting_language, ws_port, chat_port,request.consultant_id)
        )
        
        return {
            "ok": True,
            "status": "started", 
            "meet_code": meet_code, 
            "ws_port": ws_port, 
            "chat_port": chat_port
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }

@app.post("/terminate")
async def terminate(meet_code: str = Body(..., embed=False)):
    """
    Stop recording for *meet_code*.
    """
    meet_code = meet_code.strip()
    task = _session_tasks.get(meet_code)
    if not task:
        raise HTTPException(404, detail=f"No active session for {meet_code}")

    # Ask the JS plugin to shut the session down.
    await facade.js_plugin_api.terminate_by_meet_code(meet_code)

    # Optionally give the recorder coroutine up to 30 s to finish gracefully.
    try:
        await asyncio.wait_for(task, timeout=30)
    except asyncio.TimeoutError:
        task.cancel()

    _session_tasks.pop(meet_code, None)
    return {"status": "terminated", "meet_code": meet_code}


@app.post("/getAllMeets")
async def getAllMeets():
    result = await db.get_all_meets()
    return result

@app.post("/rag_chat")
async def rag_chat(request: RAGChat):
        res = await facade.process_rag_chat(request.message,request.chat_id,request.user_id)
        return res


@app.post("/sql_to_vector")
async def sql_to_vector(recreate: bool = False):
        stats = await facade.sync( recreate)
        return {"ok": True, **stats}


@app.post("/meetBotChat")
async def meetBotChat(request: MeetBotChat):
    res = await facade.startMessageBot(request.message,request.meet_id,request.chat_id)
    return res


@app.post("/getChatTopics")
async def getChatTopics(request: GetChatTopics):
    res = await db.get_all_meet_topics(request.meet_id)
    return res


# ============ PLAN ENDPOINTS ============
@app.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED, tags=["Plans"])
async def create_plan(plan: PlanCreate):
    """Create a new plan"""
    return await db_facade.create_plan(plan)
@app.get("/plans/{plan_id}", response_model=PlanResponse, tags=["Plans"])
async def get_plan(plan_id: str):
    """Get plan by ID"""
    plan = await db_facade.get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan
@app.get("/plans/code/{plan_code}", response_model=PlanResponse, tags=["Plans"])
async def get_plan_by_code(plan_code: str):
    """Get plan by plan code"""
    plan = await db_facade.get_plan_by_code(plan_code)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan
@app.get("/plans", response_model=List[PlanResponse], tags=["Plans"])
async def get_all_plans():
    """Get all plans"""
    return await db_facade.get_all_plans()
@app.patch("/plans/{plan_id}", response_model=PlanResponse, tags=["Plans"])
async def update_plan(plan_id: str, plan_update: PlanUpdate):
    """Update plan"""
    plan = await db_facade.update_plan(plan_id, plan_update)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan
@app.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Plans"])
async def delete_plan(plan_id: str):
    """Delete plan"""
    success = await db_facade.delete_plan(plan_id)
    if not success:
        raise HTTPException(status_code=404, detail="Plan not found")
# ============ PERSON ADDRESS ENDPOINTS ============
@app.post("/addresses", response_model=PersonAddressResponse, status_code=status.HTTP_201_CREATED, tags=["Addresses"])
async def create_address(address: PersonAddressCreate):
    """Create a new person address"""
    return await db_facade.create_person_address(address)
@app.get("/addresses/{address_id}", response_model=PersonAddressResponse, tags=["Addresses"])
async def get_address(address_id: str):
    """Get address by ID"""
    address = await db_facade.get_person_address_by_id(address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return address
@app.get("/addresses", response_model=List[PersonAddressResponse], tags=["Addresses"])
async def get_all_addresses():
    """Get all addresses"""
    return await db_facade.get_all_person_addresses()
@app.patch("/addresses/{address_id}", response_model=PersonAddressResponse, tags=["Addresses"])
async def update_address(address_id: str, address_update: PersonAddressUpdate):
    """Update address"""
    address = await db_facade.update_person_address(address_id, address_update)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return address
@app.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Addresses"])
async def delete_address(address_id: str):
    """Delete address"""
    success = await db_facade.delete_person_address(address_id)
    if not success:
        raise HTTPException(status_code=404, detail="Address not found")
# ============ PERSON ENDPOINTS ============
@app.post("/persons", response_model=personResponse, status_code=status.HTTP_201_CREATED, tags=["Persons"])
async def create_person(person: personCreate):
    """Create a new person"""
    return await db_facade.create_person(person)
@app.get("/persons/{person_id}", response_model=personResponse, tags=["Persons"])
async def get_person(person_id: str):
    """Get person by ID"""
    person = await db_facade.get_person_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person
@app.get("/persons/email/{email}", response_model=personResponse, tags=["Persons"])
async def get_person_by_email(email: str):
    """Get person by email"""
    person = await db_facade.get_person_by_email(email)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person
@app.get("/persons", response_model=List[personResponse], tags=["Persons"])
async def get_all_persons():
    """Get all persons"""
    return await db_facade.get_all_persons()
@app.patch("/persons/{person_id}", response_model=personResponse, tags=["Persons"])
async def update_person(person_id: str, person_update: personUpdate):
    """Update person"""
    person = await db_facade.update_person(person_id, person_update)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person
@app.delete("/persons/{person_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Persons"])
async def delete_person(person_id: str):
    """Delete person"""
    success = await db_facade.delete_person(person_id)
    if not success:
        raise HTTPException(status_code=404, detail="Person not found")
# ============ BENEFICIARY ENDPOINTS ============
@app.post("/beneficiaries", response_model=BeneficiaryResponse, status_code=status.HTTP_201_CREATED, tags=["Beneficiaries"])
async def create_beneficiary(beneficiary: BeneficiaryCreate):
    """Create a new beneficiary"""
    return await db_facade.create_beneficiary(beneficiary)
@app.get("/beneficiaries/{beneficiary_id}", response_model=BeneficiaryResponse, tags=["Beneficiaries"])
async def get_beneficiary(beneficiary_id: str):
    """Get beneficiary by ID"""
    beneficiary = await db_facade.get_beneficiary_by_id(beneficiary_id)
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")
    return beneficiary
@app.get("/beneficiaries", response_model=List[BeneficiaryResponse], tags=["Beneficiaries"])
async def get_all_beneficiaries():
    """Get all beneficiaries"""
    return await db_facade.get_all_beneficiaries()
@app.patch("/beneficiaries/{beneficiary_id}", response_model=BeneficiaryResponse, tags=["Beneficiaries"])
async def update_beneficiary(beneficiary_id: str, beneficiary_update: BeneficiaryUpdate):
    """Update beneficiary"""
    beneficiary = await db_facade.update_beneficiary(beneficiary_id, beneficiary_update)
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")
    return beneficiary
@app.delete("/beneficiaries/{beneficiary_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Beneficiaries"])
async def delete_beneficiary(beneficiary_id: str):
    """Delete beneficiary"""
    success = await db_facade.delete_beneficiary(beneficiary_id)
    if not success:
        raise HTTPException(status_code=404, detail="Beneficiary not found")
# ============ CLIENT EMPLOYMENT ENDPOINTS ============
@app.post("/employments", response_model=ClientEmploymentResponse, status_code=status.HTTP_201_CREATED, tags=["Employment"])
async def create_employment(employment: ClientEmploymentCreate):
    """Create a new employment record"""
    return await db_facade.create_client_employment(employment)
@app.get("/employments/{employment_id}", response_model=ClientEmploymentResponse, tags=["Employment"])
async def get_employment(employment_id: str):
    """Get employment by ID"""
    employment = await db_facade.get_client_employment_by_id(employment_id)
    if not employment:
        raise HTTPException(status_code=404, detail="Employment not found")
    return employment
@app.get("/employments", response_model=List[ClientEmploymentResponse], tags=["Employment"])
async def get_all_employments():
    """Get all employment records"""
    return await db_facade.get_all_client_employments()
@app.patch("/employments/{employment_id}", response_model=ClientEmploymentResponse, tags=["Employment"])
async def update_employment(employment_id: str, employment_update: ClientEmploymentUpdate):
    """Update employment"""
    employment = await db_facade.update_client_employment(employment_id, employment_update)
    if not employment:
        raise HTTPException(status_code=404, detail="Employment not found")
    return employment
@app.delete("/employments/{employment_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Employment"])
async def delete_employment(employment_id: str):
    """Delete employment"""
    success = await db_facade.delete_client_employment(employment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Employment not found")
# ============ CLIENT EDUCATION ENDPOINTS ============
@app.post("/educations", response_model=ClientEducationResponse, status_code=status.HTTP_201_CREATED, tags=["Education"])
async def create_education(education: ClientEducationCreate):
    """Create a new education record"""
    return await db_facade.create_client_education(education)
@app.get("/educations/{education_id}", response_model=ClientEducationResponse, tags=["Education"])
async def get_education(education_id: str):
    """Get education by ID"""
    education = await db_facade.get_client_education_by_id(education_id)
    if not education:
        raise HTTPException(status_code=404, detail="Education not found")
    return education
@app.get("/educations", response_model=List[ClientEducationResponse], tags=["Education"])
async def get_all_educations():
    """Get all education records"""
    return await db_facade.get_all_client_educations()
@app.patch("/educations/{education_id}", response_model=ClientEducationResponse, tags=["Education"])
async def update_education(education_id: str, education_update: ClientEducationUpdate):
    """Update education"""
    education = await db_facade.update_client_education(education_id, education_update)
    if not education:
        raise HTTPException(status_code=404, detail="Education not found")
    return education
@app.delete("/educations/{education_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Education"])
async def delete_education(education_id: str):
    """Delete education"""
    success = await db_facade.delete_client_education(education_id)
    if not success:
        raise HTTPException(status_code=404, detail="Education not found")
# ============ CLIENT ENDPOINTS ============
@app.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED, tags=["Clients"])
async def create_client(client: ClientCreate):
    """Create a new client"""
    return await db_facade.create_client(client)
@app.get("/clients/{client_id}", response_model=ClientResponse, tags=["Clients"])
async def get_client(client_id: str):
    """Get client by ID"""
    client = await db_facade.get_client_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
@app.get("/clients", response_model=List[ClientResponse], tags=["Clients"])
async def get_all_clients():
    """Get all clients"""
    return await db_facade.get_all_clients()
@app.patch("/clients/{client_id}", response_model=ClientResponse, tags=["Clients"])
async def update_client(client_id: str, client_update: ClientUpdate):
    """Update client"""
    client = await db_facade.update_client(client_id, client_update)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
@app.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Clients"])
async def delete_client(client_id: str):
    """Delete client"""
    success = await db_facade.delete_client(client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Client not found")
# ============ PRODUCT ENDPOINTS ============
@app.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, tags=["Products"])
async def create_product(product: ProductCreate):
    """Create a new product"""
    return await db_facade.create_product(product)
@app.get("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
async def get_product(product_id: str):
    """Get product by ID"""
    product = await db_facade.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
@app.get("/products/code/{product_code}", response_model=ProductResponse, tags=["Products"])
async def get_product_by_code(product_code: str):
    """Get product by product code"""
    product = await db_facade.get_product_by_code(product_code)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
@app.get("/products", response_model=List[ProductResponse], tags=["Products"])
async def get_all_products():
    """Get all products"""
    return await db_facade.get_all_products()
@app.patch("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
async def update_product(product_id: str, product_update: ProductUpdate):
    """Update product"""
    product = await db_facade.update_product(product_id, product_update)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Products"])
async def delete_product(product_id: str):
    """Delete product"""
    success = await db_facade.delete_product(product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
# ============ COMPANY ENDPOINTS ============
@app.post("/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED, tags=["Companies"])
async def create_company(company: CompanyCreate):
    """Create a new company"""
    return await db_facade.create_company(company)
@app.get("/companies/{company_id}", response_model=CompanyResponse, tags=["Companies"])
async def get_company(company_id: str):
    """Get company by ID"""
    company = await db_facade.get_company_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
@app.get("/companies/domain/{email_domain}", response_model=CompanyResponse, tags=["Companies"])
async def get_company_by_domain(email_domain: str):
    """Get company by email domain"""
    company = await db_facade.get_company_by_email_domain(email_domain)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
@app.get("/companies/title/{title}", response_model=CompanyResponse, tags=["Companies"])
async def get_company_by_title(title: str):
    """Get company by title"""
    company = await db_facade.get_company_by_title(title)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
@app.get("/companies", response_model=List[CompanyResponse], tags=["Companies"])
async def get_all_companies():
    """Get all companies"""
    return await db_facade.get_all_companies()
@app.patch("/companies/{company_id}", response_model=CompanyResponse, tags=["Companies"])
async def update_company(company_id: str, company_update: CompanyUpdate):
    """Update company"""
    company = await db_facade.update_company(company_id, company_update)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
@app.delete("/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Companies"])
async def delete_company(company_id: str):
    """Delete company"""
    success = await db_facade.delete_company(company_id)
    if not success:
        raise HTTPException(status_code=404, detail="Company not found")
# ============ CONSULTANT ENDPOINTS ============
@app.post("/consultants", response_model=ConsultantResponse, status_code=status.HTTP_201_CREATED, tags=["Consultants"])
async def create_consultant(consultant: ConsultantCreate):
    """Create a new consultant"""
    return await db_facade.create_consultant(consultant)
@app.get("/consultants/{consultant_id}", response_model=ConsultantResponse, tags=["Consultants"])
async def get_consultant(consultant_id: str):
    """Get consultant by ID"""
    consultant = await db_facade.get_consultant_by_id(consultant_id)
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    return consultant
@app.get("/consultants/email/{email}", response_model=ConsultantResponse, tags=["Consultants"])
async def get_consultant_by_email(email: str):
    """Get consultant by email"""
    consultant = await db_facade.get_consultant_by_email(email)
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    return consultant
@app.get("/consultants/username/{username}", response_model=ConsultantResponse, tags=["Consultants"])
async def get_consultant_by_username(username: str):
    """Get consultant by username"""
    consultant = await db_facade.get_consultant_by_username(username)
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    return consultant
@app.get("/consultants", response_model=List[ConsultantResponse], tags=["Consultants"])
async def get_all_consultants():
    """Get all consultants"""
    return await db_facade.get_all_consultants()
@app.patch("/consultants/{consultant_id}", response_model=ConsultantResponse, tags=["Consultants"])
async def update_consultant(consultant_id: str, consultant_update: ConsultantUpdate):
    """Update consultant"""
    consultant = await db_facade.update_consultant(consultant_id, consultant_update)
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    return consultant
@app.delete("/consultants/{consultant_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Consultants"])
async def delete_consultant(consultant_id: str):
    """Delete consultant"""
    success = await db_facade.delete_consultant(consultant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Consultant not found")
# ============ MEET ENDPOINTS ============
@app.post("/meets", response_model=MeetResponse, status_code=status.HTTP_201_CREATED, tags=["Meetings"])
async def create_meet(meet: MeetCreate):
    """Create a new meeting"""
    return await db_facade.create_meet(meet)
@app.get("/meets/{meet_id}", response_model=MeetResponse, tags=["Meetings"])
async def get_meet(meet_id: str):
    """Get meeting by ID"""
    meet = await db_facade.get_meet_by_id(meet_id)
    if not meet:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meet
@app.get("/meets/client/{client_id}", response_model=List[MeetResponse], tags=["Meetings"])
async def get_meets_by_client(client_id: str):
    """Get all meetings for a client"""
    return await db_facade.get_meets_by_client_id(client_id)
@app.get("/meets/consultant/{consultant_id}", response_model=List[MeetResponse], tags=["Meetings"])
async def get_meets_by_consultant(consultant_id: str):
    """Get all meetings for a consultant"""
    return await db_facade.get_meets_by_consultant_id(consultant_id)
@app.get("/meets", response_model=List[MeetResponse], tags=["Meetings"])
async def get_all_meets():
    """Get all meetings"""
    return await db_facade.get_all_meets()
@app.patch("/meets/{meet_id}", response_model=MeetResponse, tags=["Meetings"])
async def update_meet(meet_id: str, meet_update: MeetUpdate):
    """Update meeting"""
    meet = await db_facade.update_meet(meet_id, meet_update)
    if not meet:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meet
@app.delete("/meets/{meet_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Meetings"])
async def delete_meet(meet_id: str):
    """Delete meeting"""
    success = await db_facade.delete_meet(meet_id)
    if not success:
        raise HTTPException(status_code=404, detail="Meeting not found")
# ============ REAL TIME MEETING MESSAGE ENDPOINTS ============
@app.post("/real-time-messages", response_model=RealTimeMeetingMessageResponse, status_code=status.HTTP_201_CREATED, tags=["Real-Time Messages"])
async def create_real_time_message(message: RealTimeMeetingMessageCreate):
    """Create a new real-time meeting message"""
    return await db_facade.create_real_time_meeting_message(message)
@app.get("/real-time-messages/{message_id}", response_model=RealTimeMeetingMessageResponse, tags=["Real-Time Messages"])
async def get_real_time_message(message_id: str):
    """Get real-time message by ID"""
    message = await db_facade.get_real_time_meeting_message_by_id(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message
@app.get("/real-time-messages/meet/{meet_id}", response_model=List[RealTimeMeetingMessageResponse], tags=["Real-Time Messages"])
async def get_real_time_messages_by_meet(meet_id: str):
    """Get all real-time messages for a meeting"""
    return await db_facade.get_real_time_meeting_messages_by_meet_id(meet_id)
@app.get("/real-time-messages/email/{email}", response_model=List[RealTimeMeetingMessageResponse], tags=["Real-Time Messages"])
async def get_real_time_messages_by_email(email: str):
    """Get all real-time messages by email"""
    return await db_facade.get_real_time_meeting_messages_by_email(email)
@app.get("/real-time-messages", response_model=List[RealTimeMeetingMessageResponse], tags=["Real-Time Messages"])
async def get_all_real_time_messages():
    """Get all real-time messages"""
    return await db_facade.get_all_real_time_meeting_messages()
@app.patch("/real-time-messages/{message_id}", response_model=RealTimeMeetingMessageResponse, tags=["Real-Time Messages"])
async def update_real_time_message(message_id: str, message_update: RealTimeMeetingMessageUpdate):
    """Update real-time message"""
    message = await db_facade.update_real_time_meeting_message(message_id, message_update)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message
@app.delete("/real-time-messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Real-Time Messages"])
async def delete_real_time_message(message_id: str):
    """Delete real-time message"""
    success = await db_facade.delete_real_time_meeting_message(message_id)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found")
# ============ MEETING CHATBOT MESSAGE ENDPOINTS ============
@app.post("/chatbot-messages", response_model=MeetingChatbotMessageResponse, status_code=status.HTTP_201_CREATED, tags=["Chatbot Messages"])
async def create_chatbot_message(message: MeetingChatbotMessageCreate):
    """Create a new meeting chatbot message"""
    return await db_facade.create_meeting_chatbot_message(message)
@app.get("/chatbot-messages/{message_id}", response_model=MeetingChatbotMessageResponse, tags=["Chatbot Messages"])
async def get_chatbot_message(message_id: str):
    """Get chatbot message by ID"""
    message = await db_facade.get_meeting_chatbot_message_by_id(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message
@app.get("/chatbot-messages/meet/{meet_id}", response_model=List[MeetingChatbotMessageResponse], tags=["Chatbot Messages"])
async def get_chatbot_messages_by_meet(meet_id: str):
    """Get all chatbot messages for a meeting"""
    return await db_facade.get_meeting_chatbot_messages_by_meet_id(meet_id)
@app.get("/chatbot-messages/role/{role}", response_model=List[MeetingChatbotMessageResponse], tags=["Chatbot Messages"])
async def get_chatbot_messages_by_role(role: str):
    """Get all chatbot messages by role"""
    return await db_facade.get_meeting_chatbot_messages_by_role(role)
@app.get("/chatbot-messages", response_model=List[MeetingChatbotMessageResponse], tags=["Chatbot Messages"])
async def get_all_chatbot_messages():
    """Get all chatbot messages"""
    return await db_facade.get_all_meeting_chatbot_messages()
@app.patch("/chatbot-messages/{message_id}", response_model=MeetingChatbotMessageResponse, tags=["Chatbot Messages"])
async def update_chatbot_message(message_id: str, message_update: MeetingChatbotMessageUpdate):
    """Update chatbot message"""
    message = await db_facade.update_meeting_chatbot_message(message_id, message_update)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message
@app.delete("/chatbot-messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Chatbot Messages"])
async def delete_chatbot_message(message_id: str):
    """Delete chatbot message"""
    success = await db_facade.delete_meeting_chatbot_message(message_id)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found")
# ============ ALL CHATBOT MEETING MESSAGE ENDPOINTS ============
@app.post("/all-chatbot-messages", response_model=AllChatbotMeetingMessageResponse, status_code=status.HTTP_201_CREATED, tags=["All Chatbot Messages"])
async def create_all_chatbot_message(message: AllChatbotMeetingMessageCreate):
    """Create a new all chatbot meeting message"""
    return await db_facade.create_all_chatbot_meeting_message(message)
@app.get("/all-chatbot-messages/{message_id}", response_model=AllChatbotMeetingMessageResponse, tags=["All Chatbot Messages"])
async def get_all_chatbot_message(message_id: str):
    """Get all chatbot message by ID"""
    message = await db_facade.get_all_chatbot_meeting_message_by_id(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message
@app.get("/all-chatbot-messages/meet/{meet_id}", response_model=List[AllChatbotMeetingMessageResponse], tags=["All Chatbot Messages"])
async def get_all_chatbot_messages_by_meet(meet_id: str):
    """Get all chatbot messages for a meeting"""
    return await db_facade.get_all_chatbot_meeting_messages_by_meet_id(meet_id)
@app.get("/all-chatbot-messages/role/{role}", response_model=List[AllChatbotMeetingMessageResponse], tags=["All Chatbot Messages"])
async def get_all_chatbot_messages_by_role(role: str):
    """Get all chatbot messages by role"""
    return await db_facade.get_all_chatbot_meeting_messages_by_role(role)
@app.get("/all-chatbot-messages", response_model=List[AllChatbotMeetingMessageResponse], tags=["All Chatbot Messages"])
async def get_all_chatbot_messages():
    """Get all chatbot messages"""
    return await db_facade.get_all_chatbot_meeting_messages()
@app.patch("/all-chatbot-messages/{message_id}", response_model=AllChatbotMeetingMessageResponse, tags=["All Chatbot Messages"])
async def update_all_chatbot_message(message_id: str, message_update: AllChatbotMeetingMessageUpdate):
    """Update all chatbot message"""
    message = await db_facade.update_all_chatbot_meeting_message(message_id, message_update)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message
@app.delete("/all-chatbot-messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["All Chatbot Messages"])
async def delete_all_chatbot_message(message_id: str):
    """Delete all chatbot message"""
    success = await db_facade.delete_all_chatbot_meeting_message(message_id)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found")
# ============ UTILITY ENDPOINTS ============
@app.get("/", tags=["Health"])
async def root():
    """API health check"""
    return {"status": "ok", "message": "Database Management API is running"}
@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "version": "1.0.0"
    }
@app.post("/generate_scenario_for_user", response_model=ScenarioResponse, tags=["Scenarios"])
async def generate_scenario_for_user(request: ScenarioRequest):
    scenario = await scenario_facade.generate_scenario_for_user(user_email=request.email)
    await db_facade.update_meet(request.meet_id, MeetUpdate(next_meet_scenario=scenario))
    return ScenarioResponse(scenario=scenario)

# ============ LINKEDIN PARSER ENDPOINTS ============

@app.post("/parse-linkedin", response_model=LinkedInParseResponse, tags=["LinkedIn"])
async def parse_linkedin_profile(request: LinkedInParseRequest):
    linkedin_parser = LinkedInParser(request.linkedin_url)
    try:
        client = await db_facade.get_client_by_id(request.client_id)
        if not client:
            raise HTTPException(status_code=404, detail=f"Client with ID {request.client_id} not found")
        
        parsed_data = linkedin_parser.parse_user()
        
        employments_added = 0
        educations_added = 0
        
        for company in parsed_data.get("companies", []):
            try:
                employment_data = ClientEmploymentCreate(
                    client_id=request.client_id,
                    company_name=company.get("name", "Unknown"),
                    job_title="", 
                    job_description=company.get("description", ""),
                    hire_date=datetime.now(),
                    pay_frequency="",
                    year_funds=0.0,
                    add_funds=0.0
                )
                await db_facade.create_client_employment(employment_data)
                employments_added += 1
            except Exception as e:
                print(f"Error adding employment for {company.get('name')}: {e}")
        
        for edu in parsed_data.get("educations", []):
            try:
                university = edu.get("university") or edu.get("school") or "Unknown"
                degree = edu.get("degree") or ""
                field = edu.get("field") or edu.get("fields_of_study") or ""
                start_year = edu.get("start") or edu.get("start_year")
                end_year = edu.get("end") or edu.get("end_year")
                start_date = datetime(int(start_year), 1, 1) if start_year else None
                end_date = datetime(int(end_year), 12, 31) if end_year else None
                education_data = ClientEducationCreate(
                    client_id=request.client_id,
                    started_on=start_date,
                    ended_on=end_date,
                    field_of_study=field,
                    degree=degree,
                    university_name=university
                )
                await db_facade.create_client_education(education_data)
                educations_added += 1
            except Exception as e:
                print(f"Error adding education for {edu}: {e}")
        return LinkedInParseResponse(
            message="LinkedIn profile parsed successfully",
            client_id=request.client_id,
            employments_added=employments_added,
            educations_added=educations_added,
            companies_info=parsed_data.get("companies", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing LinkedIn profile: {str(e)}"
        )