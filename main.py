"""Run the Meet Transcript API (extension backend)."""
import os
import uvicorn

# Explicit imports so PyInstaller statically traces the full dependency chain
import src.backend.core.facade  # noqa: F401
import src.backend.core.base_facade  # noqa: F401
import src.backend.models.api_models  # noqa: F401
import src.backend.services.session_manager  # noqa: F401
import src.backend.services.slack_notifier  # noqa: F401
import src.backend.services.s3_storage  # noqa: F401
import src.backend.audio.audio_server  # noqa: F401
import src.backend.audio.transcript_manager  # noqa: F401
import src.backend.audio.speaker_tracker  # noqa: F401
import src.backend.audio.speaker_resolver  # noqa: F401
import src.backend.audio.chunk_handler  # noqa: F401
import src.backend.modules.transcriber  # noqa: F401
import src.backend.utils.logger  # noqa: F401
import src.backend.utils.configs  # noqa: F401
import src.backend.utils.audio_preprocess  # noqa: F401
import src.backend.utils.port_finder  # noqa: F401
from src.backend.api.fast_api import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8234"))
    uvicorn.run(app, host="127.0.0.1", port=port)
