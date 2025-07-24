import os
import json
from src.backend.utils.logger import CustomLog
import time
log = CustomLog()

class SpeakerTracker:
    def __init__(self):
        self.all_events = []
        self.buffer = []

    def set_paths(self, paths):
        self.paths = paths

    def process_json(self, message: str):
        try:
            data = json.loads(message)
            if "speakers" in data and "time" in data:
                event = {
                    "time_raw": data["time"],
                    "time_human": self._to_human(data["time"]),
                    "speakers": data["speakers"]
                }
                self.all_events.append(event)
                self.buffer.append(event)
        except json.JSONDecoSdeError:
            log.warning("⚠️ Invalid JSON")

    def flush_buffer(self, timestamp):
        if not self.buffer:
            return
        path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}_speakers.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.buffer, f, ensure_ascii=False, indent=2)
        log.info(f"Speaker chunk saved: {path}")
        self.buffer.clear()

    def save_timeline(self):
        path = os.path.join(self.paths["full"], "speaker_timeline.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.all_events, f, ensure_ascii=False, indent=2)
        log.info(f"Speaker timeline saved: {path}")

    def _to_human(self, ms):
        return time.strftime('%H:%M:%S', time.localtime(ms / 1000))

