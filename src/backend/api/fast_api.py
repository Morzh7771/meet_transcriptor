"""
Meet transcript: start meet → audio in 30s chunks → Groq → text in extension.
API: /start, /stop/{meet_code}, /sessions, /health, /
"""
import asyncio
from typing import Dict
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.backend.models.api_models import StartMeetingRequest
from src.backend.core.Facade import Facade

facade = Facade()
_session_tasks: Dict[str, asyncio.Task] = {}
_session_tasks_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    async with _session_tasks_lock:
        for meet_code, task in list(_session_tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


app = FastAPI(
    title="Meet Transcript API",
    description="Start/stop meeting transcription. Real-time transcript in extension.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Meet Transcript API"}


@app.post("/start")
async def start(request: StartMeetingRequest):
    """Start transcription for meet_code. Returns ws_port and chat_port for extension."""
    meet_code = None
    task = None
    try:
        meet_code = (request.meet_code or "").strip()
        if not meet_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="meet_code is required",
            )
        async with _session_tasks_lock:
            if meet_code in _session_tasks and not _session_tasks[meet_code].done():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Recording for {meet_code} is already running",
                )

        ws_port = await facade.find_free_port()
        chat_port = await facade.find_free_port()
        while chat_port == ws_port:
            chat_port = await facade.find_free_port()

        facade.logger.info(f"Starting transcript session {meet_code} ws={ws_port} chat={chat_port}")

        meeting_lang = (request.meeting_language or "uk").strip() or "uk"
        task = asyncio.create_task(
            facade.run_google_meet_recording_api(
                meet_code,
                meeting_lang,
                ws_port,
                chat_port,
            )
        )
        async with _session_tasks_lock:
            _session_tasks[meet_code] = task

        audio_server = await facade.get_or_create_audio_server(meet_code)
        servers_ready = await audio_server.wait_until_ready(timeout=20)
        if not servers_ready:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            async with _session_tasks_lock:
                _session_tasks.pop(meet_code, None)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="WebSocket servers failed to start",
            )

        def _cleanup(t):
            asyncio.create_task(_cleanup_task(meet_code, t))

        task.add_done_callback(_cleanup)
        return {
            "ok": True,
            "status": "started",
            "meet_code": meet_code,
            "ws_port": ws_port,
            "chat_port": chat_port,
        }
    except HTTPException:
        raise
    except Exception as e:
        facade.logger.error(f"Failed to start {meet_code}: {e}", exc_info=True)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if meet_code:
            async with _session_tasks_lock:
                _session_tasks.pop(meet_code, None)
        return {"ok": False, "error": str(e)}


async def _cleanup_task(meet_code: str, task: asyncio.Task):
    async with _session_tasks_lock:
        _session_tasks.pop(meet_code, None)
    try:
        if task.exception():
            facade.logger.error(f"Task {meet_code} failed: {task.exception()}")
    except (asyncio.CancelledError, Exception):
        pass


@app.post("/stop/{meet_code}")
async def stop(meet_code: str):
    """Stop transcription for meet_code."""
    try:
        meet_code = meet_code.strip()
        async with _session_tasks_lock:
            if meet_code not in _session_tasks:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No active recording for {meet_code}",
                )
            task = _session_tasks[meet_code]

        audio_server = await facade.get_or_create_audio_server(meet_code)
        await audio_server.terminate()
        try:
            await asyncio.wait_for(task, timeout=10)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        async with _session_tasks_lock:
            _session_tasks.pop(meet_code, None)
        return {"ok": True, "status": "stopped", "meet_code": meet_code}
    except HTTPException:
        raise
    except Exception as e:
        facade.logger.error(f"Error stopping {meet_code}: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/sessions")
async def list_sessions():
    """List active transcript sessions."""
    async with _session_tasks_lock:
        sessions = {
            mc: {"status": "running" if not t.done() else "completed", "done": t.done()}
            for mc, t in _session_tasks.items()
        }
    return {"ok": True, "total_sessions": len(sessions), "sessions": sessions}


@app.get("/health")
async def health():
    """Health check."""
    async with _session_tasks_lock:
        active = sum(1 for t in _session_tasks.values() if not t.done())
    return {"status": "healthy", "active_sessions": active}
