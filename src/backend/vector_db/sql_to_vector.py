import os
import uuid
import json, re
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, Filter, FieldCondition, MatchValue, Distance, VectorParams, PayloadSchemaType
from openai import OpenAI
 
from datetime import datetime, timedelta 
from src.backend.vector_db.chunker import create_chunks
from src.backend.utils.configs import Config
from src.backend.utils.logger import CustomLog

 
logger = CustomLog()

class SQLQdrantSynchronizer:
    def __init__(self):
        self.config = Config()
        
        # SQL connection
        self.sql_engine = create_engine(self.config.db.connection_url, echo=False)
        db_url = f"mysql+pymysql://{self.config.db.USER}:{self.config.db.PASSWORD.get_secret_value()}@{self.config.db.HOST}:{self.config.db.PORT}/{self.config.db.NAME}?charset=utf8mb4"
        self.sql_engine = create_engine(db_url, echo=False)
        # Qdrant connection
        qdrant_params = {
            "url": self.config.vectordb.URL,
            "timeout": 60
        }
        
 
        
        self.qdrant_client = QdrantClient(**qdrant_params)
        
        # OpenAI client using pydantic config
        self.openai_client = OpenAI(api_key=self.config.openai.API_KEY.get_secret_value())
        self.embedding_model = "text-embedding-3-small"
        
        self.collection_name = "meetings"
        self.table_name = self._find_table()
        
        self._test_connections()
        self._ensure_collection()
        
        logger.info(f"Initialized with table: {self.table_name}")
        logger.info(f"SQL Host: {self.config.db.HOST}:{self.config.db.PORT}")
        logger.info(f"Qdrant URL: {self.config.vectordb.URL}")
    
    def _vectorize_text(self, text: str) -> List[float]:
        """Create embeddings using OpenAI API"""
        response = self.openai_client.embeddings.create(
            input=text,
            model=self.embedding_model
        )
        return response.data[0].embedding
    
    def _normalize_tags(self, raw) -> List[str]:
        """Convert tags string to list for keyword matching"""
        if raw is None:
            return []
        
        if isinstance(raw, list):
            return [str(tag).strip() for tag in raw if tag and str(tag).strip()]
        
        # Split by comma, semicolon, or pipe
        tags_str = str(raw).strip()
        if not tags_str:
            return []
        
        tags = re.split(r'[,;|]+', tags_str)
        return [tag.strip() for tag in tags if tag.strip()]

    def _normalize_participants(self, raw) -> list[str]:
        if raw is None:
            return []
     
        if isinstance(raw, list):
            vals = raw
        else:
            s = str(raw).strip()
        
            try:
                maybe = json.loads(s)
                if isinstance(maybe, list):
                    vals = maybe
                else:
                    # fallback: "Alice, Bob | Charlie;  Dave"
                    vals = re.split(r"[,\|\;]+", s)
            except json.JSONDecodeError:
                vals = re.split(r"[,\|\;]+", s)

        vals = [v.strip() for v in vals if v and v.strip()]
     
        seen, out = set(), []
        for v in vals:
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out
    
    def _find_table(self) -> str:
        required_cols = {
            'id', 'client_id', 'consultant_id', 'title', 'summary', 'date', 'duration',
            'overview', 'notes', 'participants', 'action_items', 'trascription', 'language', 'tags'
        }
        
        with self.sql_engine.connect() as conn:
            tables = [row[0] for row in conn.execute(text("SHOW TABLES"))]
            
            for table in tables:
                try:
                    columns = {row[0] for row in conn.execute(text(f"DESCRIBE `{table}`"))}
                    if required_cols.issubset(columns):
                        return table
                except Exception:
                    continue
        
        raise ValueError("Meeting table not found")
    
    def _test_connections(self):
        """Test both SQL and Qdrant connections"""
        try:
            with self.sql_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("SQL connection test: OK")
        except Exception as e:
            logger.error(f"SQL connection test failed: {e}")
            raise
        
        try:
            self.qdrant_client.get_collections()
            logger.info("Qdrant connection test: OK")
        except Exception as e:
            logger.error(f"Qdrant connection test failed: {e}")
            raise
    
    def _collection_exists(self) -> bool:
        """Check if collection exists"""
        try:
            collections = [col.name for col in self.qdrant_client.get_collections().collections]
            return self.collection_name in collections
        except Exception as e:
            logger.error(f"Error checking collections: {e}")
            return False
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        if not self._collection_exists():
            logger.info(f"Creating collection '{self.collection_name}'...")
            
            # Use vector size 1536
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
            )
            
            # Create indexes
            self._create_indexes()
            logger.info(f"Collection '{self.collection_name}' created successfully")
        else:
            logger.info(f"Collection '{self.collection_name}' already exists")

    def _create_indexes(self):
        index_fields = [
            ("meeting_id", PayloadSchemaType.KEYWORD),
            ("client_id", PayloadSchemaType.KEYWORD),
            ("consultant_id", PayloadSchemaType.KEYWORD),
            ("date_start", PayloadSchemaType.DATETIME),
            ("date_end", PayloadSchemaType.DATETIME),
            ("language", PayloadSchemaType.KEYWORD),
            ("chunk", PayloadSchemaType.INTEGER),
            ("total_chunks", PayloadSchemaType.INTEGER),
            ("duration", PayloadSchemaType.INTEGER),
            ("title", PayloadSchemaType.TEXT),
            ("tags", PayloadSchemaType.KEYWORD),
            ("summary", PayloadSchemaType.TEXT),
            ("overview", PayloadSchemaType.TEXT),
            ("notes", PayloadSchemaType.TEXT),
            ("action_items", PayloadSchemaType.TEXT),
            ("participants", PayloadSchemaType.KEYWORD),
            ("chunk_text", PayloadSchemaType.TEXT),
        ]
        
        for field_name, field_type in index_fields:
            try:
                self.qdrant_client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_type
                )
                logger.info(f"Created index for field: {field_name}")
            except Exception as e:
                logger.warning(f"Failed to create index for {field_name}: {e}")

    def _get_meeting(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        with self.sql_engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT * FROM `{self.table_name}` WHERE id = :id"), 
                {"id": meeting_id}
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None
    
    def _exists_in_qdrant(self, meeting_id: str) -> bool:
        try:
            result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="meeting_id", match=MatchValue(value=meeting_id))]
                ),
                limit=1
            )
            return len(result[0]) > 0
        except Exception:
            return False
     
    def _process_meeting(self, meeting_data: Dict[str, Any]) -> bool:
        transcript = (meeting_data.get('trascription') or '').strip()
        if not transcript:
            return False
        
        duration_val = meeting_data.get('duration')
        if not duration_val or duration_val == 0:
            logger.info(f"Skipping meeting {meeting_data['id']} - duration is 0 or null")
            return False     
           
        chunks = create_chunks(transcript)
        if not chunks:
            return False
        
        points = []
        for chunk_idx, chunk_text in enumerate(chunks):
            vector = self._vectorize_text(chunk_text)

            date_obj = meeting_data.get('date')             
            duration_val = meeting_data.get('duration')     

            # Normalize values
            date_start = date_obj.isoformat() if isinstance(date_obj, datetime) else None
            date_end = (date_obj + timedelta(seconds=duration_val)).isoformat() if date_obj and duration_val else None
            
            participants_list = self._normalize_participants(meeting_data.get('participants', ''))
            tags_list = self._normalize_tags(meeting_data.get('tags', ''))
            
            payload = payload = {
                "meeting_id": meeting_data['id'],
                "client_id": meeting_data.get('client_id', ''),
                "consultant_id": meeting_data.get('consultant_id', ''),
                "title": meeting_data.get('title', ''),
                "summary": meeting_data.get('summary', ''),
                "date_start": date_start,
                "date_end": date_end,
                "duration": meeting_data.get('duration'),
                "overview": meeting_data.get('overview', ''),
                "notes": meeting_data.get('notes', ''),
                "action_items": meeting_data.get('action_items', ''),
                "language": meeting_data.get('language', ''),
                "tags": tags_list,
                "participants": participants_list,
                "chunk": chunk_idx,
                "chunk_text": chunk_text,
                "total_chunks": len(chunks),
            }
            
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=payload
            ))
        
        try:
            self.qdrant_client.upsert(collection_name=self.collection_name, points=points)
            logger.info(f"Added meeting {meeting_data['id']} with {len(chunks)} chunks")
            return True
        except Exception as e:
            logger.error(f"Failed to add meeting {meeting_data['id']}: {e}")
            return False
    
    def sync_meetings(self, meeting_ids: List[str]) -> Dict[str, int]:
        stats = {'processed': 0, 'added': 0, 'skipped': 0, 'errors': 0}
        
        for meeting_id in meeting_ids:
            stats['processed'] += 1
            
            if self._exists_in_qdrant(meeting_id):
                stats['skipped'] += 1
                logger.info(f"Meeting {meeting_id} already exists, skipping")
                continue
            
            meeting_data = self._get_meeting(meeting_id)
            if not meeting_data:
                stats['errors'] += 1
                continue
            
            if self._process_meeting(meeting_data):
                stats['added'] += 1
            else:
                stats['errors'] += 1
        
        logger.info(f"Sync complete - processed: {stats['processed']}, added: {stats['added']}, skipped: {stats['skipped']}, errors: {stats['errors']}")
        return stats
    
    def sync_all(self, limit: Optional[int] = None) -> Dict[str, int]:
        with self.sql_engine.connect() as conn:
            query = f"SELECT id FROM `{self.table_name}` ORDER BY date DESC"
            if limit:
                query += f" LIMIT {limit}"
            
            result = conn.execute(text(query))
            ids = [row[0] for row in result]
        
        logger.info(f"Found {len(ids)} meetings to process")
        return self.sync_meetings(ids) if ids else {'processed': 0, 'added': 0, 'skipped': 0, 'errors': 0}

    def recreate_collection(self):
        """Recreate collection from scratch"""
        try:
            if self._collection_exists():
                logger.info(f"Deleting existing collection '{self.collection_name}'...")
                self.qdrant_client.delete_collection(self.collection_name)
            
            logger.info(f"Creating fresh collection '{self.collection_name}'...")
            self._ensure_collection()
            
        except Exception as e:
            logger.error(f"Error recreating collection: {e}")
            raise

 