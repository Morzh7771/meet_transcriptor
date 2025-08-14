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
        # self.uri = "ws://localhost:3000"
    
    async def process_message(self, message):
        log.info(f"Proccesing the message {message}")
        response = f"The response to the message {message}"
        return response
    
    # async def send_bot_message(self, message):
    #     log.info(f"Sending bot message: {message}")
    #     try:
    #         async with websockets.connect(self.uri) as websocket:
    #             command = f"send-chat-message:{message}"
    #             await websocket.send(command)
    #             log.info(f"Message sent to JS: {command}")
    #     except Exception as e:
    #         log.error(f"Failed to send bot message: {e}")