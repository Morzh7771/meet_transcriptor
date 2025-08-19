import os
import json
import time
import asyncio
import websockets
from src.backend.audio.chunk_handler import ChunkHandler
from src.backend.audio.transcript_manager import TranscriptManager
from src.backend.audio.speaker_tracker import SpeakerTracker
from src.backend.modules.chatBot import ChatBot
from src.backend.utils.logger import CustomLog
from src.backend.db.dbFacade import DBFacade
from src.backend.models.db_models import *
from functools import partial

log = CustomLog()

class AudioServer:
    def __init__(self):
        self.chunk_handler = ChunkHandler()
        self.transcript_manager = TranscriptManager()
        self.speaker_tracker = SpeakerTracker()
        self.connection_closed = asyncio.Event()
        self.websocket = None
        self.chat_bot = ChatBot()
        self.processed_messages = set()
        self.db = DBFacade()

    async def handler_whisper(self, ws, user_id, meet_id, meeting_language):
        log.info(" Whisper WebSocket connected")
        self.websocket = ws
        try:
            async for message in ws:
                if isinstance(message, bytes):
                    await self._handle_audio_data(message, ws, meeting_language)
                elif isinstance(message, str):
                    await self._handle_json_message(message, meet_id)
        except websockets.exceptions.ConnectionClosed:
            log.warning("Whisper WebSocket disconnected")
        finally:
            log.info("[FINALLY] Calling connection_closed.set()")
            self.connection_closed.set()
            log.info("Connection_closed.set() closed")

    async def _handle_audio_data(self, data, ws, meeting_language):
        self.chunk_handler.add_data(data)
        if self.chunk_handler.should_finalize():
            webm_path, timestamp, chunk_start_time = self.chunk_handler.finalize()
            if webm_path:
                log.info(f"The starting time of this chunk is: {chunk_start_time}")
                asyncio.create_task(self.transcript_manager.transcribe_chunk(webm_path, timestamp, chunk_start_time, meeting_language))
                self.speaker_tracker.save_buffer(timestamp)
                await ws.send("restart-stream")
                await asyncio.sleep(0.1)

    async def _handle_json_message(self, message, meet_id):
        try:
            data = json.loads(message)
            if "speakers" in data and "time" in data:
                self.speaker_tracker.add_event(data)
            
            if "chat" in data and data["chat"]:
                unseen_data = [msg for msg in data["chat"] if f"{msg['name']}_{msg['time']}_{msg['massage']}" not in self.processed_messages]
                for msg in unseen_data:
                    log.info("Processing message: msg")
                    msg_id = f"{msg['name']}_{msg['time']}_{msg['massage']}"

                    self.processed_messages.add(msg_id)

                    if msg.get("massage") and msg.get("name") != "Вы":
                        log.info(f"In audio_facade: processing message: {msg}")
                        response = await self.chat_bot.process_message(meet_id, msg.get("raw_time", datetime.now()), msg.get("name"), msg["massage"])
                        log.info(f"The response from process_message is: {response}")
                        if response and self.websocket:
                            log.info(f"Sending response")
                            await self.websocket.send(json.dumps({
                                "type": "chat_response",
                                "message": response
                            }))
        except Exception as e:
            log.error(f"Error handling message: {e}")

    async def start(self, user_id, meet_code, meeting_language, ws_port):
        session_id = f"{meet_code}_{time.strftime('%Y-%m-%d_%H-%M-%S')}"
        # TODO: save it in ak blob
        paths = {
            "audio": os.path.join("recordings", "audio", session_id),
            "transcripts": os.path.join("recordings", "transcripts", session_id),
            "full": os.path.join("recordings", "full", session_id)
        }

        # Create meeting in db
        await self.db.create_tables()

        meet_id = await self.db.create_meet(MeetCreate(
            user_id=user_id,
            title="Test meet",
            date=datetime.now(),
            language=meeting_language))
        log.info(f"The meeting is successfully created and meet_id is: {meet_id}")


        for path in paths.values():
            os.makedirs(path, exist_ok=True)

        for component in [self.chunk_handler, self.transcript_manager, self.speaker_tracker]:
            component.set_paths(paths)

        self.transcript_manager.reset_transcript_buffer()

        log.info(f" Starting Whisper WebSocket server on port {ws_port}")
        # self.chat_bot.uri = f"ws://localhost:{ws_port}"
        server = await websockets.serve(
            lambda ws: self.handler_whisper(ws, user_id, meet_id, meeting_language),
            "localhost",
            ws_port
        )

        try:
            await self.connection_closed.wait()
            log.info("✅ Whisper session finished")
            await self._finalize_session(meeting_language)
        finally:
            server.close()
            await server.wait_closed()
            log.info(" WebSocket server closed")

    async def _finalize_session(self, meeting_language):
        if self.chunk_handler.has_data():
            webm_path, timestamp, chunk_start_time = self.chunk_handler.finalize()
            if webm_path:
                log.info(f"The starting time of this chunk is: {chunk_start_time}")
                await self.transcript_manager.transcribe_chunk(webm_path, timestamp, chunk_start_time, meeting_language)
                self.speaker_tracker.save_buffer(timestamp)

        full_audio_path = self.transcript_manager.save_full()
        if not full_audio_path:
            log.info("The full_audio_path is empty!!!")
        self.speaker_tracker.save_timeline()
        log.info(f"Finished sacing timeline and the full_audio_path is: {full_audio_path}")

        # Whisper does the whole transcript (with the roles)
        if not os.path.exists(full_audio_path) or os.path.getsize(full_audio_path) < 1024:
            log.error(f"Skipping Whisper full transcription — file not found or too small: {full_audio_path}")
            return
        log.info("Starting transcription and saving it of full audio")
        await self.transcript_manager.transcribe_and_save_full_recording(full_audio_path, meeting_language)

    async def terminate(self):
        log.info("Terminating session manually")

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

