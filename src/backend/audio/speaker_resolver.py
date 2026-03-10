
class SpeakerResolver:
    """Maps speaker events to segments and determines who spoke in a given time range."""

    @staticmethod
    def get_speaker_ranges(speaker_events: list) -> list:
        """Build list of {speaker, start_ms, end_ms} from ordered speaker events."""
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
        return SpeakerResolver._merge_speaker_ranges(ranges)

    @staticmethod
    def _merge_speaker_ranges(ranges: list) -> list:
        """Merge consecutive ranges for the same speaker."""
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

    @staticmethod
    def find_active_speaker(seg_start: float, seg_end: float, speaker_ranges: list, tolerance_ms: int = 500) -> str:
        """Find speaker with best overlap in [seg_start, seg_end] (ms)."""
        best_speaker, best_overlap = "", 0
        for r in speaker_ranges:
            if r.get("start_ms") is None or r.get("end_ms") is None:
                continue
            start = r["start_ms"] - tolerance_ms
            end = r["end_ms"] + tolerance_ms
            overlap = max(0, min(seg_end, end) - max(seg_start, start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = r["speaker"]
        return best_speaker

    @staticmethod
    def _speaker_at_time(at_ms: float, sorted_events: list) -> str | None:
        """Who was speaking at given time (ms)? Returns name from event covering at_ms."""
        for i, e in enumerate(sorted_events):
            t = e["time_raw"]
            t_next = sorted_events[i + 1]["time_raw"] if i + 1 < len(sorted_events) else t + 60000
            if t <= at_ms < t_next:
                for name, active in (e.get("speakers") or {}).items():
                    if name and active:
                        return name
                return None
        return None

    @staticmethod
    def find_speaker_for_segment(seg_start_ms: float, seg_end_ms: float, speaker_events: list) -> str | None:
        """
        Determine who spoke in this segment by total duration of active=True in the segment.
        When two speakers have similar duration, prefer the one active at segment END.
        """
        if not speaker_events or not isinstance(speaker_events, list):
            return None
        seg_start_ms = int(seg_start_ms)
        seg_end_ms = int(seg_end_ms)
        if seg_end_ms <= seg_start_ms:
            seg_end_ms = seg_start_ms + 1
        sorted_events = sorted(
            [e for e in speaker_events if isinstance(e, dict) and e.get("time_raw") is not None],
            key=lambda e: e["time_raw"],
        )
        if not sorted_events:
            first = speaker_events[0] if speaker_events else {}
            if isinstance(first, dict):
                names = [k for k in (first.get("speakers") or {}).keys() if k]
                return names[0] if names else None
            return None
        duration_ms = {}
        for i, e in enumerate(sorted_events):
            t = e["time_raw"]
            t_next = sorted_events[i + 1]["time_raw"] if i + 1 < len(sorted_events) else seg_end_ms
            span_start = max(t, seg_start_ms)
            span_end = min(t_next, seg_end_ms)
            if span_end <= span_start:
                continue
            for name, active in (e.get("speakers") or {}).items():
                if not name or not active:
                    continue
                duration_ms[name] = duration_ms.get(name, 0) + (span_end - span_start)
        if duration_ms:
            best = max(duration_ms, key=duration_ms.get)
            best_dur = duration_ms[best]
            second_dur = max((d for name, d in duration_ms.items() if name != best), default=0)
            close_call = (best_dur - second_dur) < max(0.3 * best_dur, 400) if second_dur else False
            speaker_at_end = SpeakerResolver._speaker_at_time(seg_end_ms - 1, sorted_events)
            if close_call and speaker_at_end and speaker_at_end in duration_ms:
                return speaker_at_end
            return best
        speaker_at_end = SpeakerResolver._speaker_at_time(seg_end_ms - 1, sorted_events)
        if speaker_at_end:
            return speaker_at_end
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
