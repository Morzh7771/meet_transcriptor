"""Facade for Meet transcript flow: start/stop session, audio server, free port."""
import asyncio
from src.backend.audio.audio_server import AudioServer
from src.backend.core.base_facade import BaseFacade
from src.backend.utils.port_finder import find_free_port


class Facade(BaseFacade):
    def __init__(self):
        super().__init__()
        self._audio_servers = {}
        self._audio_servers_lock = asyncio.Lock()

    async def get_or_create_audio_server(self, meet_code: str) -> AudioServer:
        async with self._audio_servers_lock:
            if meet_code not in self._audio_servers:
                self.logger.info(f"Creating AudioServer for {meet_code}")
                self._audio_servers[meet_code] = AudioServer()
            return self._audio_servers[meet_code]

    async def remove_audio_server(self, meet_code: str):
        async with self._audio_servers_lock:
            if meet_code in self._audio_servers:
                del self._audio_servers[meet_code]
                self.logger.info(f"Removed AudioServer for {meet_code}")

    async def find_free_port(self, max_attempts: int = 1000) -> int:
        return find_free_port(max_attempts=max_attempts)

    async def run_google_meet_recording_api(
        self,
        meet_code: str,
        meeting_language: str,
        ws_port: int,
        chat_port: int,
    ):
        audio_server = await self.get_or_create_audio_server(meet_code)
        ws_task = asyncio.create_task(
            audio_server.start(meet_code, meeting_language, ws_port, chat_port)
        )
        servers_ready = await audio_server.wait_until_ready(timeout=15)
        if not servers_ready:
            raise RuntimeError(f"WebSocket servers failed to start for {meet_code}")
        await ws_task
        await self.remove_audio_server(meet_code)
