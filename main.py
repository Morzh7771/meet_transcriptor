"""Run the Meet Transcript API (extension backend)."""
import os
import sys

if getattr(sys, "frozen", False):
    sys.path.insert(0, sys._MEIPASS)

import uvicorn
from src.backend.api.fast_api import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8234"))
    uvicorn.run(app, host="127.0.0.1", port=port)
