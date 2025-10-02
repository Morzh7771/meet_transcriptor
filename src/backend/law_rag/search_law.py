from typing import List, Dict
from src.backend.law_parser.vectorizer import TextVectorizer
from src.backend.law_parser.qdrant_manager import QdrantManager
import os

class SearchLawService:
    def __init__(self):
        self.vectorizer = TextVectorizer()
        self.qdrant = QdrantManager(collection_name="laws")
        self.collection_name = "laws"
    
    def search(self, query: str, limit: int = None) -> List[Dict]:
        """Main search method for laws"""
        search_limit = self._determine_search_limit(limit)
        results = self._perform_semantic_search(query, search_limit)
        
        if not results:
            return []
        
        return self._format_results(results[:limit] if limit else results)
    
    def _determine_search_limit(self, limit: int) -> int:
        """Calculate appropriate search limit"""
        if limit:
            return limit * 2   
        return 50   
    
    def _perform_semantic_search(self, query: str, limit: int):
        """Execute semantic search"""
        query_vector = self.vectorizer.vectorize(query)
        return self.qdrant.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector.tolist(),
            limit=limit
        )
    
    def _format_results(self, results) -> List[Dict]:
        """Format search results for output"""
        formatted = []
        for result in results:
            payload = result.payload
            formatted.append({
                "score": result.score,
                "text": payload["text"],
                "metadata": {
                    "id": payload["id"],
                    "num_chunk": payload["num_chunk"],
                    "total_chunk": payload["total_chunk"]
                }
            })
        return formatted