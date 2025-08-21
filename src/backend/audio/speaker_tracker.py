import os
import json
from src.backend.utils.logger import CustomLog

class SpeakerTracker():
    def __init__(self):
        super().__init__()
        self.events = []
        self.buffer = []
        self.paths = None
        self.logger = CustomLog()

    def set_paths(self, paths):
        self.paths = paths

    def add_event(self, data):
        event = {
            "time_raw": data["time"],
            "speakers": data["speakers"]
        }
        self.events.append(event)
        self.buffer.append(event)

    def save_buffer(self, timestamp):
        if not self.buffer:
            return

        file_path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}_speakers.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.buffer, f, ensure_ascii=False, indent=2)
        self.logger.info(f"Speaker data saved: {file_path}")
        self.buffer.clear()

    def save_timeline(self):
        if not self.events:
            return

        file_path = os.path.join(self.paths["full"], "speaker_timeline.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.events, f, ensure_ascii=False, indent=2)
        self.logger.info(f" Speaker timeline saved: {file_path}")