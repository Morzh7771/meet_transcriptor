from openai import AsyncOpenAI
import instructor
from groq import AsyncGroq
from pydantic import BaseModel
from src.backend.utils.configs import Config
from src.backend.utils.logger import CustomLog


class BaseFacade:

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BaseFacade, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.configs = Config.load_config()
        self.logger = CustomLog()
        self.raw_client = AsyncOpenAI(api_key=self.configs.openai.API_KEY.get_secret_value())
        self.client = instructor.from_openai(self.raw_client)
        self.groq_client = AsyncGroq(api_key=self.configs.groq.API_KEY.get_secret_value())

    async def completion(self, model: str, messages: list[dict],
                         max_tokens: int = 1000, temperature: float = 0.5, 
                         output_model: BaseModel = None) -> str:

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            response_model=output_model
        )
        return response

    async def audio_completion(self, webm_file: str,
                               data: bytes,
                               return_segments: bool = False,
                               language: str = None):
        """Transcribe audio via Groq (whisper-large-v3-turbo)."""
        kwargs = {
            "file": ("audio.webm", data),
            "model": "whisper-large-v3-turbo",
            "response_format": "verbose_json",
            "temperature": 0.0,
        }
        if language:
            kwargs["language"] = language

        transcription = await self.groq_client.audio.transcriptions.create(**kwargs)

        text = getattr(transcription, "text", None) or (transcription if isinstance(transcription, str) else "")
        segments_raw = getattr(transcription, "segments", None) or []

        if return_segments:
            segments = []
            for s in segments_raw:
                if isinstance(s, dict):
                    segments.append({"start": s.get("start", 0), "end": s.get("end", 0), "text": s.get("text", "")})
                else:
                    segments.append({"start": getattr(s, "start", 0), "end": getattr(s, "end", 0), "text": getattr(s, "text", "")})
            return {"text": text, "segments": segments}
        return text
