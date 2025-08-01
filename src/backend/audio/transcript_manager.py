import os
import subprocess
from glob import glob
from src.backend.llm.transcriber import Transcriber
from src.backend.utils.logger import CustomLog
import json


log = CustomLog()

class TranscriptManager:
    def __init__(self):
        self.transcriber = Transcriber()
        self.paths = None
        self.full_transcript_buffer = None

    def set_paths(self, paths):
        self.paths = paths

    def reset_transcript_buffer(self):
        self.full_transcript_buffer = []

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
            log.error(f"❌ Transcription error: {e}")

    def merge_speaker_ranges(self, speaker_ranges):

        last_speaker = None
        previous_end = None
        last_start = None

        merged_speaker_ranges = []

        for entry in speaker_ranges:
            if previous_end is not None:
                if entry["speaker"] != last_speaker or entry["start_ms"] != previous_end:
                    merged_speaker_ranges.append({"speaker": last_speaker,
                                                  "start_ms": last_start, 
                                                  "end_ms": previous_end})
                    last_start = entry["start_ms"]
                    last_speaker = entry["speaker"]
            else:
                last_speaker = entry["speaker"]
                last_start = entry["start_ms"]
            previous_end = entry["end_ms"]

        merged_speaker_ranges.append({"speaker": last_speaker,
                                    "start_ms": last_start, 
                                    "end_ms": previous_end})

        return merged_speaker_ranges

    def get_speaker_ranges(self, speaker_events):
        speaker_ranges = []
        if not speaker_events:
            return speaker_ranges

        prev_time = None

        for entry in speaker_events:
            time = entry["time_raw"]
            speakers = entry["speakers"]

            if prev_time is not None:
                for speaker, active in speakers.items():
                    if active:
                        speaker_ranges.append({
                            "speaker": speaker,
                            "start_ms": prev_time,
                            "end_ms": time
                        })

            prev_time = time
        merged_speaker_ranges = self.merge_speaker_ranges(speaker_ranges)
        return merged_speaker_ranges


    # def find_active_speaker(self, seg_start, seg_end, speaker_ranges):
    #     TOLERANCE_MS = 150
    #     log.info(f"The transcript_line_range is: {seg_start} - {seg_end}")
    #     log.info("--------------------------------")
    #     for r in speaker_ranges:
    #         log.info(f"The range is: {r["start_ms"]} - {r["end_ms"]}")
    #         if r["start_ms"] + TOLERANCE_MS >= seg_start \
    #             and r["end_ms"] - TOLERANCE_MS <= seg_end:
    #             log.info("--------------------------------")
    #             return r["speaker"]
    #     log.info("--------------------------------")
    #     return "Unknown"

    def find_active_speaker(self, seg_start, seg_end, speaker_ranges):
        TOLERANCE_MS = 150
        best_speaker = "Unknown"
        best_overlap = 0

        for r in speaker_ranges:
            r_start = r["start_ms"] - TOLERANCE_MS
            r_end = r["end_ms"] + TOLERANCE_MS

            overlap = max(0, min(seg_end, r_end) - max(seg_start, r_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = r["speaker"]

        return best_speaker


    async def transcribe_chunk_full(self, webm_path, timestamp, chunk_index):
        log.info(f" Transcribing: {webm_path}")
        try:
            result = await self.transcriber.transcribe(webm_path, return_segments=True, language="uk")
            text_lines = []

            speaker_meta_path = os.path.join(self.paths["transcripts"],
                                f"chunk_{timestamp}_speakers.json")
            with open(speaker_meta_path, "r", encoding="utf-8") as f:
                speaker_events = json.load(f)

            speaker_ranges = self.get_speaker_ranges(speaker_events)
            log.info(f"Speaker ranges are: {speaker_ranges}")

            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    log.error("❌ Could not parse response from Whisper as JSON")
                    return

            for seg in result["segments"]:  # [{start, end, text}]
                log.info(f"The segment is: {seg}")
                # mid_time = 10020 * chunk_index + ((seg["start"] + seg["end"]) / 2) * 1000
                seg_abs_start = 10020 * chunk_index + seg["start"] * 1000
                seg_abs_end = 10020 * chunk_index + seg["end"] * 1000
                speaker = self.find_active_speaker(seg_abs_start, seg_abs_end, speaker_ranges)
                if speaker:
                    text_lines.append(f"{speaker}: {seg['text'].strip()}")

            full_text = "\n".join(text_lines)

            # file_path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}.txt")
            # with open(file_path, "w", encoding="utf-8") as f:
            #     f.write(full_text)

            self.full_transcript_buffer.extend(text_lines)

            log.info("Added transctipt to previous ones.")
            log.info(f" Transcript full_text: {full_text}")
        except Exception as e:
            log.error(f"❌ Transcription error: {e}")

    def save_full_transcript(self):
        if not self.full_transcript_buffer:
            log.error("❌ Nothing to save: transcript buffer is empty")
            return

        file_path = os.path.join(self.paths["full"], "full_transcript.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.full_transcript_buffer))

        log.info(f"📝 Full transcript saved to: {file_path}")

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