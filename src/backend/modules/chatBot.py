from src.backend.llm.historyFacade import HistoryFacade
from src.backend.llm.routerFacade import RouterAgent
from src.backend.prompts.promptFacade import PromptFacade
from src.backend.core.baseFacade import BaseFacade
from datetime import datetime, timedelta


class ChatBot(BaseFacade):
    def __init__(self):
        self.history = HistoryFacade()
        self.router = RouterAgent()
    
    async def process_message(self, meet_id, timestamp, role, message, current_transcript):

        timestamp_sec = timestamp / 1000
        dt = datetime.fromtimestamp(timestamp_sec)

        prompt_template = PromptFacade.get_prompt("chat", user_query=message, meeting_transcript=current_transcript)
        
        prompt = eval(prompt_template)

        if not await self.history.get_history(meet_id):
            await self.history.add_system_message(meet_id, datetime.now() - timedelta(minutes=1), role, prompt[0]["content"]["text"])

        await self.history.add_user_message(meet_id, dt, role, prompt[1]["content"]["text"])
        
        router_response = await self.router(await self.history.get_history(meet_id))
        await self.history.add_assistant_message(meet_id, datetime.now(), role, router_response.output)

        return router_response.output
