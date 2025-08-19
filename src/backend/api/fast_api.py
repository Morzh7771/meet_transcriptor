import asyncio
from typing import Dict

from fastapi import FastAPI, HTTPException, Body
from src.backend.models.api_models import StartMeetingRequest

from src.backend.core.Facade import Facade

app = FastAPI(title="Meet-Recorder Controller")

# One Facade for the whole service.
facade = Facade()

# Keep track of recorder coroutines keyed by meet-code (or any session ID you prefer).
_session_tasks: Dict[str, asyncio.Task] = {}


@app.post("/start")
async def start(request: StartMeetingRequest):
    """
    Launch recording for *meet_code*.
    """
    meet_code = request.meet_code.strip()
    
    if not meet_code:
        raise HTTPException(400, detail="Body must contain a non-empty meet code")

    if meet_code in _session_tasks:
        raise HTTPException(409, detail=f"Recording for {meet_code} is already running")

    # fire-and-forget recorder; store task so we can await / cancel later
    _session_tasks[meet_code] = asyncio.create_task(
        facade.run_google_meet_recording_api(request.user_id, meet_code, request.meeting_language)
    )
    return {"status": "started", "meet_code": meet_code}



@app.post("/terminate")
async def terminate(meet_code: str = Body(..., embed=False)):
    """
    Stop recording for *meet_code*.
    """
    meet_code = meet_code.strip()
    task = _session_tasks.get(meet_code)
    if not task:
        raise HTTPException(404, detail=f"No active session for {meet_code}")

    # Ask the JS plugin to shut the session down.
    await facade.js_plugin_api.terminate_by_meet_code(meet_code)

    # Optionally give the recorder coroutine up to 30 s to finish gracefully.
    try:
        await asyncio.wait_for(task, timeout=30)
    except asyncio.TimeoutError:
        task.cancel()

    _session_tasks.pop(meet_code, None)
    return {"status": "terminated", "meet_code": meet_code}