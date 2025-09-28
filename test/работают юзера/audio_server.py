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

class AudioServer():
    def __init__(self):
        super().__init__()
        self.chunk_handler = ChunkHandler(chunk_duration=10)
        self.transcript_manager = TranscriptManager()
        self.speaker_tracker = SpeakerTracker()
        self.connection_closed = asyncio.Event()
        self.websocket = None
        self.chat_bot = ChatBot()
        self.processed_messages = set()
        self.db = DBFacade()
        self.logger = CustomLog()
        
        self.pcm_chunks_received = 0
        self.json_messages_received = 0
        self.total_pcm_bytes = 0
        self.webm_chunks_created = 0

    async def handler_whisper(self, ws, user_id, meet_id, meeting_language):
        self.logger.info("Whisper WebSocket connected for PCM streaming")
        self.websocket = ws
        
        ping_task = asyncio.create_task(self.send_ping(ws))
         
        try:
            async for message in ws:
                if isinstance(message, bytes):
                    self.pcm_chunks_received += 1
                    self.total_pcm_bytes += len(message)
                    await self._handle_audio_data(message, ws, meeting_language)
                    
                elif isinstance(message, str):
                    self.json_messages_received += 1
                    await self._handle_json_message(message, meet_id)
                    
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("Whisper WebSocket disconnected")
        except Exception as e:
            self.logger.error(f"Unexpected error in handler_whisper: {e}")
        finally:
            self.logger.info(f"Final PCM stats - Chunks: {self.pcm_chunks_received}, JSON: {self.json_messages_received}, Total bytes: {self.total_pcm_bytes}, Webm files: {self.webm_chunks_created}")
            ping_task.cancel()
            with suppress(asyncio.CancelledError):
                await ping_task
            self.connection_closed.set()

    async def _handle_audio_data(self, data, ws, meeting_language):
        """Handle incoming audio data with improved processing"""
        self.chunk_handler.add_data(data)
        if self.chunk_handler.should_finalize():
            webm_path, timestamp, chunk_start_time = self.chunk_handler.finalize()
            if webm_path:
                self.webm_chunks_created += 1
                self.logger.info(f"Created webm chunk #{self.webm_chunks_created}: {webm_path}")
                self.logger.info(f"The starting time of this chunk is: {chunk_start_time}")
                
                # Save speaker buffer before transcription
                self.speaker_tracker.save_buffer(timestamp)
                
                # Transcribe chunk with speaker information
                asyncio.create_task(self.transcript_manager.transcribe_chunk(webm_path, timestamp, chunk_start_time, meeting_language))

    async def _handle_json_message(self, message, meet_id):
        """Handle JSON messages with improved speaker data processing"""
        try:
            data = json.loads(message)
            self.logger.info(f"Received JSON message: {data}")
            
            # Handle different message types
            if data.get("type") == "init":
                # Handle initialization message
                self.logger.info("Received init message from client")
                audio_config = data.get("audio_config", {})
                if audio_config:
                    self.chunk_handler.set_audio_config(audio_config)
                
                # Send acknowledgment
                if self.websocket:
                    await self.websocket.send(json.dumps({
                        "type": "init_ack",
                        "status": "ready"
                    }))
                    
            elif "speakers" in data and "time" in data:
                # Handle speaker state updates from extension
                self.logger.info(f"Processing speaker data: {data}")
                self.speaker_tracker.add_event(data)
                
            elif data.get("type") == "ping":
                # Handle ping from client
                if self.websocket:
                    await self.websocket.send(json.dumps({
                        "type": "pong",
                        "timestamp": data.get("timestamp", time.time() * 1000)
                    }))
                    
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON message: {e}")
        except Exception as e:
            self.logger.error(f"Error handling JSON message: {e}")
    
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
                            response = await self.chat_bot.process_real_time_meet_message(
                                meet_id,
                                msg.get("raw_time", datetime.now()),
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
            self.connection_closed.set()

    async def start(self, user_id, meet_code, meeting_language, ws_port, chat_port):
        self.logger.info(f"Starting enhanced PCM AudioServer for meet_code: {meet_code}, language: {meeting_language}")
        session_id = f"{meet_code}_{time.strftime('%Y-%m-%d_%H-%M-%S')}"
        
        paths = {
            "audio": os.path.join("recordings", "audio", session_id),
            "transcripts": os.path.join("recordings", "transcripts", session_id),
            "full": os.path.join("recordings", "full", session_id)
        }

        await self.db.create_tables()

        meet_id = await self.db.create_meet(MeetCreate(
            user_id=user_id,
            meet_code=meet_code,
            title="Meeting Transcription",
            date=datetime.now(),
            language=meeting_language,
            participants=[]
        ))
        
        self.logger.info(f"Meeting created with meet_id: {meet_id}")

        for path in paths.values():
            os.makedirs(path, exist_ok=True)

        # Initialize all components with paths
        self.chunk_handler.set_paths(paths)
        self.transcript_manager.set_paths(paths)
        self.speaker_tracker.set_paths(paths)

        # Reset state for new session
        self.speaker_tracker.reset_speakers()
        self.transcript_manager.reset_transcript_buffer()
        
        # Reset counters
        self.pcm_chunks_received = 0
        self.json_messages_received = 0
        self.total_pcm_bytes = 0
        self.webm_chunks_created = 0
        
        server = await websockets.serve(
            lambda ws: self.handler_whisper(ws, user_id, meet_id, meeting_language),
            "localhost",
            ws_port
        )

        chat_server = await websockets.serve(
            lambda ws: self.handle_chat_ws(ws, meet_id),
            "localhost", chat_port
        )
        
        self.logger.info(f"AudioServer started on ports: ws={ws_port}, chat={chat_port}")
        
        try:
            await self.connection_closed.wait()
            await self._finalize_session(meeting_language, meet_id)
        finally:
            server.close()
            chat_server.close()
            await server.wait_closed()
            await chat_server.wait_closed()

    async def _finalize_session(self, meeting_language, meet_id):
        """Enhanced session finalization with proper statistics"""
        self.logger.info("Starting session finalization...")
        
        # Process any remaining audio data
        if self.chunk_handler.has_data():
            webm_path, timestamp, chunk_start_time = self.chunk_handler.finalize_remaining()
            if webm_path:
                self.webm_chunks_created += 1
                self.logger.info(f"Finalized remaining data as chunk #{self.webm_chunks_created}")
                
                # Save any remaining speaker data
                self.speaker_tracker.save_buffer(timestamp)
                
                # Transcribe the final chunk
                await self.transcript_manager.transcribe_chunk(webm_path, timestamp, chunk_start_time, meeting_language)

        # Generate full audio file by merging chunks
        full_audio_path = self.transcript_manager.save_full()
        if not full_audio_path:
            self.logger.warning("The full_audio_path is empty")
        
        # Save complete speaker timeline
        self.speaker_tracker.save_timeline()

        # Validate full audio file before final transcription
        if not os.path.exists(full_audio_path) or os.path.getsize(full_audio_path) < 1024:
            self.logger.error(f"Skipping Whisper full transcription - file not found or too small: {full_audio_path}")
            return
        
        # Get list of unique speakers from session
        speakers_list = self.speaker_tracker.get_unique_speakers()
        self.logger.info(f"Session speakers: {speakers_list}")
        
        # Final transcription with speaker matching
        await self.transcript_manager.transcribe_and_save_full_recording(
            full_audio_path, 
            meeting_language, 
            meet_id, 
            speakers_list  
        )
        
        # Log final statistics
        self.logger.info("=== SESSION FINALIZATION COMPLETE ===")
        self.logger.info(f"Total PCM chunks received: {self.pcm_chunks_received}")
        self.logger.info(f"Total JSON messages: {self.json_messages_received}")
        self.logger.info(f"Total audio bytes processed: {self.total_pcm_bytes}")
        self.logger.info(f"Total webm chunks created: {self.webm_chunks_created}")
        self.logger.info(f"Unique speakers found: {len(speakers_list)}")
        self.logger.info(f"Final audio file: {full_audio_path}")

    async def terminate(self):
        """Enhanced termination with better cleanup"""
        self.logger.info("Starting AudioServer termination...")
        
        if self.websocket:
            try:
                await self.websocket.send(json.dumps({
                    "type": "terminate",
                    "message": "Server shutting down"
                }))
                self.logger.info("Sent terminate message to main websocket")
            except Exception as e:
                self.logger.warning(f"Could not send terminate to main websocket: {e}")

            try:
                await self.websocket.close()
                self.logger.info("Closed main websocket")
            except Exception as e:
                self.logger.warning(f"Could not close main websocket: {e}")
        
        if getattr(self, "chat_ws", None):
            try:
                await self.chat_ws.send(json.dumps({
                    "type": "terminate",
                    "message": "Chat server shutting down"
                }))
                self.logger.info("Sent terminate message to chat websocket")
            except Exception as e:
                self.logger.warning(f"Could not send terminate to chat websocket: {e}")

            try:
                await self.chat_ws.close()
                self.logger.info("Closed chat websocket")
            except Exception as e:
                self.logger.warning(f"Could not close chat websocket: {e}")

        self.connection_closed.set()
        self.logger.info("AudioServer termination complete")
        
    async def send_ping(self, websocket):
        """Enhanced ping with better error handling"""
        ping_count = 0
        while not self.connection_closed.is_set() and not websocket.closed:
            try:
                await websocket.ping()
                ping_count += 1
                if ping_count % 10 == 0:  # Log every 10 pings (10 minutes)
                    self.logger.info(f"Sent {ping_count} pings to maintain connection")
                await asyncio.sleep(60)
            except websockets.exceptions.ConnectionClosed:
                self.logger.info("Connection closed during ping")
                break
            except Exception as e:
                self.logger.warning(f"Ping error: {e}")
                break