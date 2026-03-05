from pydantic import BaseModel


class StartMeetingRequest(BaseModel):
    """Minimal: meet_code only. Language auto-detected by Groq (ru/uk/en mix)."""
    meet_code: str
    meeting_language: str | None = None
