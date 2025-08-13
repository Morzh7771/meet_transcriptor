import os
import json
import time
import asyncio
import websockets
from src.backend.audio.chunk_handler import ChunkHandler
from src.backend.audio.transcript_manager import TranscriptManager
from src.backend.audio.speaker_tracker import SpeakerTracker
from src.backend.utils.logger import CustomLog

log = CustomLog()

class ChatBot:
    def __init__(self):
        self.messages = []
        self.uri = "ws://localhost:3000"
    
    async def send_bot_message(self, message):
        async with websockets.connect(self.uri) as websocket:
            command = f"send-bot-message:{message}"
            
            await websocket.send(command)
            print(f"Message sent to JS: {command}")