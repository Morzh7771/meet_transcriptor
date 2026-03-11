"""Base facade: config, logger, Groq client (singleton). Transcription via Groq Whisper only."""
from groq import AsyncGroq
from backend.utils.configs import Config
from backend.utils.logger import CustomLog


class BaseFacade:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BaseFacade, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.configs = Config.load_config()
        self.logger = CustomLog()
        self.groq_client = AsyncGroq(api_key=self.configs.groq.API_KEY.get_secret_value())

    async def audio_completion(
        self,
        data: bytes,
        filename: str = "audio.webm",
        return_segments: bool = False,
        language: str = None,
    ):
        """Transcribe audio via Groq Whisper. Model and prompt from config for quality."""
        kwargs = {
            "file": (filename, data),
            "model": self.configs.groq.WHISPER_MODEL.strip() or "whisper-large-v3-turbo",
            "response_format": "verbose_json",
            "temperature": 0.0,
        }
        if language:
            kwargs["language"] = language

        transcription = await self.groq_client.audio.transcriptions.create(**kwargs)

        text = getattr(transcription, "text", None) or (
            transcription if isinstance(transcription, str) else ""
        )
        segments_raw = getattr(transcription, "segments", None) or []

        if return_segments:
            segments = []
            for s in segments_raw:
                if isinstance(s, dict):
                    segments.append(
                        {"start": s.get("start", 0), "end": s.get("end", 0), "text": s.get("text", "")}
                    )
                else:
                    segments.append(
                        {
                            "start": getattr(s, "start", 0),
                            "end": getattr(s, "end", 0),
                            "text": getattr(s, "text", ""),
                        }
                    )
            return {"text": text, "segments": segments}
        return text
