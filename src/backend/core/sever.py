import time
import os
from src.backend.utils.logger import CustomLog  
log = CustomLog()
def generate_paths():
    os.makedirs("recordings/audio", exist_ok=True)
    os.makedirs("recordings/transcribts", exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M")
    audio_path = f"recordings/audio/meet_audio_{timestamp}.webm"
    text_path = f"recordings/transcribts/meet_transcript_{timestamp}.txt"
    return audio_path, text_path

def save_transcript(path: str, transcript: list[str]):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(transcript))
    log.info(f"📄 Transcript saved: {path}")