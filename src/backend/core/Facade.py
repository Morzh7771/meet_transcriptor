import os
import socket
import random
import asyncio
from uuid import uuid4
from src.backend.api.js_plagin_api import JsPluginApi
from src.backend.audio.audio_server import AudioServer
from src.backend.core.baseFacade import BaseFacade
from src.backend.modules.chatBot import ChatBot

class Facade(BaseFacade):
    def __init__(self):
        super().__init__()
        self.email = self.configs.account.EMAIL
        self.password = self.configs.account.PASSWORD
        self.backend_url = self.configs.backend.BACKEND_URL
        self.js_plugin_api = JsPluginApi(self.email, self.password, self.backend_url)
        self.session_done = asyncio.Event()
        self.chat_bot = ChatBot()

    async def find_free_port(self, max_attempts=1000):
        tried_ports = set()
        for _ in range(max_attempts):
            port = random.randint(10000, 60000)
            if port in tried_ports:
                continue
            tried_ports.add(port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("Could not find free port")


    async def run_google_meet_recording_api(self, user_id: str, meet_code: str, meeting_language: str, ws_port:int, chat_port:int,consultant_id:str):
        """
        Start a Google Meet recording session with audio server and WebSocket connection.
        
        Args:
            meet_code (str): The Google Meet code to record
        """
        audio_server = None
        ws_task = None
        
        try:
            self.logger.info(f"🚀 Starting parallel session for meet: {meet_code} on port {ws_port} and chat-port {chat_port}")
        
            audio_server = AudioServer()
            # Start recording session
            ws_task = asyncio.create_task(audio_server.start(user_id, meet_code, meeting_language, ws_port, chat_port, consultant_id))
            await asyncio.sleep(1)  # Give WebSocket time to initialize
            
            # Connect JS plugin
            #await self.js_plugin_api.connect(meet_code, ws_port, chat_port)
        
            await ws_task

            self.logger.info(f"Session for {meet_code} complete.")
            
        except Exception as e:
            self.logger.error(f"Error in session {meet_code}: {e}")
            if ws_task and not ws_task.done():
                ws_task.cancel()
                try:
                    await ws_task
                except asyncio.CancelledError:
                    pass
        
        finally:
            self.session_done.set()
            
    async def startMessageBot(self, message: str, meetId: str, chat_id=None):
        chatID = chat_id if chat_id is not None else str(uuid4())
        result = await self.chat_bot.process_meet_questions(chatID,meetId,message)
        return chatID,result
            