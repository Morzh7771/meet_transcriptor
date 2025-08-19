from src.backend.db.dbFacade import DBFacade
from src.backend.models.db_models import *

class HistoryFacade:

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(HistoryFacade, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.chat_history = []
        self.db = DBFacade()

    async def add_user_message(self, meet_id: str, time: int, role: str, message: str):
        await self.db.create_meeting_chat_message(MeetingChatMessageCreate(
            meet_id=meet_id,
            time=time,
            role="user",
            content=message))

    async def add_assistant_message(self, meet_id: str, time: int, role: str, message: str):
        await self.db.create_meeting_chat_message(MeetingChatMessageCreate(
            meet_id=meet_id,
            time=time,
            role="assistant",
            content=message))

    async def add_system_message(self, meet_id: str, time: int, role: str, message: str):
        await self.db.create_meeting_chat_message(MeetingChatMessageCreate(
            meet_id=meet_id,
            time=time,
            role="system",
            content=message))

    async def get_history(self, meet_id: str):
        return [{"role": msg.role, "content": msg.content} for msg in await self.db.get_chat_messages_by_meet_id(meet_id)]