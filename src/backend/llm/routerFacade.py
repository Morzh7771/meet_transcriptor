from src.backend.models.llm_models import RouterResponse
from src.backend.core.baseFacade import BaseFacade

class RouterAgent(BaseFacade):

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RouterAgent, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        super().__init__()

    async def __call__(self, chat_history, model="gpt-5-2025-08-07"):

        response = await self.client.chat.completions.create(
            model = model,
            messages = chat_history,
            response_model=RouterResponse
        )

        return response
