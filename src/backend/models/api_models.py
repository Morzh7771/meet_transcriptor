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

class LinkedInParseRequest(BaseModel):
    linkedin_url: str
    client_id: str
class LinkedInParseResponse(BaseModel):
    message: str
    client_id: str
    employments_added: int
    educations_added: int
    companies_info: List[dict]
    
    
class ScenarioRequest(BaseModel):
    email: str
    meet_id: str

class ScenarioResponse(BaseModel):
    scenario: str
    
class RAGChat(BaseModel):
    message: str
    chat_id: Optional[str] = None
    user_id: Optional[str] = None
