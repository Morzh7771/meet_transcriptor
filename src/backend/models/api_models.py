from pydantic import BaseModel


class StartMeetingRequest(BaseModel):
    meet_code: str
    meeting_language: str