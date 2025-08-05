
import os
import time
from src.backend.utils.logger import CustomLog

log = CustomLog()

class ChunkHandler:
    def __init__(self, chunk_duration=10):
        self.chunk_buffer = bytearray()
        self.t0 = time.time()
        self.chunk_duration = chunk_duration
        self.paths = None

    def set_paths(self, paths):
        self.paths = paths

    def add_data(self, data):
        self.chunk_buffer += data

    def should_finalize(self):
        should_finalize = time.time() - self.t0 >= self.chunk_duration
        return should_finalize

    def finalize(self):
        if not self.chunk_buffer:
            return None, None

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        webm_path = os.path.join(self.paths["audio"], f"chunk_{timestamp}.webm")

        with open(webm_path, "wb") as f:
            f.write(self.chunk_buffer)
        log.info(f" Saved audio chunk: {webm_path}")

        self.chunk_buffer.clear()
        self.t0 = time.time()
        return webm_path, timestamp

    def has_data(self):
        return len(self.chunk_buffer) > 0
