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
        self.chunk_handler = ChunkHandler()
        self.transcript_manager = TranscriptManager()
        self.speaker_tracker = SpeakerTracker()
        self.connection_closed = asyncio.Event()
        self.websocket = None
        self.chat_bot = ChatBot()
        self.processed_messages = set()
        self.db = DBFacade()
        self.logger = CustomLog()
        self.last_restart_time = 0
        self.CHUNK_INTERVAL = 10
        self._restart_ack_received = False
        self.recording_started = False
        self.violations_ws = None
        self.client_id = None
        self.consultant_id = None
        # Event to signal that servers are ready
        self.servers_ready = asyncio.Event()

    async def handler_whisper(self, ws, user_id, meet_id, meeting_language):
        self.logger.info("Whisper WebSocket connected")
        self.websocket = ws
        
        ping_task = asyncio.create_task(self.send_ping(ws))
        chunk_processor_task = asyncio.create_task(self.chunk_processor(meeting_language))
        
        self.logger.info("Started ping and chunk processor tasks")
         
        try:
            async for message in ws:
                if isinstance(message, bytes):
                    await self._handle_audio_data(message, ws, meeting_language)
                elif isinstance(message, str):
                    await self._handle_json_message(message, meet_id)
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("Whisper WebSocket disconnected")
        except Exception as e:
            self.logger.error(f"Error in WebSocket handler: {e}")
        finally:
            self.logger.info("Cancelling ping and chunk processor tasks")
            ping_task.cancel()
            chunk_processor_task.cancel()
            with suppress(asyncio.CancelledError):
                await ping_task
                await chunk_processor_task
            self.logger.info("[FINALLY] Calling connection_closed.set()")
            self.connection_closed.set()
            self.logger.info("Connection_closed.set() closed")

    async def chunk_processor(self, meeting_language):
        """Periodically processes accumulated audio data with MediaRecorder restart"""
        self.logger.info(f"Chunk processor started, will process chunks every {self.CHUNK_INTERVAL} seconds")
        
        # Wait a bit for initial data to arrive
        await asyncio.sleep(2)
        
        # Send initial restart to ensure clean start
        if not self.recording_started and self.websocket:
            self.logger.info("Sending initial restart command to ensure clean MediaRecorder start")
            restart_command = json.dumps({
                "type": "restart_recorder",
                "timestamp": time.time() * 1000
            })
            try:
                await self.websocket.send(restart_command)
                restart_success = await self._wait_for_restart_ack()
                if restart_success:
                    # Discard any data collected before first restart
                    self.chunk_handler.discard_current_buffer()
                    self.recording_started = True
                    self.logger.info("Initial restart successful, now collecting clean data")
                else:
                    self.logger.warning("Initial restart failed, data may be corrupted")
            except Exception as e:
                self.logger.error(f"Failed to send initial restart: {e}")
        
        try:
            while not self.connection_closed.is_set():
                # Wait for interval
                await asyncio.sleep(self.CHUNK_INTERVAL)
                
                if self.connection_closed.is_set():
                    break
                
                if not self.recording_started:
                    self.logger.warning("Recording not properly started yet, skipping this cycle")
                    continue
                    
                try:
                    # Send restart command to frontend before processing chunk
                    restart_success = False
                    if self.websocket:
                        restart_command = json.dumps({
                            "type": "restart_recorder",
                            "timestamp": time.time() * 1000
                        })
                        try:
                            await self.websocket.send(restart_command)
                            self.logger.info("Sent restart command to frontend")
                            
                            # Wait for restart acknowledgment from frontend
                            restart_success = await self._wait_for_restart_ack()
                            if not restart_success:
                                self.logger.warning("Frontend restart acknowledgment timeout")
                        except Exception as e:
                            self.logger.error(f"Failed to send restart command: {e}")
                    
                    # Only process if restart was successful
                    if restart_success and self.chunk_handler.has_valid_data():
                        # Wait a bit more to ensure all final data arrives
                        await asyncio.sleep(0.5)
                        
                        webm_path, timestamp, chunk_start_time = self.chunk_handler.finalize_chunk()
                        if webm_path:
                            self.logger.info(f"Processing chunk started at: {chunk_start_time}")
                            # First save speakers, then start transcription
                            self.speaker_tracker.save_buffer(timestamp)
                            # Run processing asynchronously
                            asyncio.create_task(
                                self.transcript_manager.transcribe_chunk(
                                    webm_path, timestamp, chunk_start_time, meeting_language, self.client_id, self.consultant_id
                                )
                            )
                    elif not restart_success:
                        self.logger.warning("Skipping chunk processing due to failed restart")
                        # Discard potentially corrupted data
                        self.chunk_handler.discard_current_buffer()
                    else:
                        self.logger.info("No valid audio data to process in this cycle")
                        
                except Exception as e:
                    self.logger.error(f"Error in chunk processing cycle: {e}")
                    await asyncio.sleep(1)
                    
        except asyncio.CancelledError:
            self.logger.info("Chunk processor cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Fatal error in chunk processor: {e}")
        finally:
            self.logger.info("Chunk processor stopped")

    async def _wait_for_restart_ack(self, timeout=5.0):
        """Wait for restart acknowledgment from frontend"""
        try:
            self._restart_ack_received = False
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                if self._restart_ack_received:
                    self._restart_ack_received = False
                    self.logger.info("Received restart acknowledgment from frontend")
                    return True
                await asyncio.sleep(0.1)
                
            self.logger.warning("Timeout waiting for restart acknowledgment")
            return False
            
        except Exception as e:
            self.logger.error(f"Error waiting for restart ack: {e}")
            return False

    async def _handle_audio_data(self, data, ws, meeting_language):
        """Accumulate audio data only if recording has started properly"""
        if self.recording_started:
            self.chunk_handler.add_data(data)
        else:
            # Discard data until we have a clean start
            self.logger.info("Discarding audio data - recording not started properly yet")

    async def _handle_json_message(self, message, meet_id):
        try:
            data = json.loads(message)
            if "speakers" in data and "time" in data:
                self.speaker_tracker.add_event(data)
            elif data.get("type") == "restart_ready":
                self._restart_ack_received = True
                self.logger.info("Received restart acknowledgment from frontend")
                # Mark that the next data will be from a clean restart
                self.chunk_handler.mark_new_chunk_start()
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

                        if msg.get("massage") and msg.get("name") != "You":
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
            self.logger.info("[FINALLY] Calling connection_closed.set()")
            self.connection_closed.set()
            self.logger.info("Connection_closed.set() closed")

    async def handle_violations_ws(self, ws, meet_id):
        """
        WebSocket handler for sending violation alerts to frontend.
        Sends detailed analysis when law violations are detected.
        """
        self.logger.info("Violations WebSocket connected")
        self.violations_ws = ws

        ping_task = asyncio.create_task(self.send_ping(ws))

        try:
            async for message in ws:
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        # Handle acknowledgments or status updates from frontend if needed
                        if data.get("type") == "ack":
                            self.logger.info(f"Received acknowledgment for violation: {data.get('violation_id')}")
                    except json.JSONDecodeError:
                        self.logger.warning("Received invalid JSON in violations channel")
                        continue
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("Violations WebSocket disconnected")
        finally:
            ping_task.cancel()
            with suppress(asyncio.CancelledError):
                await ping_task
            self.logger.info("Violations WebSocket handler finished")
            self.connection_closed.set()

    async def send_violation_alert(self, violation_data: dict):
        """
        Send violation alert to frontend through WebSocket.
        
        Args:
            violation_data: Dictionary containing violation details from RouterAgent
        """
        if not self.violations_ws:
            self.logger.warning("Violations WebSocket not connected, cannot send alert")
            return

        try:
            message = {
                "type": "violation_detected",
                "timestamp": time.time() * 1000,
                "data": violation_data
            }
            await self.violations_ws.send(json.dumps(message))
            self.logger.info("Violation alert sent to frontend")
        except Exception as e:
            self.logger.error(f"Failed to send violation alert: {e}")

    async def start(self, client_id, meet_code, meeting_language, ws_port, violations_port, consultant_id):
        session_id = f"{meet_code}_{time.strftime('%Y-%m-%d_%H-%M-%S')}"
        paths = {
            "audio": os.path.join("recordings", "audio", session_id),
            "transcripts": os.path.join("recordings", "transcripts", session_id),
            "full": os.path.join("recordings", "full", session_id)
        }

        await self.db.create_tables()

        self.client_id = client_id
        self.consultant_id = consultant_id

        meet_id = await self.db.create_meet(MeetCreate(
            client_id=client_id,
            consultant_id=consultant_id,
            title="Test meet",
            date=datetime.now(),
            language=meeting_language,
            participants=[]
        ))
        
        self.logger.info(f"Meeting created successfully with meet_id: {meet_id}")

        for path in paths.values():
            os.makedirs(path, exist_ok=True)

        for component in [self.chunk_handler, self.transcript_manager, self.speaker_tracker]:
            component.set_paths(paths)

        # Pass audio_server reference to transcript_manager for violation callbacks
        self.transcript_manager.set_violation_callback(self.send_violation_alert)

        self.recording_started = False
        self.transcript_manager.reset_transcript_buffer()

        self.logger.info(f"Starting Whisper WebSocket server on port {ws_port}")
        server = await websockets.serve(
            lambda ws: self.handler_whisper(ws, client_id, meet_id, meeting_language),
            "localhost",
            ws_port
        )

        violations_server = await websockets.serve(
            lambda ws: self.handle_violations_ws(ws, meet_id),
            "localhost",
            violations_port
        )
        
        # Signal that servers are ready and listening
        self.servers_ready.set()
        self.logger.info(f"✅ WebSocket servers are ready on ports {ws_port} and {violations_port}")
        
        try:
            await self.connection_closed.wait()
            self.logger.info("Session finished")
            await self._finalize_session(meeting_language, meet_id)
        finally:
            server.close()
            await server.wait_closed()
            violations_server.close()
            await violations_server.wait_closed()
            self.logger.info("WebSocket servers closed")

    async def _finalize_session(self, meeting_language, meet_id):
        # Process any remaining data if we had a clean recording
        if self.recording_started and self.chunk_handler.has_valid_data():
            webm_path, timestamp, chunk_start_time = self.chunk_handler.finalize_chunk()
            if webm_path:
                self.logger.info(f"Processing final chunk started at: {chunk_start_time}")
                await self.transcript_manager.transcribe_chunk(webm_path, timestamp, chunk_start_time, meeting_language)
                self.speaker_tracker.save_buffer(timestamp)

        full_audio_path = self.transcript_manager.save_full()
        if not full_audio_path:
            self.logger.error("Full audio path is None - no audio was recorded or merged")
            return
            
        self.speaker_tracker.save_timeline()
        self.logger.info(f"Finished saving timeline and the full_audio_path is: {full_audio_path}")

        # Check if file exists and is valid before transcription
        if not os.path.exists(full_audio_path):
            self.logger.error(f"Full audio file does not exist: {full_audio_path}")
            return
            
        file_size = os.path.getsize(full_audio_path)
        if file_size < 1024:
            self.logger.error(f"Full audio file too small ({file_size} bytes): {full_audio_path}")
            return
        
        speakers_list = self.speaker_tracker.get_unique_speakers()
        self.logger.info(f"Collected unique speakers: {speakers_list}")
        
        self.logger.info("Starting transcription and saving it of full audio")

        await self.transcript_manager.transcribe_and_save_full_recording(
            full_audio_path, 
            meeting_language, 
            meet_id, 
            speakers_list  
        )

    async def terminate(self):
        self.logger.info("Terminating session manually")

        if self.websocket:
            try:
                await self.websocket.send("terminate")
                self.logger.info("Sent terminate message to websocket")
            except Exception as e:
                self.logger.warning(f"Could not send terminate: {e}")

            try:
                await self.websocket.close()
                self.logger.info("WebSocket closed")
            except Exception as e:
                self.logger.warning(f"Could not close websocket: {e}")
        
        if self.violations_ws:
            try:
                await self.violations_ws.send(json.dumps({"type": "terminate"}))
                self.logger.info("Sent terminate to violations websocket")
            except Exception as e:
                self.logger.warning(f"Could not send terminate to violations websocket: {e}")

            try:
                await self.violations_ws.close()
                self.logger.info("Violations websocket closed")
            except Exception as e:
                self.logger.warning(f"Could not close violations websocket: {e}")

        self.connection_closed.set()
        
    async def send_ping(self, websocket):
        while not self.connection_closed.is_set() and not websocket.close:
            try:
                await websocket.ping()
                await asyncio.sleep(60)
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break
    
    async def wait_until_ready(self, timeout=15):
        """
        Wait until WebSocket servers are ready.
        Returns True if ready, False if timeout.
        """
        try:
            await asyncio.wait_for(self.servers_ready.wait(), timeout=timeout)
            self.logger.info("Server ready signal received")
            return True
        except asyncio.TimeoutError:
            self.logger.error(f"Servers did not become ready within {timeout} seconds")
            return False