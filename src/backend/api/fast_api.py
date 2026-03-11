"""
Meet transcript API: start meet → audio in 30s chunks → Groq → text in extension.
Endpoints: /start, /stop/{meet_code}, /sessions, /health, /
"""
import asyncio
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.backend.models.api_models import StartMeetingRequest
from src.backend.core.facade import Facade
from src.backend.services.session_manager import SessionManager

facade = Facade()
session_manager = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await session_manager.cleanup_all()


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


async def _cleanup_task_callback(meet_code: str, task: asyncio.Task):
    await session_manager.remove(meet_code)
    try:
        if task.exception():
            facade.logger.error(f"Task {meet_code} failed: {task.exception()}")
    except (asyncio.CancelledError, Exception):
        pass


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
        if await session_manager.is_running(meet_code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Recording for {meet_code} is already running",
            )

        ws_port = await facade.find_free_port()
        chat_port = await facade.find_free_port()
        while chat_port == ws_port:
            chat_port = await facade.find_free_port()

        facade.logger.info(f"Starting transcript session {meet_code} ws={ws_port} chat={chat_port}")

        raw = (request.meeting_language or "").strip().lower()
        meeting_lang = "auto" if (not raw or raw == "auto") else request.meeting_language.strip()
        slack_dm_email = (request.slack_dm_email or "").strip() or None
        task = asyncio.create_task(
            facade.run_google_meet_recording_api(
                meet_code,
                meeting_lang,
                ws_port,
                chat_port,
                slack_dm_email=slack_dm_email,
            )
        )
        await session_manager.register(meet_code, task)

        audio_server = await facade.get_or_create_audio_server(meet_code)
        servers_ready = await audio_server.wait_until_ready(timeout=20)
        if not servers_ready:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await session_manager.remove(meet_code)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="WebSocket servers failed to start",
            )

        def _cleanup(t):
            asyncio.create_task(_cleanup_task_callback(meet_code, t))

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
            await session_manager.remove(meet_code)
        return {"ok": False, "error": str(e)}


@app.post("/stop/{meet_code}")
async def stop(meet_code: str):
    """Stop transcription for meet_code."""
    try:
        meet_code = meet_code.strip()
        task = await session_manager.get(meet_code)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active recording for {meet_code}",
            )

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
        await session_manager.remove(meet_code)
        return {"ok": True, "status": "stopped", "meet_code": meet_code}
    except HTTPException:
        raise
    except Exception as e:
        facade.logger.error(f"Error stopping {meet_code}: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/sessions")
async def list_sessions():
    """List active transcript sessions."""
    sessions = await session_manager.list_sessions()
    return {"ok": True, "total_sessions": len(sessions), "sessions": sessions}


@app.get("/health")
async def health():
    """Health check."""
    active = await session_manager.count_active()
    return {"status": "healthy", "active_sessions": active}


@app.get("/status")
async def status():
    """For launcher UI: is any session recording."""
    active = await session_manager.count_active()
    return {"recording": active > 0}
