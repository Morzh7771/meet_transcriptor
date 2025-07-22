import os
from dotenv import load_dotenv
import asyncio
from src.backend.api.js_plagin_api import JsPluginApi
from src.backend.audio.audio_server import AudioServer
load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

class Facade:
    def __init__(self):

        self.email = os.getenv("EMAIL")
        self.password = os.getenv("PASSWORD")
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        self.js_plugin_api = JsPluginApi(self.email, self.password, self.backend_url)
        self.audio_server = AudioServer()

    async def run_google_meet_recording(self, meet_code: str ="jsa-vatt-ovo", duration_sec: int = 60, wsPort: int = 2033):
        print("🎬 Запуск WebSocket-сервера и подключение к JS...")
        audio_task = asyncio.create_task(self.audio_server.start(wsPort))

        # Отправка команды запуска в JS
        await self.js_plugin_api.connect(meet_code, duration_sec, wsPort)

        # Ждем завершения записи
        await self.audio_server.connection_closed.wait()
        print("🛑 Остановка записи.")
