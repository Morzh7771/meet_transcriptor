import os
import json
import time
import asyncio
import websockets
from contextlib import suppress
from src.backend.audio.chunk_handler import ChunkHandler
from src.backend.audio.transcript_manager import TranscriptManager
from src.backend.audio.speaker_tracker import SpeakerTracker
from src.backend.modules.chatBot import ChatBot
from src.backend.utils.logger import CustomLog
from src.backend.db.dbFacade import DBFacade
from src.backend.models.db_models import *
from src.backend.utils.logger import CustomLog

class AudioServer():
    def __init__(self):
        super().__init__()
        self.chunk_handler = ChunkHandler()
        self.transcript_manager = TranscriptManager()
        self.speaker_tracker = SpeakerTracker()
        self.connection_closed = asyncio.Event()
        self.websocket = None
        self.chat_bot = ChatBot()
        self.processed_messages = set()
        self.db = DBFacade()
        self.logger = CustomLog()

    async def handler_whisper(self, ws, user_id, meet_id, meeting_language):
        self.logger.info(" Whisper WebSocket connected")
        self.websocket = ws
        
        ping_task = asyncio.create_task(self.send_ping(ws))
         
        try:
            async for message in ws:
                if isinstance(message, bytes):
                    await self._handle_audio_data(message, ws, meeting_language)
                elif isinstance(message, str):
                    await self._handle_json_message(message, meet_id)
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("Whisper WebSocket disconnected")
        finally:
            ping_task.cancel()
            with suppress(asyncio.CancelledError):
                await ping_task
            self.logger.info("[FINALLY] Calling connection_closed.set()")
            self.connection_closed.set()
            self.logger.info("Connection_closed.set() closed")

    async def _handle_audio_data(self, data, ws, meeting_language):
        self.chunk_handler.add_data(data)
        if self.chunk_handler.should_finalize():
            webm_path, timestamp, chunk_start_time = self.chunk_handler.finalize()
            if webm_path:
                self.logger.info(f"The starting time of this chunk is: {chunk_start_time}")
                asyncio.create_task(self.transcript_manager.transcribe_chunk(webm_path, timestamp, chunk_start_time, meeting_language))
                self.speaker_tracker.save_buffer(timestamp)
                await ws.send("restart-stream")
                await asyncio.sleep(0.1)

    async def _handle_json_message(self, message, meet_id):
        try:
            data = json.loads(message)
            if "speakers" in data and "time" in data:
                self.speaker_tracker.add_event(data)
            
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
    
    async def handle_chat_ws(self, ws, meet_id):
        self.logger.info("Chat WS connected")
        self.chat_ws = ws

        ping_task = asyncio.create_task(self.send_ping(ws))

        try:
            async for message in ws:
                if not isinstance(message, str):
                    continue
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                if "chat" in data and data["chat"]:
                    unseen = [
                        msg for msg in data["chat"]
                        if f"{msg['name']}_{msg['time']}_{msg['massage']}" not in self.processed_messages
                    ]
                    for msg in unseen:
                        msg_id = f"{msg['name']}_{msg['time']}_{msg['massage']}"
                        self.processed_messages.add(msg_id)

                        if msg.get("massage") and msg.get("name") != "Вы":
                            response = await self.chat_bot.process_message(
                                meet_id,
                                msg.get("raw_time", datetime.now()),
                                msg.get("name"),
                                msg["massage"],
                                self.transcript_manager.full_transcript_buffer,
                            )
                            if response:
                                await self.chat_ws.send(json.dumps({
                                    "type": "chat_response",
                                    "message": response
                                }))
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("Chat WS disconnected")
        finally:
            ping_task.cancel()
            with suppress(asyncio.CancelledError):
                await ping_task
            self.logger.info("[FINALLY] Calling connection_closed.set()")
            self.connection_closed.set()
            self.logger.info("Connection_closed.set() closed")


    async def start(self, user_id, meet_code, meeting_language, ws_port, chat_port):
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
        
        self.logger.info(f"The meeting is successfully created and meet_id is: {meet_id}")

        for path in paths.values():
            os.makedirs(path, exist_ok=True)

        for component in [self.chunk_handler, self.transcript_manager, self.speaker_tracker]:
            component.set_paths(paths)

        self.transcript_manager.reset_transcript_buffer()

        self.logger.info(f" Starting Whisper WebSocket server on port {ws_port}")
        # self.chat_bot.uri = f"ws://localhost:{ws_port}"
        server = await websockets.serve(
            lambda ws: self.handler_whisper(ws, user_id, meet_id, meeting_language),
            "localhost",
            ws_port
        )

        chat_server = await websockets.serve(
            lambda ws: self.handle_chat_ws(ws, meet_id),
            "localhost", chat_port
        )
        
        try:
            await self.connection_closed.wait()
            self.logger.info("✅ Whisper session finished")
            await self._finalize_session(meeting_language, meet_id)
        finally:
            server.close()
            await server.wait_closed()
            self.logger.info(" WebSocket server closed")

    async def _finalize_session(self, meeting_language, meet_id):
        if self.chunk_handler.has_data():
            webm_path, timestamp, chunk_start_time = self.chunk_handler.finalize()
            if webm_path:
                self.logger.info(f"The starting time of this chunk is: {chunk_start_time}")
                await self.transcript_manager.transcribe_chunk(webm_path, timestamp, chunk_start_time, meeting_language)
                self.speaker_tracker.save_buffer(timestamp)

        full_audio_path = self.transcript_manager.save_full()
        if not full_audio_path:
            self.logger.info("The full_audio_path is empty!!!")
        self.speaker_tracker.save_timeline()
        self.logger.info(f"Finished saving timeline and the full_audio_path is: {full_audio_path}")

        # Whisper does the whole transcript (with the roles)
        if not os.path.exists(full_audio_path) or os.path.getsize(full_audio_path) < 1024:
            self.logger.error(f"Skipping Whisper full transcription — file not found or too small: {full_audio_path}")
            return
        self.logger.info("Starting transcription and saving it of full audio")
        await self.transcript_manager.transcribe_and_save_full_recording(full_audio_path, meeting_language, meet_id)

    async def terminate(self):
        self.logger.info("Terminating session manually")

        if self.websocket:
            try:
                await self.websocket.send("terminate")
                self.logger.info("📨 Sent 'terminate' message to websocket")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not send terminate: {e}")

            try:
                await self.websocket.close()
                self.logger.info("✅ WebSocket closed")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not close websocket: {e}")
        else:
            self.logger.warning("⚠️ No websocket to terminate")
        
        if getattr(self, "chat_ws", None):
            try:
                await self.chat_ws.send(json.dumps({"type": "terminate"}))
                self.logger.info("📨 Sent 'terminate' to chat websocket")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not send terminate to chat: {e}")

            try:
                await self.chat_ws.close()
                self.logger.info("✅ Chat websocket closed")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not close chat websocket: {e}")
        else:
            self.logger.warning("⚠️ No chat websocket to terminate")

        self.connection_closed.set()
        
    async def send_ping(self, websocket):
        while not self.connection_closed.is_set() and not websocket.close:
            try:
                await websocket.ping()
                await asyncio.sleep(60)
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break

