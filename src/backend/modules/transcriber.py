import aiofiles
from src.backend.core.baseFacade import BaseFacade


class Transcriber(BaseFacade):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Transcriber, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        super().__init__()

    async def transcribe(self, webm_file: str, return_segments: bool = False, language: str = None) -> str:
        self.logger.info(f"Transcribing file: {webm_file}")

        async with aiofiles.open(webm_file, "rb") as f:
            data = await f.read()

        try:
            response = await self.audio_completion(webm_file, data, return_segments, language)

            self.logger.info(f"========== GROQ TRANSCRIPTION ==========")
            self.logger.info(f"File: {webm_file}")
            self.logger.info(f"Response: {response}")
            self.logger.info(f"=======================================")

            return response

        except Exception as e:
            self.logger.error(f"Groq transcription error: {e}")
            return ""
