from src.backend.audio.chunk_handler import ChunkHandler
from src.backend.audio.transcript_manager import TranscriptionManager
from src.backend.audio.speaker_tracker import SpeakerTracker
from src.backend.utils.logger import CustomLog
import websockets
import asyncio
import os
import time

log = CustomLog()

class AudioServer:
    def __init__(self):
        self.transcriber = TranscriptionManager()
        self.speakers = SpeakerTracker()
        self.chunks = ChunkHandler(self.transcriber, self.speakers)
        self.connection_closed = asyncio.Event()

    async def start(self, meet_code, ws_port=2033):
        self.chunks.prepare_session(meet_code)
        log.info(f"WebSocket listening on port {ws_port}")
        server = await websockets.serve(self._handler, "localhost", ws_port)

        try:
            await self.connection_closed.wait()
            await self.chunks.finalize()
        finally:
            server.close()
            await server.wait_closed()
            log.info("🛑 Server closed")

    async def _handler(self, ws):
        try:
            async for message in ws:
                if isinstance(message, bytes):
                    await self.chunks.handle_audio_chunk(message, ws)
                elif isinstance(message, str):
                    self.speakers.process_json(message)
        except websockets.exceptions.ConnectionClosed:
            log.warning("🛑 WebSocket closed")
        finally:
            self.connection_closed.set()
