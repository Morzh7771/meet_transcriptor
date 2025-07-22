import os
import json
import time
import tempfile
import asyncio
import websockets
from src.backend.llm.transcriber import Transcriber

CLUSTER_SIG = b"\x1F\x43\xB6\x75"  # WebM Cluster ID

class AudioServer:
    def __init__(self):
        self.transcriber = Transcriber()
        self.header = None
        self.transcript: list[str] = []
        self.output_file = None
        self.connection_closed = asyncio.Event()
        self.buf = bytearray()
        self.t0 = time.time()

    def extract_header_and_trim(self, data: bytes):
        pos = data.find(CLUSTER_SIG)
        if pos != -1:
            return data[:pos], data[pos:]
        return None, None

    async def transcribe_chunk(self, webm_path: str):
        print(f"🎙 Sending chunk to Whisper: {webm_path}")
        try:
            text = self.transcriber.transcribe(webm_path)
            self.transcript.append(text)
            print("🧠 Whisper result:", text.strip()[:100] or "<пустой>")
        except Exception as e:
            print("❌ Whisper error:", e)

    async def handler(self, ws):
        print("🔌 Connection received. Recording and tracking started...")
        os.makedirs("recordings", exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d_%H-%M")
        self.output_file = f"recordings/meet_audio_{timestamp}.webm"
        if os.path.exists(self.output_file):
            os.remove(self.output_file)

        with open(self.output_file, "wb") as full_audio:
            try:
                async for message in ws:
                    if isinstance(message, bytes):
                        full_audio.write(message)
                        self.buf += message
                        print(f"🎙️ Audio chunk received: {len(message)} bytes")

                        if time.time() - self.t0 >= 10:
                            print(f"🧱 Collected chunk size: {len(self.buf)} bytes")

                            if self.header is None:
                                hdr, trimmed = self.extract_header_and_trim(self.buf)
                                with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                                    f.write(self.buf)
                                    path = f.name
                                if hdr:
                                    self.header = hdr
                                    print("📥 HEADER extracted")
                                else:
                                    print("⚠️ WARNING: HEADER not found in first chunk")
                                asyncio.create_task(self.transcribe_chunk(path))
                            else:
                                hdr, trimmed = self.extract_header_and_trim(self.buf)
                                with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                                    f.write(self.header)
                                    if trimmed:
                                        f.write(trimmed)
                                        print("📤 Using trimmed data")
                                    else:
                                        f.write(self.buf)
                                        print("⚠️ No cluster SIG — using full buffer")
                                    path = f.name
                                asyncio.create_task(self.transcribe_chunk(path))

                            self.buf.clear()
                            self.t0 = time.time()

                    elif isinstance(message, str):
                        try:
                            data = json.loads(message)
                            try:
                                timestamp = float(data.get("time", time.time()))
                                ts = time.strftime('%H:%M:%S', time.localtime(timestamp))
                            except (ValueError, TypeError):
                                ts = "??:??:??"
                            speakers = data.get("speakers", {})
                            print(f"🗣️ {ts} | Speaking: " +
                                ", ".join(f"{k}: {'🎤' if v else '—'}" for k, v in speakers.items()))
                        except json.JSONDecodeError:
                            print("⚠️ Invalid JSON message received:", message)
                    else:
                        print("⚠️ Unknown message type")
            except websockets.exceptions.ConnectionClosed:
                print("🔌 WebSocket client disconnected.")
            finally:
                self.connection_closed.set()

    async def start(self,ws_port):
        server = await websockets.serve(self.handler, "localhost", ws_port)
        print(f"📡 WebSocket listening at ws://localhost:{ws_port}")
        await self.connection_closed.wait()
        server.close()
        await server.wait_closed()
        print("✅ Recording finished. File saved:", self.output_file)

