import tiktoken
from src.backend.core.baseFacade import BaseFacade
from src.backend.prompts.promptFacade import PromptFacade
from src.backend.models.llm_models import NotesResponse, SummarizerResponse, OverviewResponse, ActionItemsResponse


class MeetingAnalizer(BaseFacade):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MeetingAnalizer, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        super().__init__()
        self.enc = tiktoken.encoding_for_model("gpt-4o")
        self.CHUNK_SIZE = 20_000
    
    async def summarize(self, full_transcript):

        messages = eval(PromptFacade.get_prompt("summarizer",
                                            meeting_transcript=full_transcript))
        
        result = await self.completion("gpt-4o",
                                        messages=messages,
                                        max_tokens=16000,
                                        output_model=SummarizerResponse)

        return result

    async def generate_notes(self, full_transcript):

        messages = eval(PromptFacade.get_prompt("notes",
                                            meeting_transcript=full_transcript))
        
        result = await self.completion("gpt-4o",
                                        messages=messages,
                                        max_tokens=16000,
                                        output_model=NotesResponse)

        return result

    async def generate_overview(self, full_transcript):

        messages = eval(PromptFacade.get_prompt("overview",
                                            meeting_transcript=full_transcript))
        
        result = await self.completion("gpt-4o",
                                        messages=messages,
                                        max_tokens=16000,
                                        output_model=OverviewResponse)

        return result

    async def generate_action_items(self, full_transcript):

        messages = eval(PromptFacade.get_prompt("action_items",
                                            meeting_transcript=full_transcript))
        
        result = await self.completion("gpt-4o",
                                        messages=messages,
                                        max_tokens=16000,
                                        output_model=ActionItemsResponse)

        return result
