from pydantic import BaseModel
from typing import Optional

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
