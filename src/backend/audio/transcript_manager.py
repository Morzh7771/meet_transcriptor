import os
import subprocess
from glob import glob
import json
import time
from pydub import AudioSegment
import tempfile
import math
from src.backend.llm.transcriber import Transcriber
from src.backend.utils.logger import CustomLog
from pathlib import Path

log = CustomLog()

class TranscriptManager:
    def __init__(self):
        self.transcriber = Transcriber()
        self.paths = None
        self.full_transcript_buffer = None
        # Whisper може трпнскрибувати за раз аудіо довжиною до 5 хв (300 секунд)
        # Беремо з запасом 290 секунд + по 2 секунди до і після для
        # обходу проблеми з обрубаними словами
        self.MAX_CHUNK_DURATION_SEC = 290
        self.CHUNK_EXTENSION = ".webm"

    def set_paths(self, paths):
        self.paths = paths

    def reset_transcript_buffer(self):
        self.full_transcript_buffer = []

    # async def transcribe_chunk(self, webm_path, timestamp):
    #     log.info(f" Transcribing: {webm_path}")
    #     try:
    #         text = (await self.transcriber.transcribe(webm_path)).strip()
    #         log.info(f"▶  {text or '<empty>'}")

    #         if text:
    #             file_path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}.txt")
    #             with open(file_path, "w", encoding="utf-8") as f:
    #                 f.write(text)
    #             log.info(f" Transcript saved: {file_path}")
    #     except Exception as e:
    #         log.error(f"❌ Transcription error: {e}")

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


    async def transcribe_chunk(self, webm_path, timestamp, chunk_index):
        log.info(f" Transcribing: {webm_path}")
        # log.info(f"Current time in transcribe_chunk is: {time.time()}")
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
                seg_abs_start = 10000 * chunk_index + seg["start"] * 1000
                seg_abs_end = 10000 * chunk_index + seg["end"] * 1000
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

    async def transcribe_and_save_full_recording(self, webm_path):
        if not webm_path or not os.path.exists(webm_path):
            log.error("❌ Nothing to transcribe: audio path is empty or file doesn't exist")
            return

        try:
            audio = AudioSegment.from_file(webm_path)
            duration_sec = len(audio) / 1000
            log.info(f"Full audio length: {duration_sec:.2f} seconds")

            num_chunks = math.ceil(duration_sec / self.MAX_CHUNK_DURATION_SEC)
            log.info(f"Splitting into {num_chunks} chunks (≤ {self.MAX_CHUNK_DURATION_SEC} sec each)")

            all_text = []

            for i in range(num_chunks):
                start_ms = max(i * self.MAX_CHUNK_DURATION_SEC * 1000 - 1000, 0)
                end_ms = min((i + 1) * self.MAX_CHUNK_DURATION_SEC * 1000 + 1000, len(audio))
                chunk = audio[start_ms:end_ms]

                with tempfile.NamedTemporaryFile(suffix=self.CHUNK_EXTENSION, delete=False) as tmp_file:
                    chunk.export(tmp_file.name, format="webm")
                    chunk_path = tmp_file.name

                try:
                    log.info(f"🧠 Transcribing chunk {i+1}/{num_chunks}")
                    result = await self.transcriber.transcribe(chunk_path, language="uk")
                    if result:
                        all_text.append(result.strip())
                    else:
                        log.warning(f"⚠️ Empty result for chunk {i+1}")
                except Exception as e:
                    log.error(f"❌ Error transcribing chunk {i+1}: {e}")

                os.remove(chunk_path)

            full_transcript_raw = "\n".join(all_text)

            # 4. Save the full transcript
            file_path = os.path.join(self.paths["full"], "full_transcript_from_full_audio.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_transcript_raw)

            log.info(f"✅ Full transcript saved to: {file_path}")

            # UNCOMMENT !!!!!!!!!
            # full_transcript = self.transcriber.match_transcript_speakers("\n".join(self.full_transcript_buffer), full_transcript_raw)

            # full_transcript_path = os.path.join(self.paths["full"], "full_final_transcript.txt")
            # with open(full_transcript_path, "w", encoding="utf-8") as f:
            #     f.write(full_transcript)
            
            self.reset_transcript_buffer()

        except Exception as e:
            log.error(f"❌ Failed to process full recording: {e}")

        # file_path = os.path.join(self.paths["full"], "full_transcript_afterwards.txt")
        # with open(file_path, "w", encoding="utf-8") as f:
        #     f.write(result)

        # log.info(f"📝 Full transcript afterwards saved to: {file_path}")

        # real_time_path = os.path.join(self.paths["full"], "full_transcript.txt")

    def save_full_transcript(self):
        if not self.full_transcript_buffer:
            log.error("❌ Nothing to save: transcript buffer is empty")
            return

        file_path = os.path.join(self.paths["full"], "full_transcript.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.full_transcript_buffer))

        log.info(f"📝 Full transcript saved to: {file_path}")

    def save_full(self):
        # self._save_transcript()
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
        log.info(f" Full transcript saved: {file_path}")

    def _merge_audio(self) -> str:
        """
        Сшивает все chunk_*.webm в full_audio.webm.
        Возвращает путь к итоговому файлу или '' при ошибке.
        """

        # ⏳ небольшая пауза перед началом работы
        time.sleep(5)

        # 1️⃣  Собираем чанк-файлы
        audio_dir = Path(self.paths["audio"])
        session_dir = Path(self.paths["full"])
        session_dir.mkdir(parents=True, exist_ok=True)

        webm_files = sorted(audio_dir.glob("chunk_*.webm"))
        log.info("Found chunks: %s", webm_files)

        valid_files = [f for f in webm_files if f.stat().st_size > 1_024]
        if not valid_files:
            log.error("❌ No valid audio chunks for merging")
            return ""

        # 2️⃣  Создаём concat_list.txt (абсолютные пути в posix-формате)
        concat_file = session_dir / "concat_list.txt"
        with concat_file.open("w", encoding="utf-8") as f:
            for p in valid_files:
                f.write(f"file '{p.resolve().as_posix()}'\n")

        output_file = session_dir / "full_audio.webm"
        log.info("Concatenating %d files into %s", len(valid_files), output_file)

        # 3️⃣  Функция-обёртка для запуска FFmpeg
        def _run_ffmpeg(cmd: list[str], desc: str) -> bool:
            try:
                subprocess.run(
                    cmd, check=True, cwd=session_dir,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                log.info("✅ %s succeeded", desc)
                return True
            except subprocess.CalledProcessError as e:
                log.error("❌ %s failed (code %s):\n%s",
                        desc, e.returncode, e.stderr.strip())
                return False

        base_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(concat_file)
        ]

        # ▶️ Попытка №1 — без перекодирования
        if _run_ffmpeg(base_cmd + ["-c", "copy", str(output_file)],
                    "FFmpeg merge (-c copy)"):
            return str(output_file)

        # ▶️ Попытка №2 — перекодируем в Opus
        if _run_ffmpeg(base_cmd + ["-c:a", "libopus", str(output_file)],
                    "FFmpeg merge (re-encode)"):
            return str(output_file)

        # Если обе попытки не удались — бросаем исключение
        raise RuntimeError("FFmpeg merge failed after re-encode")

