import os
import subprocess
from glob import glob
import json
import time
from pydub import AudioSegment
import tempfile
import math
# from src.backend.llm.transcriber import Transcriber
from src.backend.modules.transcriber import Transcriber
from src.backend.core.baseFacade import BaseFacade
from src.backend.db.dbFacade import DBFacade
from src.backend.models.db_models import MeetUpdate
from src.backend.modules.meetingAnalizer import MeetingAnalizer

class TranscriptManager(BaseFacade):
    def __init__(self):
        super().__init__()
        self.transcriber = Transcriber()
        self.db = DBFacade()
        self.paths = None # this as well
        self.full_transcript_buffer = None # What to do with this (musn't be a singleton)
        self.MAX_CHUNK_DURATION_SEC = 290
        self.CHUNK_EXTENSION = ".webm"
        self.meeting_analizer = MeetingAnalizer()
        self.audio_start_time = None

    def set_paths(self, paths):
        self.paths = paths

    def reset_transcript_buffer(self):
        self.full_transcript_buffer = []

    def get_transcript(self):
        return "\n".join(self.full_transcript_buffer)

    def merge_speaker_ranges(self, speaker_ranges):

        if not speaker_ranges:
            return []

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
            time = entry.get("time_raw")
            speakers = entry.get("speakers", {})

            if time is None:
                continue

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

    def find_active_speaker(self, seg_start, seg_end, speaker_ranges):
        TOLERANCE_MS = 150
        best_speaker = "Unknown"
        best_overlap = 0

        for r in speaker_ranges:
            if r["start_ms"] is None or r["end_ms"] is None:
                continue
            r_start = r["start_ms"] - TOLERANCE_MS
            r_end = r["end_ms"] + TOLERANCE_MS

            overlap = max(0, min(seg_end, r_end) - max(seg_start, r_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = r["speaker"]

        return best_speaker


    async def transcribe_chunk(self, webm_path, timestamp, chunk_start_time, language):
        self.logger.info(f" Transcribing: {webm_path}")
        try:
            if not self.audio_start_time:
                self.audio_start_time = chunk_start_time # set up the start time of the recording (wrong)
            elif chunk_start_time - self.audio_start_time > 50_000:
                print(f"The difference is bigger than 30 seconds:\nChunk_str_time = {chunk_start_time}\naudio_str_time = {self.audio_start_time}")
                self.audio_start_time = chunk_start_time

            result = await self.transcriber.transcribe(webm_path, return_segments=True, language=language)
            text_lines = []

            speaker_meta_path = os.path.join(self.paths["transcripts"],
                                f"chunk_{timestamp}_speakers.json")
            with open(speaker_meta_path, "r", encoding="utf-8") as f:
                speaker_events = json.load(f)

            speaker_ranges = self.get_speaker_ranges(speaker_events)
            self.logger.info(f"Speaker ranges are: {speaker_ranges}")

            if not speaker_ranges:
                self.logger.info("No active speakers in this chunk; skipping transcript append.")
                return

            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    self.logger.error("Could not parse response from Whisper as JSON")
                    return
            
            seg_starting_point = int((chunk_start_time - self.audio_start_time) // 1000)

            for seg in result["segments"]:
                seg_abs_start = chunk_start_time + seg["start"] * 1000
                seg_abs_end = chunk_start_time + seg["end"] * 1000
                seg_rel_start = seg_starting_point + seg["start"]
                seg_rel_end = seg_starting_point + seg["end"]
                speaker = self.find_active_speaker(seg_abs_start, seg_abs_end, speaker_ranges)
                if speaker:
                    start_h = int(seg_rel_start // 3600)
                    start_m = int((seg_rel_start % 3600) // 60)
                    start_s = int(seg_rel_start % 60)

                    end_h = int(seg_rel_end // 3600)
                    end_m = int((seg_rel_end % 3600) // 60)
                    end_s = int(seg_rel_end % 60)
                    text_lines.append(f"({start_h:02d}:{start_m:02d}:{start_s:02d}-{end_h:02d}:{end_m:02d}:{end_s:02d}) {speaker}: {seg['text'].strip()}")

            full_text = "\n".join(text_lines)
            self.logger.info(f"The transcript is: {full_text}")

            self.full_transcript_buffer.extend(text_lines)
            # TODO: add slm for improving chunks quality

        except Exception as e:
            self.logger.error(f"Transcription error: {e}")

    async def transcribe_and_save_full_recording(self, webm_path, language, meet_id, participants):
        if not webm_path or not os.path.exists(webm_path):
            self.logger.error("❌ Nothing to transcribe: audio path is empty or file doesn't exist")
            return

        self.logger.info("Inside transcribe_and_save_full_recording before try-except")

        try:
            self.logger.info("Inside try-except")
            audio = AudioSegment.from_file(webm_path)
            duration_sec = len(audio) / 1000
            self.logger.info(f"Full audio length: {duration_sec:.2f} seconds")

            num_chunks = math.ceil(duration_sec / self.MAX_CHUNK_DURATION_SEC)
            self.logger.info(f"Splitting into {num_chunks} chunks (≤ {self.MAX_CHUNK_DURATION_SEC} sec each)")

            all_text = []

            for i in range(num_chunks):
                start_ms = max(i * self.MAX_CHUNK_DURATION_SEC * 1000 - 1000, 0)
                end_ms = min((i + 1) * self.MAX_CHUNK_DURATION_SEC * 1000 + 1000, len(audio))
                chunk = audio[start_ms:end_ms]

                with tempfile.NamedTemporaryFile(suffix=self.CHUNK_EXTENSION, delete=False) as tmp_file:
                    chunk.export(tmp_file.name, format="webm")
                    chunk_path = tmp_file.name

                try:
                    self.logger.info(f"🧠 Transcribing chunk {i+1}/{num_chunks}")
                    result = await self.transcriber.transcribe(chunk_path, language=language)
                    if result:
                        all_text.append(result.strip())
                    else:
                        self.logger.warning(f"⚠️ Empty result for chunk {i+1}")
                except Exception as e:
                    self.logger.error(f"❌ Error transcribing chunk {i+1}: {e}")

                os.remove(chunk_path)

            full_transcript_raw = "\n".join(all_text)

            # Save the full transcript
            file_path = os.path.join(self.paths["full"], "full_transcript_from_full_audio.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_transcript_raw)

            self.logger.info(f"✅ Full transcript saved to: {file_path}")

            full_transcript = await self.transcriber.match_transcript_speakers("\n".join(self.full_transcript_buffer), full_transcript_raw)
            full_transcript_text = "\n".join([f"{segment.speaker}: {segment.text}" for segment in full_transcript])
            self.logger.info(f"The full transcript returned from llm call is: {full_transcript_text}")

            overview = await self.meeting_analizer.generate_overview(full_transcript_text)
            overview = overview.overview
            summary_and_tags = await self.meeting_analizer.summarize(full_transcript_text)
            summary = summary_and_tags.summary
            tags = summary_and_tags.tags
            notes = await self.meeting_analizer.generate_notes(full_transcript_text)
            notes = notes.notes
            action_items = await self.meeting_analizer.generate_action_items(full_transcript_text)
            action_items = action_items.action_items
            self.logger.info(f"The summary is: {summary}\nThe overview is: {overview}\nThe tags are: {tags}\nThe notes are: {notes}\nThe action_items are: {action_items}")
            
            await self.db.update_meet(meet_id, MeetUpdate(
                transcript=full_transcript_text, 
                overview="\n".join(overview),
                summary=summary,
                duration=math.ceil(duration_sec),
                tags=",".join(tags),
                action_items=action_items,
                participants=participants,
                notes=notes))
            
            full_transcript_path = os.path.join(self.paths["full"], "full_final_transcript.txt")
            
            with open(full_transcript_path, "w", encoding="utf-8") as f:
                f.write(full_transcript_text)
            
            self.reset_transcript_buffer()

        except Exception as e:
            self.logger.error(f"❌ Failed to process full recording: {e}")


    def save_full_transcript(self):
        if not self.full_transcript_buffer:
            self.logger.error("❌ Nothing to save: transcript buffer is empty")
            return

        file_path = os.path.join(self.paths["full"], "full_transcript.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.full_transcript_buffer))

        self.logger.info(f"📝 Full transcript saved to: {file_path}")

    def save_full(self):

        self.save_full_transcript()
        output_file = self._merge_audio()
        return output_file

    def _save_transcript(self):
        file_path = os.path.join(self.paths["full"], "full_transcript.txt")
        transcript_files = sorted(glob(os.path.join(self.paths["transcripts"], "chunk_*.txt")))

        with open(file_path, "w", encoding="utf-8") as outfile:
            for file in transcript_files:
                with open(file, "r", encoding="utf-8") as infile:
                    outfile.write(infile.read() + "\t")
        self.logger.info(f" Full transcript saved: {file_path}")

    def _merge_audio(self):
        webm_files = sorted(glob(os.path.join(self.paths["audio"], "chunk_*.webm")))
        valid_files = [f for f in webm_files if os.path.getsize(f) > 1024]
        self.logger.info(f"The number of webm files is: {len(webm_files)}")
        self.logger.info(f"The number of valid files is: {len(valid_files)}")
        
        if not valid_files:
            self.logger.error("❌ No valid audio chunks for merging")
            return None

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
            self.logger.info(f" Full audio saved: {output_file}")
            return output_file
        except subprocess.CalledProcessError as e:
            self.logger.error("❌ FFmpeg merge error:", e)
            return None


