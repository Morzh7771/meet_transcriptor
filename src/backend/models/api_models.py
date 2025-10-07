from pydantic import BaseModel
from typing import Optional,List

class StartMeetingRequest(BaseModel):
    client_id: str
    meet_code: str
    meeting_language: str
    consultant_id: str
    
    
    
class MeetBotChat(BaseModel):
    chat_id: Optional[str] = None
    message: str
    meet_id: str
    
    
class GetChatTopics(BaseModel):
    meet_id: str

class EmploymentInfo(BaseModel):
    company_name: str
    job_title: str
    job_description: str
    start_date: str | None = None
    end_date: str | None = None

class EducationInfo(BaseModel):
    university_name: str
    degree: str | None = None  # Make optional
    field_of_study: str | None = None  # Make optional
    start_date: str | None = None
    end_date: str | None = None

class LinkedInParseRequest(BaseModel):
    linkedin_url: str

class LinkedInParseResponse(BaseModel):
    message: str
    employments: List[EmploymentInfo]
    educations: List[EducationInfo]
    
    
class ScenarioRequest(BaseModel):
    email: str
    meet_id: str

class ScenarioResponse(BaseModel):
    scenario: str
    
class ScenarioRequestFirst(BaseModel):
    client_id: str
    consultant_id: str

class ScenarioResponseFirst(BaseModel):
    scenario: str
    meet_id: str
class RAGChat(BaseModel):
    message: str
    chat_id: Optional[str] = None
    user_id: Optional[str] = None
