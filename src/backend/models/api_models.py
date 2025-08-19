from pydantic import BaseModel


class StartMeetingRequest(BaseModel):
    user_id: str
    meet_code: str
    meeting_language: str