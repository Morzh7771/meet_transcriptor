import os
import time
import asyncio
from src.backend.utils.logger import CustomLog

log = CustomLog()

class ChunkHandler:
    def __init__(self, transcriber, speaker_tracker):
        self.transcriber = transcriber
        self.speakers = speaker_tracker
        self.chunk_buffer = bytearray()
        self.t0 = time.time()

    def prepare_session(self, meet_code):
        timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
        self.session_id = f"{meet_code}_{timestamp}"
        base = os.path.join("recordings")
        self.paths = {
            "audio": os.path.join(base, "audio", self.session_id),
            "transcripts": os.path.join(base, "transcripts", self.session_id),
            "full": os.path.join(base, "full", self.session_id),
        }
        for path in self.paths.values():
            os.makedirs(path, exist_ok=True)
        self.transcriber.set_paths(self.paths)
        self.speakers.set_paths(self.paths)

    async def handle_audio_chunk(self, data, ws):
        self.chunk_buffer += data
        if time.time() - self.t0 < 10:
            return

        await self._save_chunk_and_transcribe(ws)
        self.chunk_buffer.clear()
        self.t0 = time.time()

    async def _save_chunk_and_transcribe(self, ws):
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        file_path = os.path.join(self.paths["audio"], f"chunk_{timestamp}.webm")
        with open(file_path, "wb") as f:
            f.write(self.chunk_buffer)
        log.info(f"Saved: {file_path}")

        asyncio.create_task(self.transcriber.transcribe(file_path, timestamp))
        self.speakers.flush_buffer(timestamp)
        if ws is not None:
            await ws.send("restart-stream")
            await asyncio.sleep(0.1)
        else:
            log.warning("WebSocket is None during finalize() — no restart sent") #

    async def finalize(self):
        if not self.chunk_buffer:
            return
        log.info("Finalizing chunk")
        await self._save_chunk_and_transcribe(ws=None)
        self.transcriber.assemble_full()
        self.speakers.save_timeline()
