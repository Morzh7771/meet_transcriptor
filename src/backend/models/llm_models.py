from pydantic import BaseModel, Field
from typing import List

class SpeakerUtterance(BaseModel):
    speaker: str
    text: str

class MatchSpeakersOtput(BaseModel):
    transcript: List[SpeakerUtterance] = Field(
        ...,
        description="List of speaker utterances in the meeting"
    )

class RouterResponse(BaseModel):
    output: str = Field(..., description="A simple answer to user's question")
