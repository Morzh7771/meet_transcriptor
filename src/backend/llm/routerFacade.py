import instructor
from openai import AsyncOpenAI
from src.backend.models.llm_models import RouterResponse
import os
from dotenv import load_dotenv

load_dotenv()

class RouterAgent:

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RouterAgent, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.raw_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.client = instructor.from_openai(self.raw_client)

    async def __call__(self, chat_history, model="gpt-4", temperature=0.5):

        response = await self.client.chat.completions.create(
            model = model,
            messages = chat_history,
            temperature = temperature,
            response_model=RouterResponse
        )

        return response
