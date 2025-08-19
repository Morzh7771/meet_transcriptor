from src.backend.llm.historyFacade import HistoryFacade
from src.backend.utils.logger import CustomLog
from src.backend.llm.routerFacade import RouterAgent
from src.backend.prompts.promptFacade import PromptFacade
import json
from datetime import datetime, timedelta

log = CustomLog()

class ChatBot:
    def __init__(self):
        self.history = HistoryFacade()
        self.router = RouterAgent()
    
    async def process_message(self, meet_id, timestamp, role, message):
        log.info(f"Inside the process_message function, timestamp is: {timestamp}")

        timestamp_sec = timestamp / 1000
        log.info(f'Timestamp_sec is: {timestamp_sec}')
        dt = datetime.fromtimestamp(timestamp_sec)

        prompt_template = PromptFacade.get_prompt("chat", user_query=message)
        
        prompt = json.loads(prompt_template)

        if not await self.history.get_history(meet_id):
            log.info("Adding the system message")
            await self.history.add_system_message(meet_id, datetime.now() - timedelta(minutes=1), role, prompt[0]["content"]["text"])

        await self.history.add_user_message(meet_id, dt, role, prompt[1]["content"]["text"])
        
        router_response = await self.router(await self.history.get_history(meet_id))
        await self.history.add_assistant_message(meet_id, datetime.now(), role, router_response.output)

        return router_response.output
