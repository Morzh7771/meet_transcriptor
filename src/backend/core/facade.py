import os
import subprocess
import re
import socket
import random
import asyncio

from dotenv import load_dotenv
from src.backend.api.js_plagin_api import JsPluginApi
from src.backend.audio.audio_server import AudioServer
from src.backend.utils.logger import CustomLog

load_dotenv()
log = CustomLog()

class Facade:
    def __init__(self):

        self.email = os.getenv("EMAIL")
        self.password = os.getenv("PASSWORD")
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        self.js_plugin_api = JsPluginApi(self.email, self.password, self.backend_url)
        self.audio_server = AudioServer()

    @staticmethod
    async def find_free_port(max_attempts=1000):
        tried_ports = set()

        for _ in range(max_attempts):
            port = random.randint(1, 65535)
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

    async def run_google_meet_recording(self, meet_code: str = "rgf-miyn-sbf", duration_sec: int = 30):
        log.info(" Starting WebSocket server and connecting to JS...")
        wsPort = await self.find_free_port()
        # We run start() directly so that it runs completely
        start_task = asyncio.create_task(self.audio_server.start(meet_code, wsPort))

        # We connect the JS plugin (it automatically terminates WebSocket on a timer)
        await self.js_plugin_api.connect(meet_code, duration_sec, wsPort)

        # We wait for start() to be fully processed.
        await start_task

        log.info("🛑 Recording stop complete.")
