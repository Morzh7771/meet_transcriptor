from openai import OpenAI
from dotenv import load_dotenv
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

    def transcribe(self, webm_file: str) -> str:
        log.info(f"🎧 Sending file {webm_file} to Whisper API...")
        try:
            with open(webm_file, "rb") as f:
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
            log.info(f"✅ Received {len(response.text)} characters in transcript")
            return response.text
        except Exception as e:
            log.error(f"❌ Transcription error: {e}")
            return ""