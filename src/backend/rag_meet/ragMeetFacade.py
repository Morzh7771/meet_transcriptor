from src.backend.vector_db.qdrant_Facade import VectorDBFacade
from src.backend.rag_meet.llm_filter_meet import LLMFilter
from src.backend.rag_meet.search_meet import SearchService
from src.backend.utils.configs import Config   
from typing import Dict, Any, List 

class MeetRAGFacade:
    def __init__(self):
        config = Config.load_config()
        vector_db = VectorDBFacade()
        self.search_service = SearchService(vector_db.meetings)
        self.llm_filter = LLMFilter(config.openai.API_KEY.get_secret_value(), "prompts")
    
    def search_with_llm_filters(self, user_query: str, limit: int = None) -> Dict[str, Any]:
        """Main search method with LLM-extracted filters"""
        filters = self.llm_filter.extract_filters(user_query)
        results = self.search_service.search(user_query, limit, filters)
        answer = self.llm_filter.generate_answer(user_query, results)
        
        return self._build_response(user_query, filters, results, answer)
 
    def _build_response(self, query: str, filters: Dict[str, Any], results: List[Dict], 
                       answer: str, **extra_fields) -> Dict[str, Any]:
        """Build standardized response"""
        response = {
            "original_query": query,
            "applied_filters": filters,
            "results": results,
            "answer": answer,
            "total_results": len(results)
        }
        response.update(extra_fields)
        return response