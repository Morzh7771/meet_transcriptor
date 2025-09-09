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
        self.unique_speakers = set()

    def set_paths(self, paths):
        self.paths = paths

    def add_event(self, data):
        event = {
            "time_raw": data["time"], 
            "speakers": data["speakers"]
        }
        self.events.append(event)
        self.buffer.append(event)
        
        if isinstance(data["speakers"], dict):
            for speaker_name in data["speakers"].keys():
                if speaker_name: 
                    self.unique_speakers.add(speaker_name)

    def get_unique_speakers(self):
        return list(self.unique_speakers)

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
        self.logger.info(f"Speaker timeline saved: {file_path}")
        
        speakers_file_path = os.path.join(self.paths["full"], "unique_speakers.json")
        with open(speakers_file_path, "w", encoding="utf-8") as f:
            json.dump(self.get_unique_speakers(), f, ensure_ascii=False, indent=2)
        self.logger.info(f"Unique speakers saved: {speakers_file_path}")

    def reset_speakers(self):
        self.unique_speakers.clear()
        self.logger.info("Unique speakers list reset")