"""Real-time transcript: Whisper chunks → text → callback to send to extension."""
import os
import json
import time
from src.backend.modules.transcriber import Transcriber
from src.backend.core.base_facade import BaseFacade
from src.backend.audio.speaker_resolver import SpeakerResolver


class TranscriptManager(BaseFacade):
    def __init__(self):
        super().__init__()
        self.transcriber = Transcriber()
        self.speaker_resolver = SpeakerResolver()
        self.paths = None
        self.full_transcript_buffer = []
        self.audio_start_time = None
        self.transcript_callback = None
        self.violation_callback = None

    def set_transcript_callback(self, callback):
        """Called with (text: str, segments: list[dict]) to send transcript to frontend."""
        self.transcript_callback = callback

    def set_violation_callback(self, callback):
        self.violation_callback = callback

    def set_paths(self, paths):
        self.paths = paths

    def reset_transcript_buffer(self):
        self.full_transcript_buffer = []
        self.audio_start_time = None

    @staticmethod
    def _cap_first(s: str) -> str:
        """Capitalize first character of segment text for readable transcript."""
        if not s:
            return s
        return s[0].upper() + s[1:]

    @staticmethod
    def _merge_consecutive_speaker_segments(segment_entries: list[dict]) -> list[dict]:
        """Merge consecutive segments with the same speaker: one time range, concatenated text."""
        if not segment_entries:
            return []
        merged = []
        current = dict(segment_entries[0])
        for seg in segment_entries[1:]:
            if seg["speaker"] == current["speaker"]:
                current["end_sec"] = seg["end_sec"]
                current["text"] = (current["text"] + " " + seg["text"]).strip()
            else:
                merged.append(current)
                current = dict(seg)
        merged.append(current)
        return merged

    async def transcribe_chunk(self, webm_path, timestamp, chunk_start_time, language):
        self.logger.info(f"Transcribing: {webm_path}")
        try:
            chunk_start_time = int(chunk_start_time)
            if self.audio_start_time is None:
                self.audio_start_time = chunk_start_time
            else:
                self.audio_start_time = min(int(self.audio_start_time), chunk_start_time)

            if not self.paths:
                self.logger.warning("transcribe_chunk: paths not set")
                return
            try:
                if os.path.getsize(webm_path) < 1024:
                    self.logger.warning("Skip: file too small")
                    return
            except OSError:
                self.logger.warning("Skip: cannot stat webm file")
                return

            raw = (language or "").strip().lower()
            lang = None if raw in ("auto", "") else raw
            self.logger.info(f"Calling Groq transcribe: lang={lang}, file_size={os.path.getsize(webm_path)}")
            result = await self.transcriber.transcribe(webm_path, return_segments=True, language=lang)
            self.logger.info(f"Groq returned: type={type(result).__name__}, truthy={bool(result)}")
            speaker_events = []
            speaker_meta_path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}_speakers.json")
            try:
                with open(speaker_meta_path, "r", encoding="utf-8") as f:
                    speaker_events = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            if isinstance(result, str):
                if not result:
                    self.logger.warning("Transcription returned empty string, skipping chunk")
                    return
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    self.logger.warning(f"Transcription result is not valid JSON: {result[:200]}")
                    return
            if not result or "segments" not in result:
                self.logger.warning(f"Transcription result has no segments: {type(result)}")
                return

            segments = sorted(result["segments"], key=lambda s: float(s.get("start", 0)))
            seg_starting_point = max(0, int((chunk_start_time - self.audio_start_time) // 1000))
            segment_entries = []
            for seg in segments:
                start_sec = float(seg.get("start", 0))
                end_sec = float(seg.get("end", start_sec))
                seg_abs_start = int(chunk_start_time + start_sec * 1000)
                seg_abs_end = int(chunk_start_time + end_sec * 1000)
                seg_rel_start = max(0, seg_starting_point + start_sec)
                seg_rel_end = max(seg_rel_start, seg_starting_point + end_sec)
                speaker = (
                    self.speaker_resolver.find_speaker_for_segment(seg_abs_start, seg_abs_end, speaker_events)
                    or "Unknown"
                )
                seg_text = (seg.get("text") or "").strip()
                segment_entries.append({
                    "start_sec": seg_rel_start,
                    "end_sec": seg_rel_end,
                    "speaker": speaker,
                    "text": seg_text,
                })

            merged = self._merge_consecutive_speaker_segments(segment_entries)
            for m in merged:
                m["text"] = self._cap_first((m["text"] or "").strip())
            text_lines = []
            saved_lines = []
            for m in merged:
                text = m["text"]
                sh = int(m["start_sec"] // 3600)
                sm = int((m["start_sec"] % 3600) // 60)
                ss = int(m["start_sec"] % 60)
                eh = int(m["end_sec"] // 3600)
                em = int((m["end_sec"] % 3600) // 60)
                es = int(m["end_sec"] % 60)
                text_lines.append(
                    f"({sh:02d}:{sm:02d}:{ss:02d}-{eh:02d}:{em:02d}:{es:02d}) {m['speaker']}: {text}"
                )
                saved_lines.append(f"{m['speaker']} - {sh:02d}:{sm:02d}:{ss:02d} - {text}")

            full_text = "\n".join(text_lines)  # (HH:MM:SS-HH:MM:SS) Speaker: text — audio markers
            saved_text = "\n".join(saved_lines)
            if saved_text:
                transcript_path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}_transcript.txt")
                try:
                    with open(transcript_path, "w", encoding="utf-8") as f:
                        f.write(saved_text)
                    self.logger.info(f"Saved transcript: {transcript_path}")
                except Exception as e:
                    self.logger.warning(f"Could not save transcript file: {e}")
            self.logger.info(f"Segments processed: {len(segments)} raw, {len(merged)} merged, text_len={len(full_text)}")
            if full_text:
                self.full_transcript_buffer.append({
                    "chunk_start_time": chunk_start_time,
                    "saved_text": full_text,
                })
                self.logger.info(f"Buffer updated, total entries: {len(self.full_transcript_buffer)}")
                if self.transcript_callback:
                    await self.transcript_callback(full_text, merged)
        except Exception as e:
            self.logger.error(f"Transcribe error: {e}", exc_info=True)

    def save_full(self, skip_file: bool = False) -> str | None:
        """Merge chunk transcripts. If skip_file=False, also save to recordings/full/."""
        if not self.full_transcript_buffer:
            self.logger.info("save_full: no transcript chunks to merge")
            return None
        try:
            sorted_chunks = sorted(
                self.full_transcript_buffer,
                key=lambda x: x["chunk_start_time"],
            )
            full_text = "\n\n".join(c["saved_text"] for c in sorted_chunks if c.get("saved_text"))
            if not skip_file and self.paths and self.paths.get("full"):
                full_dir = self.paths["full"]
                os.makedirs(full_dir, exist_ok=True)
                out_path = os.path.join(full_dir, "full_transcript.txt")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(full_text)
                self.logger.info(f"Saved full transcript: {out_path} ({len(sorted_chunks)} chunks)")
            else:
                self.logger.info(f"Built full transcript ({len(sorted_chunks)} chunks)")
            return full_text
        except Exception as e:
            self.logger.error(f"save_full failed: {e}", exc_info=True)
            return None
