import asyncio
from typing import Dict, Optional


class SessionManager:
    """Registry of active recording sessions (meet_code -> asyncio.Task)."""

    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def register(self, meet_code: str, task: asyncio.Task) -> None:
        """Register a session task for meet_code."""
        async with self._lock:
            self._tasks[meet_code] = task

    async def remove(self, meet_code: str) -> None:
        """Remove session from registry."""
        async with self._lock:
            self._tasks.pop(meet_code, None)

    async def get(self, meet_code: str) -> Optional[asyncio.Task]:
        """Get task for meet_code if present."""
        async with self._lock:
            return self._tasks.get(meet_code)

    async def is_running(self, meet_code: str) -> bool:
        """True if meet_code has an active (not done) task."""
        async with self._lock:
            task = self._tasks.get(meet_code)
            return task is not None and not task.done()

    async def list_sessions(self) -> Dict[str, dict]:
        """Return dict of meet_code -> {status, done} for all sessions."""
        async with self._lock:
            return {
                mc: {"status": "running" if not t.done() else "completed", "done": t.done()}
                for mc, t in self._tasks.items()
            }

    async def count_active(self) -> int:
        """Number of sessions with non-done tasks."""
        async with self._lock:
            return sum(1 for t in self._tasks.values() if not t.done())

    async def cleanup_all(self) -> None:
        """Cancel all tasks and wait for them. Call on app shutdown."""
        async with self._lock:
            for meet_code, task in list(self._tasks.items()):
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            self._tasks.clear()
