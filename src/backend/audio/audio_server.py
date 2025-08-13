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
    def __init__(self, meeting_language=None):
        self.chunk_handler = ChunkHandler()
        self.transcript_manager = TranscriptManager()
        self.speaker_tracker = SpeakerTracker()
        self.connection_closed = asyncio.Event()
        self.websocket = None  # Храним единственное подключение от Puppeteer
        self.meeting_language = meeting_language

    async def handler_whisper(self, ws):
        log.info(" Whisper WebSocket connected")
        self.websocket = ws
        log.info("after definition of self.websocket")
        try:
            log.info("inside try-except")
            async for message in ws:
                #log.info("inside for message in ws")
                if isinstance(message, bytes):
                    await self._handle_audio_data(message, ws)
                elif isinstance(message, str):
                    await self._handle_json_message(message)
        except websockets.exceptions.ConnectionClosed:
            log.warning("🛑 Whisper WebSocket disconnected")
        finally:
            log.info("💡 [FINALLY] Calling connection_closed.set()")
            self.connection_closed.set()
            log.info("🛑 connection_closed.set() closed")

    async def _handle_audio_data(self, data, ws):
        self.chunk_handler.add_data(data)
        if self.chunk_handler.should_finalize():
            webm_path, timestamp, chunk_start_time = self.chunk_handler.finalize()
            if webm_path:
                log.info(f"The starting time of this chunk is: {chunk_start_time}")
                asyncio.create_task(self.transcript_manager.transcribe_chunk(webm_path, timestamp, chunk_start_time, self.meeting_language))
                self.speaker_tracker.save_buffer(timestamp)
                await ws.send("restart-stream")
                await asyncio.sleep(0.1)

    async def _handle_json_message(self, message):
        try:
            data = json.loads(message)
            if "speakers" in data and "time" in data:
                self.speaker_tracker.add_event(data)
        except json.JSONDecodeError:
            log.warning(f"⚠️ Invalid JSON message: {message}")

    async def start(self, meet_code, ws_port):
        session_id = f"{meet_code}_{time.strftime('%Y-%m-%d_%H-%M-%S')}"
        paths = {
            "audio": os.path.join("recordings", "audio", session_id),
            "transcripts": os.path.join("recordings", "transcripts", session_id),
            "full": os.path.join("recordings", "full", session_id)
        }

        for path in paths.values():
            os.makedirs(path, exist_ok=True)

        # Установим пути во все компоненты
        for component in [self.chunk_handler, self.transcript_manager, self.speaker_tracker]:
            component.set_paths(paths)
        self.transcript_manager.reset_transcript_buffer()

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
        if self.chunk_handler.has_data():
            webm_path, timestamp, chunk_start_time = self.chunk_handler.finalize()
            if webm_path:
                log.info(f"The starting time of this chunk is: {chunk_start_time}")
                await self.transcript_manager.transcribe_chunk(webm_path, timestamp, chunk_start_time, self.meeting_language)
                self.speaker_tracker.save_buffer(timestamp)

        full_audio_path = self.transcript_manager.save_full()
        self.speaker_tracker.save_timeline()
        log.info(f"Finished sacing timeline and the full_audio_path is: {full_audio_path}")

        # Whisper does the whole transcript (with the roles)
        if not os.path.exists(full_audio_path) or os.path.getsize(full_audio_path) < 1024:
            log.error(f"❌ Skipping Whisper full transcription — file not found or too small: {full_audio_path}")
            return
        log.info("Starting transcription and saving it of full audio")
        await self.transcript_manager.transcribe_and_save_full_recording(full_audio_path, self.meeting_language)

    async def terminate(self):
        log.info("🚨 Terminating session manually")

        if self.websocket:
            try:
                await self.websocket.send("terminate")
                log.info("📨 Sent 'terminate' message to websocket")
            except Exception as e:
                log.warning(f"⚠️ Could not send terminate: {e}")

            try:
                await self.websocket.close()
                log.info("✅ WebSocket closed")
            except Exception as e:
                log.warning(f"⚠️ Could not close websocket: {e}")
        else:
            log.warning("⚠️ No websocket to terminate")

        self.connection_closed.set()

