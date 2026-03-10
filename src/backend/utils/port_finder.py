import random
import socket


def find_free_port(max_attempts: int = 1000) -> int:
    """Find a free port in the dynamic range (10000-60000)."""
    tried = set()
    for _ in range(max_attempts):
        port = random.randint(10000, 60000)
        if port in tried:
            continue
        tried.add(port)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found")
