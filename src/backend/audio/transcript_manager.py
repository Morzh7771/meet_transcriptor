"""Real-time transcript: Whisper chunks → text → callback to send to extension."""
import os
import json
import time
from src.backend.modules.transcriber import Transcriber
from src.backend.core.baseFacade import BaseFacade


class TranscriptManager(BaseFacade):
    def __init__(self):
        super().__init__()
        self.transcriber = Transcriber()
        self.paths = None
        self.full_transcript_buffer = []  # list of {"chunk_start_time": ms, "saved_text": str} for final merge
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

    def get_speaker_ranges(self, speaker_events):
        if not speaker_events:
            return []
        ranges = []
        prev_time = None
        for entry in speaker_events:
            t = entry.get("time_raw")
            speakers = entry.get("speakers", {})
            if t is None:
                continue
            if prev_time is not None:
                for speaker, active in speakers.items():
                    if active:
                        ranges.append({"speaker": speaker, "start_ms": prev_time, "end_ms": t})
            prev_time = t
        return self._merge_speaker_ranges(ranges)

    def _merge_speaker_ranges(self, ranges):
        if not ranges:
            return []
        out = []
        last_speaker, last_start, prev_end = None, None, None
        for r in ranges:
            if prev_end is not None:
                if r["speaker"] != last_speaker or r["start_ms"] != prev_end:
                    out.append({"speaker": last_speaker, "start_ms": last_start, "end_ms": prev_end})
                    last_start = r["start_ms"]
                    last_speaker = r["speaker"]
            else:
                last_speaker, last_start = r["speaker"], r["start_ms"]
            prev_end = r["end_ms"]
        out.append({"speaker": last_speaker, "start_ms": last_start, "end_ms": prev_end})
        return out

    def find_active_speaker(self, seg_start, seg_end, speaker_ranges):
        tol = 500
        best_speaker, best_overlap = "", 0
        for r in speaker_ranges:
            if r.get("start_ms") is None or r.get("end_ms") is None:
                continue
            start = r["start_ms"] - tol
            end = r["end_ms"] + tol
            overlap = max(0, min(seg_end, end) - max(seg_start, start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = r["speaker"]
        return best_speaker

    def find_speaker_for_segment(self, seg_start_ms, seg_end_ms, speaker_events):
        """Determine who spoke in this segment by total duration of active=True in the segment.
        Normalize chunk to 0-30s, intersect with segment [seg_start_ms, seg_end_ms], sum ms per speaker
        when they had True; assign segment to the speaker with the longest total True time."""
        if not speaker_events or not isinstance(speaker_events, list):
            return None
        seg_start_ms = int(seg_start_ms)
        seg_end_ms = int(seg_end_ms)
        if seg_end_ms <= seg_start_ms:
            seg_end_ms = seg_start_ms + 1
        # Events sorted by time; we need duration each speaker was true inside [seg_start_ms, seg_end_ms]
        sorted_events = sorted(
            [e for e in speaker_events if isinstance(e, dict) and e.get("time_raw") is not None],
            key=lambda e: e["time_raw"]
        )
        if not sorted_events:
            first = speaker_events[0] if speaker_events else {}
            if isinstance(first, dict):
                names = [k for k in (first.get("speakers") or {}).keys() if k]
                return names[0] if names else None
            return None
        # Duration (ms) each speaker had True within [seg_start_ms, seg_end_ms]
        duration_ms = {}
        for i, e in enumerate(sorted_events):
            t = e["time_raw"]
            t_next = sorted_events[i + 1]["time_raw"] if i + 1 < len(sorted_events) else seg_end_ms
            # Interval [t, t_next] is when this snapshot holds; clip to segment
            span_start = max(t, seg_start_ms)
            span_end = min(t_next, seg_end_ms)
            if span_end <= span_start:
                continue
            for name, active in (e.get("speakers") or {}).items():
                if not name or not active:
                    continue
                duration_ms[name] = duration_ms.get(name, 0) + (span_end - span_start)
        if duration_ms:
            return max(duration_ms, key=duration_ms.get)
        # No one had True in segment: who had True longest in wider window
        tol_ms = 3000
        low, high = seg_start_ms - tol_ms, seg_end_ms + tol_ms
        for i, e in enumerate(sorted_events):
            if not (low <= e["time_raw"] <= high):
                continue
            t = e["time_raw"]
            t_next = sorted_events[i + 1]["time_raw"] if i + 1 < len(sorted_events) else t + 100
            span_start = max(t, low)
            span_end = min(t_next, high)
            if span_end <= span_start:
                continue
            for name, active in (e.get("speakers") or {}).items():
                if name and active:
                    duration_ms[name] = duration_ms.get(name, 0) + (span_end - span_start)
        if duration_ms:
            return max(duration_ms, key=duration_ms.get)
        first = sorted_events[0]
        names = list((first.get("speakers") or {}).keys())
        return names[0] if names else None

    async def transcribe_chunk(self, webm_path, timestamp, chunk_start_time, language):
        self.logger.info(f"Transcribing: {webm_path}")
        try:
            # Use earliest chunk start as meeting start (chunks complete in arbitrary order)
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

            # Default to Ukrainian if not specified (Groq whisper-large supports "uk")
            lang = (language or "uk").strip() or "uk"
            result = await self.transcriber.transcribe(webm_path, return_segments=True, language=lang)
            speaker_events = []
            speaker_meta_path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}_speakers.json")
            try:
                with open(speaker_meta_path, "r", encoding="utf-8") as f:
                    speaker_events = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    return
            if not result or "segments" not in result:
                return

            # Sort by start time so order is chronological within the chunk
            segments = sorted(result["segments"], key=lambda s: float(s.get("start", 0)))
            seg_starting_point = max(0, int((chunk_start_time - self.audio_start_time) // 1000))
            # For saving: "Спикер MM-SS: текст" (e.g. "Морж 00-05: что-то говорил")
            saved_lines = []
            text_lines = []
            segment_entries = []
            for seg in segments:
                start_sec = float(seg.get("start", 0))
                end_sec = float(seg.get("end", start_sec))
                seg_abs_start = int(chunk_start_time + start_sec * 1000)
                seg_abs_end = int(chunk_start_time + end_sec * 1000)
                seg_rel_start = max(0, seg_starting_point + start_sec)
                seg_rel_end = max(seg_rel_start, seg_starting_point + end_sec)
                speaker = self.find_speaker_for_segment(seg_abs_start, seg_abs_end, speaker_events) or "Unknown"
                # Saved file format: "Speaker MM-SS: text" (e.g. "Морж 00-05: что-то говорил")
                seg_text = (seg.get("text") or "").strip()
                mm, ss = int(seg_rel_start // 60), int(seg_rel_start % 60)
                saved_lines.append(f"{speaker} {mm:02d}-{ss:02d}: {seg_text}")
                # For extension: full timestamps
                sh, sm, ss = int(seg_rel_start // 3600), int((seg_rel_start % 3600) // 60), int(seg_rel_start % 60)
                eh, em, es = int(seg_rel_end // 3600), int((seg_rel_end % 3600) // 60), int(seg_rel_end % 60)
                text_lines.append(f"({sh:02d}:{sm:02d}:{ss:02d}-{eh:02d}:{em:02d}:{es:02d}) {speaker}: {seg_text}")
                segment_entries.append({
                    "start_sec": seg_rel_start,
                    "end_sec": seg_rel_end,
                    "speaker": speaker,
                    "text": seg_text,
                })

            full_text = "\n".join(text_lines)
            saved_text = "\n".join(saved_lines)
            if saved_text:
                # Save transcript chunk (30s) in format "Speaker MM-SS: text" (e.g. "Морж 00-05: что-то говорил")
                transcript_path = os.path.join(self.paths["transcripts"], f"chunk_{timestamp}_transcript.txt")
                try:
                    with open(transcript_path, "w", encoding="utf-8") as f:
                        f.write(saved_text)
                    self.logger.info(f"Saved transcript: {transcript_path}")
                except Exception as e:
                    self.logger.warning(f"Could not save transcript file: {e}")
            if full_text:
                self.full_transcript_buffer.append({
                    "chunk_start_time": chunk_start_time,
                    "saved_text": saved_text or full_text,
                })
                if self.transcript_callback:
                    await self.transcript_callback(full_text, segment_entries)
        except Exception as e:
            self.logger.error(f"Transcribe error: {e}", exc_info=True)

    def save_full(self):
        """Write full transcript (all chunks in order) to recordings/full/<session_id>/full_transcript.txt."""
        if not self.paths:
            self.logger.warning("save_full: no paths set")
            return None
        full_dir = self.paths.get("full")
        if not full_dir:
            self.logger.warning("save_full: no full path")
            return None
        if not self.full_transcript_buffer:
            self.logger.info("save_full: no transcript chunks to merge")
            return None
        try:
            os.makedirs(full_dir, exist_ok=True)
            sorted_chunks = sorted(
                self.full_transcript_buffer,
                key=lambda x: x["chunk_start_time"],
            )
            full_text = "\n\n".join(c["saved_text"] for c in sorted_chunks if c.get("saved_text"))
            out_path = os.path.join(full_dir, "full_transcript.txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            self.logger.info(f"Saved full transcript: {out_path} ({len(sorted_chunks)} chunks)")
            return out_path
        except Exception as e:
            self.logger.error(f"save_full failed: {e}", exc_info=True)
            return None
