import os
import subprocess
from glob import glob
from src.backend.llm.transcriber import Transcriber
from src.backend.utils.logger import CustomLog

log = CustomLog()

class TranscriptManager:
    def __init__(self):
        self.transcriber = Transcriber()
        self.paths = None

    def set_paths(self, paths):
        self.paths = paths

    async def transcribe_chunk(self, webm_path, timestamp):
        log.info(f" Transcribing: {webm_path}")
        try:
            text = (await self.transcriber.transcribe(webm_path)).strip()
            log.info(f"▶  {text or '<empty>'}")

            if text:
                file_path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}.txt")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                log.info(f" Transcript saved: {file_path}")
        except Exception as e:
            log.error("❌ Transcription error:", e)

    def save_full(self):
        self._save_transcript()
        self._merge_audio()

    def _save_transcript(self):
        file_path = os.path.join(self.paths["full"], "full_transcript.txt")
        transcript_files = sorted(glob(os.path.join(self.paths["transcripts"], "chunk_*.txt")))

        with open(file_path, "w", encoding="utf-8") as outfile:
            for file in transcript_files:
                with open(file, "r", encoding="utf-8") as infile:
                    outfile.write(infile.read() + "\t")
        log.info(f" Full transcript saved: {file_path}")

    def _merge_audio(self):
        webm_files = sorted(glob(os.path.join(self.paths["audio"], "chunk_*.webm")))
        valid_files = [f for f in webm_files if os.path.getsize(f) > 1024]
        
        if not valid_files:
            log.error("❌ No valid audio chunks for merging")
            return

        concat_file = os.path.join(self.paths["full"], "concat_list.txt")
        output_file = os.path.join(self.paths["full"], "full_audio.webm")

        with open(concat_file, "w", encoding="utf-8") as f:
            for path in valid_files:
                f.write(f"file '{os.path.abspath(path)}'\n")

        try:
            subprocess.run([
                "ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_file, 
                "-c", "copy", output_file
            ], check=True)
            log.info(f" Full audio saved: {output_file}")
        except subprocess.CalledProcessError as e:
            log.error("❌ FFmpeg merge error:", e)