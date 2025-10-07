import asyncio
from typing import List, Dict
from fastapi import FastAPI, HTTPException, Body, status
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
linkedin_parser = LinkedInParser()

# Keep track of recorder coroutines keyed by meet-code
# This allows parallel execution of multiple sessions
_session_tasks: Dict[str, asyncio.Task] = {}
_session_tasks_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_facade.create_tables()
    await vector_db.ensure_client_profiles_initialized()
    yield
    # Clean up any running sessions on shutdown
    async with _session_tasks_lock:
        for meet_code, task in list(_session_tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    
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


@app.post("/start")
async def start(request: StartMeetingRequest):
    """
    Launch recording for meet_code.
    
    Returns only when WebSocket servers are ready and listening.
    Supports parallel execution - can handle 20+ simultaneous starts.
    
    Args:
        request: Contains client_id, meet_code, meeting_language, consultant_id
        
    Returns:
        dict with ok, status, meet_code, ws_port, chat_port
        
    Raises:
        HTTPException: If servers fail to start or meet_code is invalid
    """
    meet_code = None
    task = None
    
    try:
        meet_code = request.meet_code.strip()
        
        if not meet_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Body must contain a non-empty meet code"
            )
        
        # Check if session already exists
        async with _session_tasks_lock:
            if meet_code in _session_tasks and not _session_tasks[meet_code].done():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Recording for {meet_code} is already running"
                )
        
        # Find free ports
        ws_port = await facade.find_free_port()
        chat_port = await facade.find_free_port()
        
        # Ensure different ports
        while chat_port == ws_port:
            chat_port = await facade.find_free_port()
        
        facade.logger.info(
            f"📍 Starting session for {meet_code} with ports: "
            f"ws={ws_port}, chat={chat_port}"
        )
        
        # Create background task for this session
        task = asyncio.create_task(
            facade.run_google_meet_recording_api(
                request.client_id, 
                meet_code, 
                request.meeting_language, 
                ws_port, 
                chat_port, 
                request.consultant_id
            )
        )
        
        # Register task
        async with _session_tasks_lock:
            _session_tasks[meet_code] = task
        
        # Get audio server instance and wait for it to be ready
        audio_server = await facade.get_or_create_audio_server(meet_code)
        servers_ready = await audio_server.wait_until_ready(timeout=15)
        
        if not servers_ready:
            # Clean up the task if servers didn't start
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            async with _session_tasks_lock:
                if meet_code in _session_tasks:
                    del _session_tasks[meet_code]
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"WebSocket servers failed to start within timeout for {meet_code}"
            )
        
        facade.logger.info(
            f"✅ Session {meet_code} started successfully on ports {ws_port}/{chat_port}"
        )
        
        # Setup task cleanup callback
        def task_done_callback(t):
            asyncio.create_task(_cleanup_task(meet_code, t))
        
        task.add_done_callback(task_done_callback)
        
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
        facade.logger.error(f"❌ Failed to start session {meet_code}: {e}", exc_info=True)
        
        # Clean up on any error
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        if meet_code:
            async with _session_tasks_lock:
                if meet_code in _session_tasks:
                    del _session_tasks[meet_code]
        
        return {
            "ok": False,
            "error": str(e)
        }


async def _cleanup_task(meet_code: str, task: asyncio.Task):
    """
    Cleanup callback for completed tasks.
    Removes task from registry and logs completion/errors.
    """
    async with _session_tasks_lock:
        if meet_code in _session_tasks:
            del _session_tasks[meet_code]
    
    try:
        # Check if task raised an exception
        if task.exception():
            facade.logger.error(
                f"❌ Task for {meet_code} failed with exception: {task.exception()}"
            )
        else:
            facade.logger.info(f"✅ Task for {meet_code} completed successfully")
    except asyncio.CancelledError:
        facade.logger.info(f"🛑 Task for {meet_code} was cancelled")
    except Exception as e:
        facade.logger.error(f"❌ Error in task cleanup for {meet_code}: {e}")


@app.post("/stop/{meet_code}")
async def stop(meet_code: str):
    """
    Stop recording session for given meet_code.
    
    Args:
        meet_code: Meeting identifier to stop
        
    Returns:
        dict with ok and status
    """
    try:
        meet_code = meet_code.strip()
        
        async with _session_tasks_lock:
            if meet_code not in _session_tasks:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No active recording found for {meet_code}"
                )
            
            task = _session_tasks[meet_code]
        
        # Get audio server and terminate gracefully
        audio_server = await facade.get_or_create_audio_server(meet_code)
        await audio_server.terminate()
        
        # Wait for task to complete with timeout
        try:
            await asyncio.wait_for(task, timeout=10)
        except asyncio.TimeoutError:
            facade.logger.warning(f"Task for {meet_code} did not stop gracefully, cancelling")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        facade.logger.info(f"✅ Stopped session for {meet_code}")
        
        return {
            "ok": True,
            "status": "stopped",
            "meet_code": meet_code
        }
        
    except HTTPException:
        raise
    except Exception as e:
        facade.logger.error(f"❌ Error stopping session {meet_code}: {e}")
        return {
            "ok": False,
            "error": str(e)
        }


