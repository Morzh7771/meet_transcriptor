import asyncio
from backend.core.base_facade import BaseFacade
from backend.utils.audio_preprocess import preprocess_audio_for_whisper


class Transcriber(BaseFacade):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Transcriber, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        super().__init__()

    async def transcribe(self, webm_file: str, return_segments: bool = False, language: str = None) -> str:
        self.logger.info(f"Transcribing file: {webm_file}")
        try:
            data, filename = await asyncio.to_thread(preprocess_audio_for_whisper, webm_file)
            self.logger.info(f"Preprocessed: {filename}, size={len(data)} bytes")
        except Exception as e:
            self.logger.error(f"Audio preprocessing failed: {e}", exc_info=True)
            return ""

        parts = self._split_if_needed(data, filename)
        self.logger.info(f"Parts to transcribe: {len(parts)}")

        if len(parts) == 1:
            return await self._transcribe_single(parts[0][0], parts[0][1], return_segments, language)

        all_segments = []
        all_texts = []
        time_offset = 0.0
        for idx, (part_data, part_name, part_duration) in enumerate(parts):
            self.logger.info(f"Transcribing part {idx+1}/{len(parts)}: {len(part_data)} bytes, offset={time_offset:.1f}s")
            result = await self._transcribe_single(part_data, part_name, True, language)
            if isinstance(result, dict) and result.get("segments"):
                for seg in result["segments"]:
                    seg["start"] = seg.get("start", 0) + time_offset
                    seg["end"] = seg.get("end", 0) + time_offset
                    all_segments.append(seg)
                all_texts.append(result.get("text", ""))
            elif isinstance(result, str) and result:
                all_texts.append(result)
            time_offset += part_duration

        if return_segments:
            return {"text": " ".join(all_texts), "segments": all_segments}
        return " ".join(all_texts)

    async def _transcribe_single(self, data: bytes, filename: str, return_segments: bool, language: str):
        try:
            response = await self.audio_completion(data, filename, return_segments, language)
            self.logger.info(f"Groq result: type={type(response).__name__}, "
                             f"text_len={len(response.get('text','')) if isinstance(response, dict) else len(str(response))}")
            return response
        except Exception as e:
            self.logger.error(f"Groq transcription error: {e}", exc_info=True)
            return ""

    def _split_if_needed(self, data: bytes, filename: str) -> list:
        """Split audio into <=24MB parts. Returns [(bytes, filename, duration_seconds), ...]."""
        max_bytes = 24 * 1024 * 1024
        if len(data) <= max_bytes:
            return [(data, filename, 0.0)]

        self.logger.info(f"Audio too large ({len(data)} bytes), splitting into {max_bytes}-byte parts")
        try:
            from pydub import AudioSegment
            import io
            fmt = "mp3" if filename.endswith(".mp3") else ("wav" if filename.endswith(".wav") else "webm")
            segment = AudioSegment.from_file(io.BytesIO(data), format=fmt)
            total_ms = len(segment)
            ratio = max_bytes / len(data)
            chunk_ms = int(total_ms * ratio * 0.9)
            chunk_ms = max(chunk_ms, 10_000)

            parts = []
            pos = 0
            idx = 0
            while pos < total_ms:
                end = min(pos + chunk_ms, total_ms)
                part = segment[pos:end]
                buf = io.BytesIO()
                part.export(buf, format="mp3", parameters=["-ac", "1"])
                part_bytes = buf.getvalue()
                part_name = f"part_{idx}.mp3"
                duration_sec = (end - pos) / 1000.0
                parts.append((part_bytes, part_name, duration_sec))
                self.logger.info(f"Split part {idx}: {pos/1000:.1f}s-{end/1000:.1f}s, {len(part_bytes)} bytes")
                pos = end
                idx += 1
            return parts
        except Exception as e:
            self.logger.warning(f"pydub split failed ({e}), sending raw data in chunks")
            parts = []
            for i in range(0, len(data), max_bytes):
                chunk = data[i:i + max_bytes]
                parts.append((chunk, filename, 0.0))
            return parts
