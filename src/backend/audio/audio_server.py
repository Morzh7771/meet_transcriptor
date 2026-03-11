import os
import json
import shutil
import tempfile
import time
import asyncio
import websockets
from contextlib import suppress
from backend.audio.chunk_handler import ChunkHandler
from backend.audio.transcript_manager import TranscriptManager
from backend.audio.speaker_tracker import SpeakerTracker
from backend.utils.logger import CustomLog
from backend.services.s3_storage import S3Storage
from backend.services.slack_notifier import SlackNotifier


def is_app_mode() -> bool:
    return os.environ.get("APP_MODE") == "1"


class AudioServer:
    def __init__(self):
        self.chunk_handler = ChunkHandler()
        self.transcript_manager = TranscriptManager()
        self.speaker_tracker = SpeakerTracker()
        self.connection_closed = asyncio.Event()
        self.websocket = None
        self.logger = CustomLog()
        self.CHUNK_INTERVAL = int(os.environ.get("AUDIO_CHUNK_INTERVAL_SEC", "30"))
        self.RESTART_ACK_TIMEOUT = 10
        self._restart_ack_received = False
        self.recording_started = False
        self.violations_ws = None
        self.servers_ready = asyncio.Event()
        self._session_id = None
        self._meet_code = None
        self._slack_dm_email = None
        self._start_time: float | None = None
        self._s3 = S3Storage()
        self._slack = SlackNotifier()
        self._temp_dir = None

    async def handler_whisper(self, ws, meet_code, meeting_language):
        self.logger.info("Whisper WebSocket connected")
        self.websocket = ws
        self.recording_started = True
        self.chunk_handler.chunk_valid = True

        ping_task = asyncio.create_task(self.send_ping(ws))

        try:
            async for message in ws:
                if isinstance(message, bytes):
                    await self._handle_audio_data(message, ws, meeting_language)
                elif isinstance(message, str):
                    await self._handle_json_message(message)
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("Whisper WebSocket disconnected")
        except Exception as e:
            self.logger.error(f"Error in WebSocket handler: {e}")
        finally:
            self.logger.info("Cancelling ping task")
            ping_task.cancel()
            with suppress(asyncio.CancelledError):
                await ping_task
            self.connection_closed.set()

    async def _wait_for_restart_ack(self, timeout=None):
        """Wait for restart acknowledgment from frontend. Timeout must exceed frontend silence wait (5s) + stop time (~3s)."""
        if timeout is None:
            timeout = getattr(self, "RESTART_ACK_TIMEOUT", 10)
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
        if self.recording_started:
            self.chunk_handler.add_data(data)
        else:
            self.logger.info("Discarding audio data - recording not started properly yet")

    async def _handle_json_message(self, message):
        try:
            data = json.loads(message)
            if data.get("type") == "init":
                self.recording_started = True
                self.logger.info("Recording started (init from client), accepting audio immediately")
                if self.websocket:
                    await self.websocket.send(json.dumps({"type": "init_ack", "timestamp": time.time() * 1000}))
            elif "speakers" in data and "time" in data:
                self.speaker_tracker.add_event(data)
            elif data.get("type") == "restart_ready":
                self._restart_ack_received = True
                self.logger.info("Received restart acknowledgment from frontend")
                self.chunk_handler.mark_new_chunk_start()
            elif data.get("type") == "end":
                self.logger.info("Received 'end' from client, scheduling terminate")
                self._finalized_by_terminate = True  # prevent _finalize_session racing
                asyncio.create_task(self.terminate())
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    async def _send_transcript(self, text: str, segments: list = None):
        """Send transcript text and segments to extension over Whisper WebSocket."""
        if not self.websocket:
            return
        try:
            payload = {
                "type": "transcript",
                "text": text,
                "timestamp": time.time() * 1000,
            }
            if segments:
                payload["segments"] = segments
            await self.websocket.send(json.dumps(payload))
        except Exception as e:
            if "1005" in str(e) or "no status received" in str(e).lower():
                self.logger.info("Transcript not sent: client already disconnected")
            else:
                self.logger.error(f"Failed to send transcript: {e}")

    async def handle_chat_ws(self, ws, meet_code):
        self.logger.info("Chat WS connected")
        self.chat_ws = ws
        ping_task = asyncio.create_task(self.send_ping(ws))
        try:
            async for _ in ws:
                pass
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("Chat WS disconnected")
        finally:
            ping_task.cancel()
            with suppress(asyncio.CancelledError):
                await ping_task

    async def handle_violations_ws(self, ws, meet_code):
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

    async def send_violation_alert(self, violation_data: dict):
        """Send violation alert to frontend through WebSocket."""
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

    async def start(self, meet_code, meeting_language, ws_port, violations_port, slack_dm_email=None):
        self._start_time = time.time()
        session_id = f"{meet_code}_{time.strftime('%Y-%m-%d_%H-%M-%S')}"
        self._session_id = session_id
        self._meet_code = meet_code
        self._slack_dm_email = (slack_dm_email or "").strip() or None
        raw = (meeting_language or "").strip().lower()
        self._meeting_language = "auto" if (not raw or raw == "auto") else meeting_language.strip()

        if is_app_mode():
            self._temp_dir = tempfile.mkdtemp(prefix="meet_transcript_")
            base = self._temp_dir
            self.logger.info(f"App mode: using temp dir {base}")
        else:
            base = "recordings"
            self._temp_dir = None

        paths = {
            "audio": os.path.join(base, "audio", session_id),
            "transcripts": os.path.join(base, "transcripts", session_id),
            "full": os.path.join(base, "full", session_id),
        }

        for path in paths.values():
            os.makedirs(path, exist_ok=True)

        for component in [self.chunk_handler, self.transcript_manager, self.speaker_tracker]:
            component.set_paths(paths)

        self.transcript_manager.set_violation_callback(self.send_violation_alert)
        self.transcript_manager.set_transcript_callback(self._send_transcript)

        self.recording_started = False
        self.transcript_manager.reset_transcript_buffer()
        self._finalized_by_terminate = False

        self.logger.info(f"Starting audio WebSocket server on port {ws_port}")
        server = await websockets.serve(
            lambda ws: self.handler_whisper(ws, meet_code, meeting_language),
            "localhost",
            ws_port
        )

        violations_server = await websockets.serve(
            lambda ws: self.handle_violations_ws(ws, meet_code),
            "localhost",
            violations_port
        )
        
        self.servers_ready.set()
        self.logger.info(f"WebSocket servers ready on ports {ws_port} and {violations_port}")
        
        try:
            await self.connection_closed.wait()
            self.logger.info("Session finished")
            if not getattr(self, "_finalized_by_terminate", False):
                await self._finalize_session(meeting_language)
        finally:
            server.close()
            await server.wait_closed()
            violations_server.close()
            await violations_server.wait_closed()
            self.logger.info("WebSocket servers closed")

    async def _finalize_session(self, meeting_language):
        webm_path = None
        if self.recording_started:
            if self.chunk_handler.has_valid_data():
                webm_path, timestamp, chunk_start_time = self.chunk_handler.finalize_chunk()
                if webm_path:
                    self.speaker_tracker.save_buffer(timestamp)
                    await self.transcript_manager.transcribe_chunk(
                        webm_path, timestamp, chunk_start_time, meeting_language,
                    )
            elif self.chunk_handler.has_data():
                webm_path, timestamp, chunk_start_time = self.chunk_handler.finalize()
                if webm_path:
                    self.speaker_tracker.save_buffer(timestamp)
                    await self.transcript_manager.transcribe_chunk(
                        webm_path, timestamp, chunk_start_time, meeting_language,
                    )
        await asyncio.sleep(2)
        full_content = self.transcript_manager.save_full(skip_file=is_app_mode())
        self.logger.info("Session finalized")
        if (full_content or webm_path) and self._session_id and self._meet_code:
            await self._run_finalize_integrations(full_content, webm_path)
        self._cleanup_temp()

    def _parse_session_datetime(self):
        """From _session_id (meet_code_YYYY-MM-DD_HH-MM-SS) return (date_str, time_str)."""
        if not self._session_id:
            return "-", "-"
        parts = self._session_id.split("_")
        if len(parts) >= 3:
            date_str = parts[-2]
            time_str = parts[-1].replace("-", ":", 2)
            return date_str, time_str
        return "-", "-"

    @staticmethod
    def _format_duration(seconds: int) -> str:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h:
            return f"{h}h {m:02d}m {s:02d}s"
        if m:
            return f"{m}m {s:02d}s"
        return f"{s}s"

    async def _run_finalize_integrations(
        self, full_content: str | None, webm_path: str | None = None
    ) -> tuple[str | None, str | None]:
        """Upload transcript and audio to S3, print summary, notify Slack. Returns (transcript_url, audio_url)."""
        import datetime
        end_ts = time.time()
        date_str, start_time_str = self._parse_session_datetime()
        end_dt = datetime.datetime.fromtimestamp(end_ts)
        end_time_str = end_dt.strftime("%H:%M:%S")
        duration_sec = int(end_ts - self._start_time) if self._start_time else 0
        duration_str = self._format_duration(duration_sec)

        participants = self.speaker_tracker.get_unique_speakers()
        participants_str = ", ".join(participants) if participants else "-"

        transcript_url = None
        audio_url = None
        if self._s3.is_configured():
            self.logger.info("S3 configured, uploading...")
            if full_content:
                transcript_url = await asyncio.to_thread(
                    self._s3.upload_transcript,
                    full_content,
                    date_str,
                    self._meet_code,
                    start_time_str,
                )
                self.logger.info(f"Transcript upload result: {transcript_url}")
            else:
                self.logger.warning("No transcript content to upload")
            if webm_path:
                audio_url = await asyncio.to_thread(
                    self._s3.upload_audio,
                    webm_path,
                    date_str,
                    self._meet_code,
                    start_time_str,
                )
                self.logger.info(f"Audio upload result: {audio_url}")
            else:
                self.logger.warning("No audio path to upload")
        else:
            self.logger.warning("S3 not configured, skipping upload")

        self.logger.info(
            f"Session summary: date={date_str} start={start_time_str} end={end_time_str} "
            f"duration={duration_str} room={self._meet_code} "
            f"participants={participants_str} transcript={transcript_url or '-'} audio={audio_url or '-'}"
        )

        if self._slack.is_configured():
            await asyncio.to_thread(
                self._slack.notify_transcript_ready,
                date_str,
                start_time_str,
                self._meet_code,
                participants,
                transcript_url,
                audio_url,
                end_time_str=end_time_str,
                duration_str=duration_str,
                slack_dm_email=self._slack_dm_email,
            )
        return transcript_url, audio_url

    async def terminate(self):
        """Request full recording (restart_recorder → restart_ready), save one file, transcribe, upload to S3, close."""
        meeting_language = getattr(self, "_meeting_language", "auto")
        self.logger.info("Terminating session: request full recording then close")
        webm_path = None

        if self.websocket and self.recording_started:
            try:
                restart_command = json.dumps({"type": "restart_recorder", "timestamp": time.time() * 1000})
                await self.websocket.send(restart_command)
                self.logger.info("Sent restart_recorder to get last chunk")
                restart_ok = await self._wait_for_restart_ack(timeout=self.RESTART_ACK_TIMEOUT)
                if restart_ok and self.chunk_handler.has_valid_data():
                    await asyncio.sleep(0.5)
                    wp, timestamp, chunk_start_time = self.chunk_handler.finalize_chunk()
                    if wp:
                        webm_path = wp
                        self.speaker_tracker.save_buffer(timestamp)
                        await self.transcript_manager.transcribe_chunk(
                            wp, timestamp, chunk_start_time, meeting_language,
                        )
                        self.logger.info("Last chunk processed")
                elif self.chunk_handler.has_data():
                    wp, timestamp, chunk_start_time = self.chunk_handler.finalize()
                    if wp:
                        webm_path = wp
                        self.speaker_tracker.save_buffer(timestamp)
                        await self.transcript_manager.transcribe_chunk(
                            wp, timestamp, chunk_start_time, meeting_language,
                        )
                        self.logger.info("Last chunk (finalize) processed")
            except Exception as e:
                self.logger.warning(f"Last chunk on terminate failed: {e}")

        await asyncio.sleep(0.5)
        full_content = self.transcript_manager.save_full(skip_file=is_app_mode())
        if full_content:
            self.logger.info(f"Built full transcript (terminate), length={len(full_content)}")
        else:
            buf_len = len(self.transcript_manager.full_transcript_buffer)
            self.logger.warning(f"No transcript content after save_full, buffer_entries={buf_len}")
        transcript_url, audio_url = None, None
        if (full_content or webm_path) and self._session_id and self._meet_code:
            transcript_url, audio_url = await self._run_finalize_integrations(
                full_content, webm_path
            )
        self._finalized_by_terminate = True

        if self.websocket:
            try:
                await self.websocket.send(
                    json.dumps({
                        "type": "transcript_ready",
                        "transcript_url": transcript_url,
                        "audio_url": audio_url,
                    })
                )
                self.logger.info(f"Sent transcript_ready: transcript={transcript_url} audio={audio_url}")
            except Exception as e:
                self.logger.warning(f"Could not send transcript_ready: {e}")
            try:
                await self.websocket.send(json.dumps({"type": "terminate"}))
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
                await self.violations_ws.close()
            except Exception as e:
                self.logger.warning(f"Could not close violations websocket: {e}")

        self.connection_closed.set()
        self._cleanup_temp()

    def _cleanup_temp(self):
        if self._temp_dir and os.path.isdir(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                self.logger.info(f"Cleaned up temp dir: {self._temp_dir}")
            except Exception as e:
                self.logger.warning(f"Temp cleanup failed: {e}")
            self._temp_dir = None

    async def send_ping(self, websocket):
        while not self.connection_closed.is_set():
            try:
                await websocket.ping()
                await asyncio.sleep(60)
            except Exception:
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