@app.get("/sessions")
async def list_sessions():
    """
    List all active recording sessions.
    
    Returns:
        dict with active sessions and their status
    """
    async with _session_tasks_lock:
        sessions = {
            meet_code: {
                "status": "running" if not task.done() else "completed",
                "done": task.done(),
                "cancelled": task.cancelled() if task.done() else False
            }
            for meet_code, task in _session_tasks.items()
        }
    
    return {
        "ok": True,
        "total_sessions": len(sessions),
        "sessions": sessions
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    async with _session_tasks_lock:
        active_sessions = sum(1 for task in _session_tasks.values() if not task.done())
    
    return {
        "status": "healthy",
        "active_sessions": active_sessions,
        "total_tracked_sessions": len(_session_tasks)
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
    result = await db_facade.get_all_meets()
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
    res = await db_facade.get_all_meet_topics(request.meet_id)
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
    scenario = await scenario_facade.generate_scenario_for_user(client_email=request.email)
    scenario_text = scenario.choices[0].message.content
    await db_facade.update_meet(request.meet_id, MeetUpdate(next_meet_scenario=scenario_text))
    return ScenarioResponse(scenario=scenario_text)

@app.post("/generate_scenario_for_user_first", response_model=ScenarioResponseFirst, tags=["Scenarios"])
async def generate_scenario_for_user_first(request: ScenarioRequestFirst):
    meet_id = await db_facade.create_meet(MeetCreate(
            client_id=request.client_id,
            consultant_id=request.consultant_id,
        ))
    
    person = await db_facade.get_persons_by_client_id(request.client_id)
    scenario = await scenario_facade.generate_scenario_for_user(client_email=person[0].model_dump().get("email"))
    scenario_text = scenario.choices[0].message.content
    await db_facade.update_meet(meet_id, MeetUpdate(next_meet_scenario=scenario_text))
    return ScenarioResponseFirst(scenario=scenario_text,meet_id=meet_id)

# ============ LINKEDIN PARSER ENDPOINTS ============
@app.post("/parse-linkedin", response_model=LinkedInParseResponse, tags=["LinkedIn"])
async def parse_linkedin_profile(request: LinkedInParseRequest):
    """
    Parse a LinkedIn profile and extract employment and education information.
    
    Args:
        request: LinkedInParseRequest containing the linkedin_url
        
    Returns:
        LinkedInParseResponse with parsed employments and educations
        
    Raises:
        HTTPException: If parsing fails
    """
    try:
        # Parse the LinkedIn profile
        parsed_data = await linkedin_parser.parse_user(request.linkedin_url)
        
        employments = []
        educations = []
        
        # Process employment data
        for company in parsed_data.get("companies", []):
            try:
                employment = EmploymentInfo(
                    company_name=company.get("name", "Unknown"),
                    job_title=company.get("title", ""),
                    job_description=company.get("description", ""),
                    start_date=company.get("start_date"),
                    end_date=company.get("end_date")
                )
                employments.append(employment)
            except Exception as e:
                print(f"Error processing employment for {company.get('name')}: {e}")
        
        # Process education data
        for edu in parsed_data.get("educations", []):
            try:
                university = edu.get("university") or edu.get("school") or "Unknown"
                degree = edu.get("degree") or None
                field = edu.get("field") or edu.get("fields_of_study") or None
                start_year = edu.get("start") or edu.get("start_year")
                end_year = edu.get("end") or edu.get("end_year")
                
                start_date = f"{start_year}-01-01" if start_year else None
                end_date = f"{end_year}-12-31" if end_year else None
                
                education = EducationInfo(
                    university_name=university,
                    degree=degree,
                    field_of_study=field,
                    start_date=start_date,
                    end_date=end_date
                )
                educations.append(education)
            except Exception as e:
                print(f"Error processing education for {edu}: {e}")
        
        return LinkedInParseResponse(
            message="LinkedIn profile parsed successfully",
            employments=employments,
            educations=educations
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing LinkedIn profile: {str(e)}"
        )
