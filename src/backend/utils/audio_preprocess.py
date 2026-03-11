"""WebM to mono 16 kHz MP3 for Whisper. Peak normalization + compressed output.
Splitting for files > 24 MB is handled by the Transcriber."""
import os
import sys
from io import BytesIO
from typing import Tuple

from backend.utils.logger import CustomLog

WHISPER_SAMPLE_RATE = 16000


def _setup_ffmpeg() -> None:
    """Ensure pydub can find ffmpeg/ffprobe.

    Priority:
      1. Bundled binaries next to the frozen executable (_MEIPASS).
      2. Common Homebrew/system locations on macOS/Linux.
      3. System PATH (default pydub behaviour).

    On Windows also patches pydub's internal Popen to use CREATE_NO_WINDOW
    so no stray console windows appear.
    """
    is_win = sys.platform == "win32"
    exe_suffix = ".exe" if is_win else ""

    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(sys._MEIPASS)
        # Also check sibling of the executable on Windows one-dir builds
        candidates.append(os.path.dirname(sys.executable))
    if not is_win:
        candidates += ["/opt/homebrew/bin", "/usr/local/bin"]

    found_dir = None
    for directory in candidates:
        ffmpeg = os.path.join(directory, "ffmpeg" + exe_suffix)
        ffprobe = os.path.join(directory, "ffprobe" + exe_suffix)
        if os.path.isfile(ffmpeg) and os.path.isfile(ffprobe):
            found_dir = directory
            current = os.environ.get("PATH", "")
            if directory not in current:
                os.environ["PATH"] = directory + os.pathsep + current
            # Tell pydub explicitly where the binaries are
            try:
                from pydub import AudioSegment
                AudioSegment.converter = ffmpeg
                AudioSegment.ffmpeg = ffmpeg
                AudioSegment.ffprobe = ffprobe
            except Exception:
                pass
            break

    # On Windows: patch pydub's utils.Popen to suppress console windows.
    # This covers mediainfo_json / ffprobe calls regardless of PATH resolution.
    if is_win:
        try:
            import subprocess as _sp
            import pydub.utils as _pydub_utils

            _orig_popen = _pydub_utils.Popen

            def _hidden_popen(cmd, **kwargs):
                kwargs.setdefault("creationflags", _sp.CREATE_NO_WINDOW)
                return _orig_popen(cmd, **kwargs)

            _pydub_utils.Popen = _hidden_popen
        except Exception:
            pass


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
