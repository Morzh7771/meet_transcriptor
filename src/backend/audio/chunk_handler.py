import os
import time
from src.backend.utils.logger import CustomLog

class ChunkHandler():
    def __init__(self, chunk_duration=10):
        super().__init__()
        self.current_chunk_buffer = bytearray()
        self.finalized_chunk_buffer = bytearray()
        self.t0 = time.time()
        self.chunk_duration = chunk_duration
        self.paths = None
        self.logger = CustomLog()
        self.is_new_chunk = False  # Track if this is start of new chunk after restart
        self.chunk_valid = False  # Track if current chunk is valid (after restart)

    def set_paths(self, paths):
        self.paths = paths

    def add_data(self, data):
        """Add data to current buffer"""
        self.current_chunk_buffer += data

    def mark_new_chunk_start(self):
        """Mark that we're starting a new chunk after MediaRecorder restart"""
        # Move current buffer to finalized if it's valid
        if self.chunk_valid and self.current_chunk_buffer:
            self.finalized_chunk_buffer = bytearray(self.current_chunk_buffer)
            self.logger.info(f"Marked {len(self.finalized_chunk_buffer)} bytes as finalized chunk data")
        
        # Reset current buffer for new chunk
        self.current_chunk_buffer.clear()
        self.t0 = time.time()
        self.chunk_valid = True
        self.is_new_chunk = True
        self.logger.info("Marked new chunk start after MediaRecorder restart")

    def has_valid_data(self):
        """Check if we have valid finalized data ready to save"""
        return len(self.finalized_chunk_buffer) > 0 and self.chunk_valid

    def has_data(self):
        """Check if we have any data (for backward compatibility)"""
        return len(self.current_chunk_buffer) > 0 or len(self.finalized_chunk_buffer) > 0

    def discard_current_buffer(self):
        """Discard current buffer (used when data might be corrupted)"""
        discarded_size = len(self.current_chunk_buffer)
        self.current_chunk_buffer.clear()
        self.chunk_valid = False
        self.logger.warning(f"Discarded {discarded_size} bytes of potentially corrupted data")

    def finalize_chunk(self):
        """Save the finalized chunk that was properly ended by MediaRecorder restart"""
        if not self.finalized_chunk_buffer:
            self.logger.warning("No finalized chunk buffer to save")
            return None, None, None

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        webm_path = os.path.join(self.paths["audio"], f"chunk_{timestamp}.webm")

        # Save the finalized buffer
        with open(webm_path, "wb") as f:
            f.write(self.finalized_chunk_buffer)
        
        file_size = len(self.finalized_chunk_buffer)
        self.logger.info(f"Saved finalized audio chunk: {webm_path} ({file_size} bytes)")

        # Calculate chunk start time in milliseconds
        chunk_start_time = int(self.t0 * 1000)
        
        # Clear the finalized buffer after saving
        self.finalized_chunk_buffer.clear()
        
        # Validate the saved file
        if os.path.getsize(webm_path) < 1024:
            self.logger.error(f"Saved chunk is too small ({file_size} bytes), likely corrupted")
            return None, None, None
        
        return webm_path, timestamp, chunk_start_time

    def finalize(self):
        """Legacy method for compatibility - try to save whatever we have"""
        # This should only be called at session end
        if self.chunk_valid and self.current_chunk_buffer:
            # If we have valid current data, treat it as finalized
            self.finalized_chunk_buffer = bytearray(self.current_chunk_buffer)
            self.current_chunk_buffer.clear()
        
        return self.finalize_chunk()

    def reset_for_restart(self):
        """Reset buffer and timer for MediaRecorder restart without saving"""
        # This method is deprecated - use mark_new_chunk_start instead
        self.current_chunk_buffer.clear()
        self.t0 = time.time()
        self.logger.info("Chunk buffer reset for MediaRecorder restart")

    def should_finalize(self):
        """Check if enough time has passed for a new chunk"""
        should_finalize = time.time() - self.t0 >= self.chunk_duration
        return should_finalize