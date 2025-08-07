# from openai import OpenAI
# from openai import AsyncOpenAI
# from dotenv import load_dotenv
import aiofiles
import os
from src.backend.utils.logger import CustomLog
from src.backend.llm.baseFacade import BaseFacade
from src.backend.prompts.promptFacade import PromptFacade
from src.backend.llm.models import MatchSpeakersOtput

log = CustomLog()

# # Load keys from .env
# load_dotenv()

class Transcriber(BaseFacade):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Transcriber, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        super().__init__()

    async def transcribe(self, webm_file: str, return_segments: bool = False, language: str = "en") -> str:
        log.info(f" Sending file {webm_file} to Whisper API...")

        async with aiofiles.open(webm_file, 'rb') as f:
            data = await f.read()
        try:
            response = self.audio_completion(webm_file, data, return_segments, language)
            return response
        except Exception as e:
            log.error(f"❌ Whisper error: {e}")
            return ""
    
    async def match_transcript_speakers(self, real_time_transcript, afterwards_transcript):

        messages = eval(PromptFacade.get_prompt("match_speakers",
                                           real_time_transcript=real_time_transcript,
                                           post_meeting_transcript=afterwards_transcript))
    
        print(messages)
        
        result = await self.completion("gpt-4o", messages=messages, max_tokens=16000, output_model=MatchSpeakersOtput)

        return result
