import os
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
        self.session_done = asyncio.Event()
        # self.arr = ["mmi-guyd-ibh", "cqf-zeyo-hpe", "pbe-qqpx-rxy"]
        self.arr = ["mby-wbxs-ydg"]
        self.meeting_language = "ru"

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
        raise RuntimeError("❌ Could not find free port")

    async def run_google_meet_recording(self):
        tasks = []

        for meet_code in self.arr:
            ws_port = await self.find_free_port()
            log.info(f"🚀 Starting parallel session for meet: {meet_code} on port {ws_port}")

            audio_server = AudioServer(self.meeting_language)
            # audio_server.chat_bot.uri = 

            task = asyncio.create_task(self._start_recording_session(audio_server, meet_code, ws_port))
            tasks.append(task)

        await asyncio.gather(*tasks)
        log.info("✅ All sessions completed.")

        self.session_done.set()

    async def _start_recording_session(self, audio_server: AudioServer, meet_code: str, ws_port: int):
        try:
            ws_task = asyncio.create_task(audio_server.start(meet_code, ws_port))
            await asyncio.sleep(1) 
            await self.js_plugin_api.connect(meet_code, ws_port)

            await ws_task

            log.info(f"🛑 Session for {meet_code} complete.")
        except Exception as e:
            log.error(f"❌ Error in session {meet_code}: {e}")

    async def run_google_meet_recording_api(self,meet_code):
        tasks = []

        ws_port = await self.find_free_port()
        log.info(f"🚀 Starting parallel session for meet: {meet_code} on port {ws_port}")
        audio_server = AudioServer(self.meeting_language)
        task = asyncio.create_task(self._start_recording_session(audio_server, meet_code, ws_port))
        tasks.append(task)
        await asyncio.gather(*tasks)
        log.info("✅ All sessions completed.")

        self.session_done.set()
