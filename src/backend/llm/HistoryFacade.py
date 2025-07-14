from pydantic import BaseModel, Field


class HistoryUnit(BaseModel):
    role: str = Field(description="Role of the message")
    content: str = Field(description="Content of the message")




class HistoryFacade:

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = object.__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.history: dict[str, list[HistoryUnit]] = {}

    def new_chat(self, chat_id: str):
        self.history[chat_id] = [HistoryUnit(role="system", content="Hey, Larry! I am Neura, your health coach.")]

    def check_chat(self, chat_id: str):
        if chat_id not in self.history:
            return False
        else:
            return True
            
    def add_user_message(self, chat_id: str, message: str):
        if not self.check_chat(chat_id):
            self.new_chat(chat_id)
        self.history[chat_id].append(HistoryUnit(role="user", content=message))

    def add_bot_message(self, chat_id: str, message: str):
        if not self.check_chat(chat_id):
            self.new_chat(chat_id)
        self.history[chat_id].append(HistoryUnit(role="system", content=message))

    def get_history(self, chat_id: str) -> list[HistoryUnit]:
        if not self.check_chat(chat_id):
            return []
        history = self.history[chat_id]

        if history is None:
            return []

        return history

    def clear_history(self, chat_id: str):
        if not self.check_chat(chat_id):
            return
        self.history[chat_id] = []