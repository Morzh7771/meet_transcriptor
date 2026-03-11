"""Run the Meet Transcript API (extension backend)."""
import os
import sys

# In non-frozen mode (plain `python main.py`), add src/ so 'backend' is importable
if not getattr(sys, "frozen", False):
    _src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
    if _src_dir not in sys.path:
        sys.path.insert(0, _src_dir)

import uvicorn
from backend.api.fast_api import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8234"))
    uvicorn.run(app, host="127.0.0.1", port=port)
