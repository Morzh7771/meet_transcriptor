from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from src.backend.vector_db.chunker import create_chunks
from src.backend.vector_db.vectorizer import TextVectorizer
import uuid
from src.backend.utils.configs import Config

class QdrantManager:
    def __init__(self, collection_name: str = "laws"):
        self.configs = Config().load_config()
        
        self.client = QdrantClient(url=self.configs.vectordb.URL)
        self.collection_name = collection_name
        self.vectorizer = TextVectorizer()
        self._create_collection()
    
    def _create_collection(self):
        collections = self.client.get_collections().collections
        if not any(collection.name == self.collection_name for collection in collections):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
            )
    
    def process_and_store_law(self, law_text: str, law_id: str = None):
        if not law_id:
            law_id = str(uuid.uuid4())
        
       
        if not law_text.strip():
            return 0
            
        chunks = create_chunks(law_text)
        if not chunks:
            return 0
            
        total_chunks = len(chunks)
        
        points = []
        for i, chunk in enumerate(chunks):
            try:
                vector = self.vectorizer.vectorize(chunk)
                
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector.tolist(),
                    payload={
                        'text': chunk,
                        'total_chunk': total_chunks,
                        'id': law_id,
                        'num_chunk': i + 1
                    }
                )
                points.append(point)
            except Exception as e:
                print(f"Error vectorizing chunk {i+1} for {law_id}: {e}")
                continue
        
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        
        return len(points)