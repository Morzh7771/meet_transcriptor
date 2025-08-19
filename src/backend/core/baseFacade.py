from openai import AsyncOpenAI
import instructor
from pydantic import BaseModel
import os
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

    async def completion(self, model: str, messages: list[dict],
                         max_tokens: int = 1000, temperature: float = 0.5, 
                         output_model: BaseModel = None) -> str:

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_model=output_model
        )
        return response

    async def audio_completion(self, webm_file: str,
                               data: str,
                               return_segments: bool = False, 
                               language: str = None):
        
        arguments_dict = dict(
            model="whisper-1",
            file=(webm_file, data),
            response_format="verbose_json" if return_segments else "text"
        )

        if language:
            arguments_dict["language"] = language

        response = await self.client.audio.transcriptions.create(
            **arguments_dict
        )
        if return_segments:
            return {
                "text": response.text,
                "segments": [
                    {
                        "start": s.start,
                        "end": s.end,
                        "text": s.text
                    } for s in response.segments
                ]
            }
        return response
