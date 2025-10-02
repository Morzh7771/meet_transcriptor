from src.backend.llm.historyFacade import HistoryFacade
from src.backend.llm.routerFacade import RouterAgent
from src.backend.prompts.promptFacade import PromptFacade
from src.backend.core.baseFacade import BaseFacade
from datetime import datetime, timedelta
from src.backend.db.dbFacade import DBFacade

class ChatBot(BaseFacade):
    def __init__(self):
        self.history = HistoryFacade()
        self.router = RouterAgent()
        self.db_facade = DBFacade()
    
    async def process_real_time_meet_message(self, meet_id, timestamp, message, current_transcript):

        timestamp_sec = timestamp / 1000
        dt = datetime.fromtimestamp(timestamp_sec)

        prompt_template = PromptFacade.get_prompt("chat", user_query=message, meeting_transcript=current_transcript)
        
        prompt = eval(prompt_template)

        if not await self.history.get_history_real_time(meet_id):
            await self.history.add_system_message_real_time(meet_id, datetime.now() - timedelta(minutes=1), prompt[0]["content"]["text"])

        await self.history.add_user_message_real_time(meet_id, dt, prompt[1]["content"]["text"])
        
        router_response = await self.router(await self.history.get_history(meet_id))
        await self.history.add_assistant_message_real_time(meet_id, datetime.now(), router_response.output)

        return router_response.output
    
    
    async def process_meet_questions(self, chat_id, meet_id, message):
        dt = datetime.now()
        meet = await self.db_facade.get_meet_by_id(meet_id)

        prompt_template = PromptFacade.get_prompt("chat", user_query=message, meeting=meet)
        prompt = eval(prompt_template)

        
        if not await self.history.get_history_front(chat_id):
            await self.history.add_system_message_front(chat_id, meet_id, dt - timedelta(minutes=2), prompt[0]["content"]["text"])

        await self.history.add_user_message_front(chat_id, meet_id, dt - timedelta(minutes=1), prompt[1]["content"]["text"])
        
        router_response = await self.router.front_chat(await self.history.get_history_front(chat_id))
        await self.history.add_assistant_message_front(chat_id, meet_id, dt, router_response.output)
        return await self.history.get_history_front(chat_id)
