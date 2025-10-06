import os
import socket
import random
import asyncio
from uuid import uuid4
from src.backend.api.js_plagin_api import JsPluginApi
from src.backend.audio.audio_server import AudioServer
from src.backend.core.baseFacade import BaseFacade
from src.backend.modules.chatBot import ChatBot
from src.backend.rag_meet.ragMeetFacade import MeetRAGFacade
from src.backend.vector_db.sql_to_vector import SQLQdrantSynchronizer
 

class Facade(BaseFacade):
    def __init__(self):
        super().__init__()
        self.email = self.configs.account.EMAIL
        self.password = self.configs.account.PASSWORD
        self.backend_url = self.configs.backend.BACKEND_URL
        self.js_plugin_api = JsPluginApi(self.email, self.password, self.backend_url)
        self.session_done = asyncio.Event()
        self.chat_bot = ChatBot()
        self.meet_rag_facade = MeetRAGFacade()
        # Dictionary to store AudioServer instances by meet_code for parallel sessions
        self._audio_servers = {}
        self._audio_servers_lock = asyncio.Lock()
        
    async def get_or_create_audio_server(self, meet_code: str) -> AudioServer:
        """
        Get existing AudioServer instance or create a new one for the meet_code.
        Thread-safe for parallel sessions.
        
        Args:
            meet_code: Unique meeting identifier
            
        Returns:
            AudioServer instance
        """
        async with self._audio_servers_lock:
            if meet_code not in self._audio_servers:
                self.logger.info(f"Creating new AudioServer for meet_code: {meet_code}")
                self._audio_servers[meet_code] = AudioServer()
            return self._audio_servers[meet_code]
    
    async def remove_audio_server(self, meet_code: str):
        """
        Remove AudioServer instance when session ends.
        Thread-safe cleanup.
        
        Args:
            meet_code: Meeting identifier to remove
        """
        async with self._audio_servers_lock:
            if meet_code in self._audio_servers:
                self.logger.info(f"Removing AudioServer for meet_code: {meet_code}")
                del self._audio_servers[meet_code]
        
    async def process_rag_chat(self, message: str, chat_id: str = None, user_id: str = None):
        """
        Process RAG chat message.
        
        Args:
            message: User message
            chat_id: Optional chat ID
            user_id: Optional user ID
            
        Returns:
            Tuple of (chat_id, user_id, response)
        """
        chat_id = chat_id or str(uuid4())
        user_id = user_id or str(uuid4())
        try:
            rag_result = await asyncio.to_thread(
                self.meet_rag_facade.search_with_llm_filters, message)
            
            # Extract response
            response = {
                "message": rag_result.get("answer", "Sorry, we couldn't get a response."),
            }
            
            self.logger.info(
                f"RAG chat processed: chat_id={chat_id}, user_id={user_id}, "
                f"results={rag_result.get('total_results', 0)}"
            )
            
            return chat_id, user_id, response
            
        except Exception as e:
            self.logger.error(f"Error in RAG chat processing: {e}", exc_info=True)
            return chat_id, user_id, {
                "message": f"An error occurred while processing your request.: {str(e)}",
            }

    async def sync(self, recreate: bool = False):
        """
        Sync meetings from SQL to vector DB.
        
        Args:
            recreate: Whether to recreate the collection
            
        Returns:
            Sync result
        """
        def _sync():
            sync = SQLQdrantSynchronizer()
            if recreate:
                sync.recreate_collection()
            return sync.sync_all()
        
        return await asyncio.to_thread(_sync)

    async def find_free_port(self, max_attempts=1000):
        """
        Find free port - thread-safe for parallel sessions.
        
        Args:
            max_attempts: Maximum number of attempts to find a free port
            
        Returns:
            Free port number
            
        Raises:
            RuntimeError: If no free port found after max_attempts
        """
        tried_ports = set()
        for _ in range(max_attempts):
            port = random.randint(10000, 60000)
            if port in tried_ports:
                continue
            tried_ports.add(port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("Could not find free port")

    async def run_google_meet_recording_api(
        self, 
        user_id: str, 
        meet_code: str, 
        meeting_language: str, 
        ws_port: int, 
        chat_port: int, 
        consultant_id: str
    ):
        """
        Start a Google Meet recording session with audio server and WebSocket connection.
        Supports parallel execution for multiple meetings.
        
        Args:
            user_id: The user/client ID
            meet_code: The Google Meet code to record
            meeting_language: Language for transcription
            ws_port: WebSocket port for audio
            chat_port: WebSocket port for violations/chat
            consultant_id: Consultant ID
            
        Raises:
            RuntimeError: If WebSocket servers fail to start
        """
        audio_server = None
        ws_task = None
        
        try:
            self.logger.info(
                f"🚀 Starting session for meet: {meet_code} on ports {ws_port}/{chat_port}"
            )
        
            # Get or create audio server for this specific meeting
            audio_server = await self.get_or_create_audio_server(meet_code)
            
            # Start recording session
            ws_task = asyncio.create_task(
                audio_server.start(
                    user_id, 
                    meet_code, 
                    meeting_language, 
                    ws_port, 
                    chat_port, 
                    consultant_id
                )
            )
            
            # Wait for servers to be ready before proceeding
            servers_ready = await audio_server.wait_until_ready(timeout=15)
            if not servers_ready:
                raise RuntimeError(
                    f"WebSocket servers failed to start for meet {meet_code}"
                )
            
            self.logger.info(f"✅ WebSocket servers ready for meet {meet_code}")
            
            # Connect JS plugin (uncomment when ready)
            # await self.js_plugin_api.connect(meet_code, ws_port, chat_port)
        
            # Wait for session to complete
            await ws_task

            self.logger.info(f"✅ Session for {meet_code} completed successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Error in session {meet_code}: {e}", exc_info=True)
            if ws_task and not ws_task.done():
                ws_task.cancel()
                try:
                    await ws_task
                except asyncio.CancelledError:
                    pass
            raise  # Re-raise to propagate error to API endpoint
        
        finally:
            # Clean up audio server instance
            await self.remove_audio_server(meet_code)
            self.logger.info(f"🧹 Cleaned up resources for meet {meet_code}")
            
    async def startMessageBot(self, message: str, meetId: str, chat_id=None):
        """
        Start message bot for meeting questions.
        
        Args:
            message: User message
            meetId: Meeting ID
            chat_id: Optional chat ID
            
        Returns:
            Tuple of (chat_id, result)
        """
        chatID = chat_id if chat_id is not None else str(uuid4())
        result = await self.chat_bot.process_meet_questions(chatID, meetId, message)
        return chatID, result