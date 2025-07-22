import os
import json
import time
import asyncio
import websockets
import subprocess
from glob import glob
from src.backend.llm.transcriber import Transcriber


class AudioServer:
    def __init__(self):
        self.transcriber = Transcriber()
        self.chunk_buffer = bytearray()
        self.t0 = time.time()
        self.connection_closed = asyncio.Event()
        self.speaker_events: list[dict] = []
        self.speaker_events_buffer: list[dict] = []
        self.current_timestamp = None

    async def transcribe_chunk(self, webm_path: str, timestamp: str):
        print(f"🎹 Sending chunk to Whisper: {webm_path}")
        try:
            text = await self.transcriber.transcribe(webm_path)
            transcript_text = text.strip()
            print("🧐 Whisper result:", transcript_text[:100] or "<пустой>")

            if transcript_text:
                transcript_path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}.txt")
                with open(transcript_path, "w", encoding="utf-8") as f:
                    f.write(transcript_text)
                print(f"📄 Saved transcript to: {transcript_path}")

        except Exception as e:
            print("❌ Whisper error:", e)

    async def handler_whisper(self, ws):
        print("🎤 Whisper WebSocket connected")
        try:
            async for message in ws:
                if isinstance(message, bytes):
                    self.chunk_buffer += message

                    if time.time() - self.t0 >= 10:
                        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                        self.current_timestamp = timestamp
                        webm_path = os.path.join(self.paths["audio"], f"chunk_{timestamp}.webm")
                        with open(webm_path, "wb") as f:
                            f.write(self.chunk_buffer)
                        print(f"📂 Saved audio chunk to: {webm_path}")

                        asyncio.create_task(self.transcribe_chunk(webm_path, timestamp))
                        await ws.send("restart-stream")
                        await asyncio.sleep(0.1)
                        if self.speaker_events_buffer:
                            speaker_file = os.path.join(
                                self.paths["transcripts"],
                                f"chunk_{timestamp}_speakers.json"
                            )
                            with open(speaker_file, "w", encoding="utf-8") as f:
                                json.dump(self.speaker_events_buffer, f, ensure_ascii=False, indent=2)
                            print(f"🗣 Speaker data saved to: {speaker_file}")
                            self.speaker_events_buffer.clear()
                        self.chunk_buffer.clear()
                        self.t0 = time.time()

                elif isinstance(message, str):
                    try:
                        data = json.loads(message)

                        # speaker chunk-by-chunk
                        if "speakers" in data and "time" in data:
                            event = {
                                "time_raw": data["time"],
                                "time_human": time.strftime('%H:%M:%S', time.localtime(data["time"] / 1000)),
                                "speakers": data["speakers"]
                            }
                            self.speaker_events.append(event)
                            self.speaker_events_buffer.append(event)

                    except json.JSONDecodeError:
                        print("⚠️ Invalid JSON message:", message)
        except websockets.exceptions.ConnectionClosed:
            print("🛑 Whisper WebSocket disconnected")
        finally:
            self.connection_closed.set()

    async def start(self, meet_code, ws_port=2033):
        self.meet_code = meet_code
        self.session_id = f"{meet_code}_{time.strftime('%Y-%m-%d_%H-%M-%S')}"
        self.paths = {
            "audio": os.path.join("recordings", "audio", self.session_id),
            "transcripts": os.path.join("recordings", "transcripts", self.session_id),
            "full": os.path.join("recordings", "full", self.session_id)
        }
        for path in self.paths.values():
            os.makedirs(path, exist_ok=True)

        print(f"🚀 Starting Whisper WebSocket server on port {ws_port}")
        server = await websockets.serve(self.handler_whisper, "localhost", ws_port)

        try:
            await self.connection_closed.wait()
            print("✅ Whisper session finished")

            await self.finalize_last_chunk()

            self.save()
        finally:
            server.close()
            await server.wait_closed()
            print("🧹 WebSocket server closed")

    async def finalize_last_chunk(self):
        """Сохраняет оставшийся буфер аудио и спикеров перед завершением"""
        if self.chunk_buffer:
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            self.current_timestamp = timestamp
            webm_path = os.path.join(self.paths["audio"], f"chunk_{timestamp}.webm")
            with open(webm_path, "wb") as f:
                f.write(self.chunk_buffer)
            print(f"📦 Final audio chunk saved: {webm_path}")

            await self.transcribe_chunk(webm_path, timestamp)

            if self.speaker_events_buffer:
                speaker_file = os.path.join(
                    self.paths["transcripts"],
                    f"chunk_{timestamp}_speakers.json"
                )
                with open(speaker_file, "w", encoding="utf-8") as f:
                    json.dump(self.speaker_events_buffer, f, ensure_ascii=False, indent=2)
                print(f"🗣 Final speaker data saved to: {speaker_file}")
                self.speaker_events_buffer.clear()

            self.chunk_buffer.clear()
    def save(self):
        os.makedirs(self.paths["full"], exist_ok=True)

        # Сборка полного транскрипта
        full_transcript_path = os.path.join(self.paths["full"], "full_transcript.txt")
        transcript_files = sorted(glob(os.path.join(self.paths["transcripts"], "chunk_*.txt")))

        with open(full_transcript_path, "w", encoding="utf-8") as outfile:
            for file in transcript_files:
                with open(file, "r", encoding="utf-8") as infile:
                    outfile.write(infile.read() + "\n\n")

        print(f"📄 Full transcript saved to: {full_transcript_path}")

        # Сборка speaker событий в один JSON
        speaker_timeline_path = os.path.join(self.paths["full"], "speaker_timeline.json")
        with open(speaker_timeline_path, "w", encoding="utf-8") as f:
            json.dump(self.speaker_events, f, ensure_ascii=False, indent=2)
        print(f"🧑‍💬 Speaker timeline saved to: {speaker_timeline_path}")

        # Сборка аудио через ffmpeg — фильтрация маленьких файлов
        concat_list_path = os.path.join(self.paths["full"], "concat_list.txt")
        webm_files = sorted(glob(os.path.join(self.paths["audio"], "chunk_*.webm")))

        valid_webms = []
        for path in webm_files:
            if os.path.getsize(path) > 1024:  # более 1 KB
                valid_webms.append(path)
            else:
                print(f"⚠️ Skipping invalid or too small chunk: {path}")

        if not valid_webms:
            print("❌ No valid audio chunks found for merging.")
            return

        with open(concat_list_path, "w", encoding="utf-8") as f:
            for path in valid_webms:
                f.write(f"file '{os.path.abspath(path)}'\n")

        output_audio_path = os.path.join(self.paths["full"], "full_audio.webm")

        try:
            subprocess.run(
                ["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c", "copy", output_audio_path],
                check=True
            )
            print(f"🔊 Full audio saved to: {output_audio_path}")
        except subprocess.CalledProcessError as e:
            print("❌ FFmpeg error while merging audio:", e)

