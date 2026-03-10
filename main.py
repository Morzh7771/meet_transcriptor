"""Run the Meet Transcript API (extension backend)."""
import os
import sys

if getattr(sys, "frozen", False):
    sys.path.insert(0, sys._MEIPASS)

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8234"))
    host = "127.0.0.1"
    uvicorn.run(
        "src.backend.api.fast_api:app",
        host=host,
        port=port,
        reload=False,
    )
