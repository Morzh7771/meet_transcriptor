from typing import List, Tuple
from pydantic import BaseModel, Field

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
