import os
import json
import subprocess
from glob import glob
from src.backend.llm.transcriber import Transcriber as Whisper
from src.backend.utils.logger import CustomLog

log = CustomLog()

class TranscriptionManager:
    def __init__(self):
        self.whisper = Whisper()

    def set_paths(self, paths):
        self.paths = paths

    async def transcribe(self, webm_path, timestamp):
        log.info(f"Transcribing {webm_path}")
        
        text = await self.whisper.transcribe(webm_path)
        log.info(f"▶  {text or '<empty>'}")
        if text.strip():
            path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text.strip())
            log.info(f"Transcript saved: {path}")
        else:
            log.warning("❗ Empty transcript")

    def assemble_full(self):
        full_txt = os.path.join(self.paths["full"], "full_transcript.txt")
        with open(full_txt, "w", encoding="utf-8") as out:
            for path in sorted(glob(os.path.join(self.paths["transcripts"], "chunk_*.txt"))):
                with open(path, encoding="utf-8") as f:
                    out.write(f.read() + "\n\n")
        log.info(f"Full transcript: {full_txt}")
        self._merge_audio()

    def _merge_audio(self):
        webms = sorted(glob(os.path.join(self.paths["audio"], "chunk_*.webm")))
        valid = [f for f in webms if os.path.getsize(f) > 1024]
        if not valid:
            log.error("❌ No audio chunks to merge")
            return

        list_path = os.path.join(self.paths["full"], "concat_list.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            for path in valid:
                f.write(f"file '{os.path.abspath(path)}'\n")

        output = os.path.join(self.paths["full"], "full_audio.webm")
        try:
            subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output], check=True)
            log.info(f"Full audio saved: {output}")
        except subprocess.CalledProcessError as e:
            log.error("❌ FFmpeg merge error", e)
