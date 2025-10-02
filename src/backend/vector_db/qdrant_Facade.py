from typing import Optional
from src.backend.vector_db.qdrant_manager_meetings import QdrantManager
from src.backend.vector_db.qdrant_manager_law import QdrantManager as LawQdrantManager
from src.backend.vector_db.qdrant_manager_client_profiles import ClientVectorSimilarity
from src.backend.utils.configs import Config
from src.backend.utils.logger import CustomLog


class VectorDBFacade:
    """Unified facade for all vector database operations"""
    
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self.config = Config.load_config()
        self.logger = CustomLog()
        
        self.logger.info("Initializing all vector database managers...")
        
        self._meetings_manager = QdrantManager(url=self.config.vectordb.URL)
        self._meetings_manager.create_collection(
            collection_name="meetings",
            vector_size=1536
        )
        self.logger.info("✓ Meetings collection ready")
        
        self._laws_manager = LawQdrantManager(collection_name="laws")
        self.logger.info("✓ Laws collection ready")
        
        self._client_profiles_manager = ClientVectorSimilarity()
    
   
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
        
                asyncio.create_task(self._client_profiles_manager.initialize_collection())
            else:
        
                loop.run_until_complete(self._client_profiles_manager.initialize_collection())
            self.logger.info("✓ Client profiles collection ready")
        except Exception as e:
            self.logger.warning(f"Client profiles collection will be initialized later: {e}")
        
        self.logger.info("All vector database managers initialized successfully")
        self._initialized = True

    @property
    def meetings(self) -> QdrantManager:
        """Get meetings collection manager"""
        return self._meetings_manager

    @property
    def laws(self) -> LawQdrantManager:
        """Get laws collection manager"""
        return self._laws_manager

    @property
    def client_profiles(self) -> ClientVectorSimilarity:
        """Get client profiles manager"""
        return self._client_profiles_manager

    async def ensure_client_profiles_initialized(self):
        """Ensure client profiles collection is initialized (async helper)"""
        try:
            await self._client_profiles_manager.initialize_collection()
            self.logger.info("✓ Client profiles collection initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize client profiles: {e}")

    def get_collection_stats(self) -> dict:
        """Get statistics for all collections"""
        stats = {}
        
        try:
            # Meetings stats
            meetings_info = self.meetings.client.get_collection("meetings")
            stats["meetings"] = {
                "points_count": meetings_info.points_count,
                "status": meetings_info.status
            }
        except Exception as e:
            stats["meetings"] = {"error": str(e)}
        
        try:
            # Laws stats
            laws_info = self.laws.client.get_collection("laws")
            stats["laws"] = {
                "points_count": laws_info.points_count,
                "status": laws_info.status
            }
        except Exception as e:
            stats["laws"] = {"error": str(e)}
        
        try:
            # Client profiles stats
            profiles_info = self.client_profiles.qdrant_client.get_collection("client_profiles")
            stats["client_profiles"] = {
                "points_count": profiles_info.points_count,
                "status": profiles_info.status
            }
        except Exception as e:
            stats["client_profiles"] = {"error": str(e)}
        
        return stats