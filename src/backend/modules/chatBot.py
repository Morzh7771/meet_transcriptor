from src.backend.llm.historyFacade import HistoryFacade
from src.backend.utils.logger import CustomLog
from src.backend.llm.routerFacade import RouterAgent
from src.backend.prompts.promptFacade import PromptFacade
import json

log = CustomLog()

class ChatBot:
    def __init__(self):
        self.history = HistoryFacade()
        self.router = RouterAgent()
    
    async def process_message(self, message):

        prompt_template = PromptFacade.get_prompt("chat", user_query=message)
        
        prompt = json.loads(prompt_template)

        if not self.history.get_history():
            self.history.add_system_message(prompt[0]["content"]["text"])
            
        self.history.add_user_query(prompt[1]["content"]["text"])
        
        router_response = await self.router(self.history.get_history())
        self.history.add_assistant_message(str(router_response))

        return router_response.output
