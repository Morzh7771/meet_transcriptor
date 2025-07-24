from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.backend.audio.audio_server import AudioServer
import asyncio
import websockets
import aiohttp
import os
import json
import time
from typing import Optional

app = FastAPI()
audio_server = AudioServer()
BACKEND_URL = "http://localhost:3000"

class LoginRequest(BaseModel):
    email: str
    password: str
    phone: str

class TwoFARequest(BaseModel):
    code: str

class ConnectRequest(BaseModel):
    email: str
    password: str
    meetCode: str
    duration: int = 30
    port: int = 8765

@app.post("/start-login")
async def login(req: LoginRequest):
    async with aiohttp.ClientSession() as session:
        print("🔐 Sending request to /start-login...")
        response = await session.post(
            f"{BACKEND_URL}/start-login",
            json=req.dict()
        )
        text = await response.text()
        return {"status": response.status, "message": text}

@app.post("/submit-2fa")
async def submit_2fa(req: TwoFARequest):
    async with aiohttp.ClientSession() as session:
        print("🔐 Sending code to /submit-2fa...")
        response = await session.post(
            f"{BACKEND_URL}/submit-2fa",
            json=req.dict()
        )
        text = await response.text()
        return {"status": response.status, "message": text}

@app.post("/connect")
async def connect(req: ConnectRequest):
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            f"{BACKEND_URL}/start",
            json={
                "email": req.email,
                "password": req.password,
                "meetCode": req.meetCode,
                "duration": req.duration,
                "port": req.port
            }
        )
        text = await response.text()
        print(f"▶️ Start command sent, response: {response.status} — {text}")
    try:
        asyncio.create_task(audio_server.start(req.port))
        return {
            "status": "started",
            "message": "Audio server started and Node.js stream launched",
            "websocket_port": req.port
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start audio server: {e}")
