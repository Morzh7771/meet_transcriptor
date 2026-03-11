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


def _free_port(port: int) -> None:
    """Kill any process listening on *port* so uvicorn can bind cleanly."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) != 0:
            return  # port already free
    try:
        if sys.platform == "win32":
            import subprocess
            r = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            for line in r.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    try:
                        pid = int(parts[-1])
                    except (ValueError, IndexError):
                        continue
                    if pid and pid != os.getpid():
                        subprocess.run(
                            ["taskkill", "/PID", str(pid), "/F"],
                            creationflags=subprocess.CREATE_NO_WINDOW,
                            capture_output=True,
                        )
                        break
        else:
            import signal
            import subprocess
            r = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True,
            )
            for pid_str in r.stdout.strip().splitlines():
                try:
                    pid = int(pid_str.strip())
                    if pid != os.getpid():
                        os.kill(pid, signal.SIGTERM)
                except (ValueError, ProcessLookupError):
                    pass
    except Exception:
        pass
    import time
    time.sleep(0.5)


def _filter_health_logs() -> None:
    """Suppress uvicorn access-log entries for /health and /status endpoints."""
    import logging

    class _HealthFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage()
            return '/health HTTP/' not in msg and '/status HTTP/' not in msg

    logging.getLogger("uvicorn.access").addFilter(_HealthFilter())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8234"))
    _free_port(port)
    _filter_health_logs()
    uvicorn.run(app, host="127.0.0.1", port=port)
