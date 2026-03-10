import os
import time
from src.backend.utils.logger import CustomLog

class ChunkHandler:
    def __init__(self, chunk_duration=10):
        self.current_chunk_buffer = bytearray()
        self.finalized_chunk_buffer = bytearray()
        self.t0 = time.time()
        self.chunk_duration = chunk_duration
        self.paths = None
        self.logger = CustomLog()
        self.is_new_chunk = False
        self.chunk_valid = False
        self.finalized_chunk_start_time = self.t0

    def set_paths(self, paths):
        self.paths = paths

    def add_data(self, data):
        """Add data to current buffer"""
        self.current_chunk_buffer += data

    def mark_new_chunk_start(self):
        # Save current buffer regardless of chunk_valid flag — first call also has valid data
        if self.current_chunk_buffer:
            self.finalized_chunk_buffer = bytearray(self.current_chunk_buffer)
            self.finalized_chunk_start_time = self.t0
            self.logger.info(f"Marked {len(self.finalized_chunk_buffer)} bytes as finalized chunk data")
        else:
            self.logger.warning("mark_new_chunk_start: current_chunk_buffer is empty, nothing to finalize")
        self.current_chunk_buffer.clear()
        self.t0 = time.time()
        self.chunk_valid = True
        self.is_new_chunk = True
        self.logger.info("Marked new chunk start after MediaRecorder restart")

    def has_valid_data(self):
        return len(self.finalized_chunk_buffer) > 0 and self.chunk_valid

    def has_data(self):
        return len(self.current_chunk_buffer) > 0 or len(self.finalized_chunk_buffer) > 0

    def discard_current_buffer(self):
        discarded_size = len(self.current_chunk_buffer)
        self.current_chunk_buffer.clear()
        self.chunk_valid = False
        self.logger.warning(f"Discarded {discarded_size} bytes of potentially corrupted data")

    def finalize_chunk(self):
        if not self.finalized_chunk_buffer:
            self.logger.warning("No finalized chunk buffer to save")
            return None, None, None
        if not self.paths:
            self.logger.warning("finalize_chunk: paths not set")
            return None, None, None

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        webm_path = os.path.join(self.paths["audio"], f"chunk_{timestamp}.webm")

        with open(webm_path, "wb") as f:
            f.write(self.finalized_chunk_buffer)
        
        file_size = len(self.finalized_chunk_buffer)
        self.logger.info(f"Saved finalized audio chunk: {webm_path} ({file_size} bytes)")
        chunk_start_time = int(self.finalized_chunk_start_time * 1000)
        self.finalized_chunk_buffer.clear()
        if os.path.getsize(webm_path) < 1024:
            self.logger.error(f"Saved chunk is too small ({file_size} bytes), likely corrupted")
            return None, None, None
        
        return webm_path, timestamp, chunk_start_time

    def finalize(self):
        if self.current_chunk_buffer:
            self.finalized_chunk_buffer = bytearray(self.current_chunk_buffer)
            self.finalized_chunk_start_time = self.t0
            self.current_chunk_buffer.clear()
        return self.finalize_chunk()

    def reset_for_restart(self):
        self.current_chunk_buffer.clear()
        self.t0 = time.time()
        self.logger.info("Chunk buffer reset for MediaRecorder restart")

    def should_finalize(self):
        return time.time() - self.t0 >= self.chunk_duration