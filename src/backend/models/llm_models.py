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


class SummarizerResponse(BaseModel):
    summary: str = Field(..., description="A summary of the meeting transcript")
    tags: List[str] = Field(..., description="A list of tags related to the meeting transcript")

class OverviewResponse(BaseModel):
    overview: List[str] = Field(..., description="A list of key points and outcomes of the meeting")

class NotesResponse(BaseModel):
    notes: str = Field(..., description="The notes of the meeting transcript")

class ActionItemsResponse(BaseModel):
    action_items: str = Field(..., description="The action items list with people responsible for each task")
