import os
import json
import time
import asyncio
import websockets
from src.backend.audio.chunk_handler import ChunkHandler
from src.backend.audio.transcript_manager import TranscriptManager
from src.backend.audio.speaker_tracker import SpeakerTracker
from src.backend.utils.logger import CustomLog

log = CustomLog()

class AudioServer:
    def __init__(self):
        self.chunk_handler = ChunkHandler()
        self.transcript_manager = TranscriptManager()
        self.speaker_tracker = SpeakerTracker()
        self.connection_closed = asyncio.Event()

    async def handler_whisper(self, ws):
        log.info(" Whisper WebSocket connected")
        try:
            async for message in ws:
                if isinstance(message, bytes):
                    await self._handle_audio_data(message, ws)
                elif isinstance(message, str):
                    await self._handle_json_message(message)
        except websockets.exceptions.ConnectionClosed:
            log.warning("🛑 Whisper WebSocket disconnected")
        finally:
            self.connection_closed.set()

    async def _handle_audio_data(self, data, ws):
        self.chunk_handler.add_data(data)
        if self.chunk_handler.should_finalize():
            webm_path, timestamp = self.chunk_handler.finalize()
            if webm_path:
                asyncio.create_task(self.transcript_manager.transcribe_chunk(webm_path, timestamp))
                self.speaker_tracker.save_buffer(timestamp)
                await ws.send("restart-stream")
                await asyncio.sleep(0.1)

    async def _handle_json_message(self, message):
        try:
            data = json.loads(message)
            if "speakers" in data and "time" in data:
                self.speaker_tracker.add_event(data)
        except json.JSONDecodeError:
            log.warning("⚠️ Invalid JSON message:", message)

    async def start(self, meet_code, ws_port):
        session_id = f"{meet_code}_{time.strftime('%Y-%m-%d_%H-%M-%S')}"
        paths = {
            "audio": os.path.join("recordings", "audio", session_id),
            "transcripts": os.path.join("recordings", "transcripts", session_id),
            "full": os.path.join("recordings", "full", session_id)
        }
        
        for path in paths.values():
            os.makedirs(path, exist_ok=True)

        # Initialize all components with paths
        for component in [self.chunk_handler, self.transcript_manager, self.speaker_tracker]:
            component.set_paths(paths)

        log.info(f" Starting Whisper WebSocket server on port {ws_port}")
        server = await websockets.serve(self.handler_whisper, "localhost", ws_port)

        try:
            await self.connection_closed.wait()
            log.info("✅ Whisper session finished")
            await self._finalize_session()
        finally:
            server.close()
            await server.wait_closed()
            log.info(" WebSocket server closed")

    async def _finalize_session(self):
        # Finalize last chunk if exists
        if self.chunk_handler.has_data():
            webm_path, timestamp = self.chunk_handler.finalize()
            if webm_path:
                await self.transcript_manager.transcribe_chunk(webm_path, timestamp)
                self.speaker_tracker.save_buffer(timestamp)

        # Save all outputs
        self.transcript_manager.save_full()
        self.speaker_tracker.save_timeline()