import asyncio
from typing import Dict

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from src.backend.models.api_models import StartMeetingRequest,MeetBotChat,GetChatTopics

from src.backend.core.Facade import Facade

from src.backend.db.dbFacade import DBFacade

app = FastAPI(title="Meet-Recorder Controller")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app URL
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# One Facade for the whole service.
facade = Facade()
db = DBFacade()
# Keep track of recorder coroutines keyed by meet-code (or any session ID you prefer).
_session_tasks: Dict[str, asyncio.Task] = {}


@app.post("/start")
async def start(request: StartMeetingRequest):
    """
    Launch recording for *meet_code*.
    """
    try:
        meet_code = request.meet_code.strip()
        ws_port = await facade.find_free_port()
        chat_port = await facade.find_free_port()
        
        while chat_port == ws_port:
            chat_port = await facade.find_free_port()
            
        if not meet_code:
            raise HTTPException(400, detail="Body must contain a non-empty meet code")

        #if meet_code in _session_tasks:
            #raise HTTPException(409, detail=f"Recording for {meet_code} is already running")

        # fire-and-forget recorder; store task so we can await / cancel later
        _session_tasks[meet_code] = asyncio.create_task(
            facade.run_google_meet_recording_api(request.client_id, meet_code, request.meeting_language, ws_port, chat_port,request.consultant_id)
        )
        
        return {
            "ok": True,
            "status": "started", 
            "meet_code": meet_code, 
            "ws_port": ws_port, 
            "chat_port": chat_port
        }
    except HTTPException:
        raise
    except Exception as e:
        # Возвращаем ошибку в формате, который ожидает frontend
        return {
            "ok": False,
            "error": str(e)
        }

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


@app.post("/getAllMeets")
async def getAllMeets():
    result = await db.get_all_meets()
    return result


@app.post("/meetBotChat")
async def getAllMeets(request: MeetBotChat):
    res = await facade.startMessageBot(request.message,request.meet_id,request.chat_id)
    return res


@app.post("/getChatTopics")
async def getAllMeets(request: GetChatTopics):
    res = await db.get_all_meet_topics(request.meet_id)
    return res

