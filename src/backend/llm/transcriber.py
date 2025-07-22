from openai import OpenAI
from openai import AsyncOpenAI
from dotenv import load_dotenv
import aiofiles
import os
from src.backend.utils.logger import CustomLog

log = CustomLog()

# Load keys from .env
load_dotenv()

class Transcriber:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is missing in .env")
        self.client = OpenAI(api_key=api_key)

    async def transcribe(self, webm_file: str) -> str:
        log.info(f"🎧 Sending file {webm_file} to Whisper API...")
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        async with aiofiles.open(webm_file, 'rb') as f:
            data = await f.read()
        try:
            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=(webm_file, data)
            )
            return response.text
        except Exception as e:
            log.error(f"❌ Whisper error: {e}")
            return ""