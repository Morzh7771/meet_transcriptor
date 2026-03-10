"""WebM to mono 16 kHz MP3 for Whisper. Peak normalization + compressed output.
Splitting for files > 24 MB is handled by the Transcriber."""
import os
import sys
from io import BytesIO
from typing import Tuple

from src.backend.utils.logger import CustomLog

WHISPER_SAMPLE_RATE = 16000


def _setup_ffmpeg() -> None:
    """Ensure pydub can find ffmpeg/ffprobe.

    Priority:
      1. Bundled binaries next to the frozen executable (_MEIPASS).
      2. Common Homebrew locations on macOS.
      3. System PATH (default pydub behaviour).
    """
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(sys._MEIPASS)
    candidates += ["/opt/homebrew/bin", "/usr/local/bin"]

    import shutil
    for directory in candidates:
        ffmpeg = os.path.join(directory, "ffmpeg")
        ffprobe = os.path.join(directory, "ffprobe")
        if os.path.isfile(ffmpeg) and os.path.isfile(ffprobe):
            # Prepend to PATH so pydub's shutil.which finds them
            current = os.environ.get("PATH", "")
            if directory not in current:
                os.environ["PATH"] = directory + os.pathsep + current
            return


_setup_ffmpeg()


def _read_raw(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def preprocess_audio_for_whisper(webm_path: str) -> Tuple[bytes, str]:
    """Load WebM, convert to mono 16 kHz MP3 with peak-normalization."""
    logger = CustomLog()
    try:
        from pydub import AudioSegment

        segment = AudioSegment.from_file(webm_path, format="webm")
        if segment.frame_count() == 0 or len(segment) == 0:
            logger.warning("Audio preprocess: empty segment, skip")
            return _read_raw(webm_path), "audio.webm"

        segment = segment.set_channels(1)
        try:
            segment = segment.apply_gain(-segment.max_dBFS - 1.0)
        except Exception as e:
            logger.warning(f"Audio normalize skipped: {e}")
        buf = BytesIO()
        segment.export(buf, format="mp3", parameters=["-ar", str(WHISPER_SAMPLE_RATE), "-ac", "1"])
        mp3_bytes = buf.getvalue()
        logger.info(f"Audio preprocess: mono {WHISPER_SAMPLE_RATE} Hz MP3, {len(mp3_bytes)} bytes")
        return mp3_bytes, "audio.mp3"
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.warning(f"Audio preprocess failed ({e}), using original file")
        try:
            return _read_raw(webm_path), "audio.webm"
        except Exception:
            raise e
