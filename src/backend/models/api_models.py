from pydantic import BaseModel
from typing import Optional

class StartMeetingRequest(BaseModel):
    user_id: str
    meet_code: str
    meeting_language: str
    
    
    
class MeetBotChat(BaseModel):
    chat_id: Optional[str] = None
    message: str
    meet_id: str