import os
import socket
import random
import asyncio

from dotenv import load_dotenv
from src.backend.api.js_plagin_api import JsPluginApi
from src.backend.audio.audio_server import AudioServer
from src.backend.core.baseFacade import BaseFacade

load_dotenv()


class Facade(BaseFacade):
    def __init__(self):
        super().__init__()
        # TODO: move to configs
        self.email = os.getenv("EMAIL")
        self.password = os.getenv("PASSWORD")
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        self.js_plugin_api = JsPluginApi(self.email, self.password, self.backend_url)
        self.session_done = asyncio.Event()


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


    async def run_google_meet_recording_api(self, user_id: str, meet_code: str, meeting_language: str):
        """
        Start a Google Meet recording session with audio server and WebSocket connection.
        
        Args:
            meet_code (str): The Google Meet code to record
        """
        chat_port = None
        ws_port = None
        audio_server = None
        ws_task = None
        
        try:
            ws_port = await self.find_free_port()
            chat_port = await self.find_free_port()
            while chat_port == ws_port:
                chat_port = await self.find_free_port()
            self.logger.info(f"🚀 Starting parallel session for meet: {meet_code} on port {ws_port} and chat-port {chat_port}")
        
            audio_server = AudioServer()
            # Start recording session
            ws_task = asyncio.create_task(audio_server.start(user_id, meet_code, meeting_language, ws_port, chat_port))
            await asyncio.sleep(1)  # Give WebSocket time to initialize
            
            # Connect JS plugin
            await self.js_plugin_api.connect(meet_code, ws_port, chat_port)
        
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
            