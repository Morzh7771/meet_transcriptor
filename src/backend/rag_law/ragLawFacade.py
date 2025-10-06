import os
from typing import Dict, Any, List
from src.backend.vector_db.qdrant_Facade import VectorDBFacade
from src.backend.rag_law.llm_filter_law import LLMFilter
from src.backend.rag_law.search_law import SearchLawService
class LawRAGFacade:
    def __init__(self):
        vector_db = VectorDBFacade()
        self.search_law_service = SearchLawService(vector_db.laws)
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)   
        template_dir = os.path.join(project_root, 'prompts', 'templates')
        
        self.llm_filter = LLMFilter(template_dir=template_dir)
    
    def search_laws(self, user_query: str, limit: int = None) -> Dict[str, Any]:
        """Search method for laws without filters"""
        results = self.search_law_service.search(user_query, limit)
        answer = self.llm_filter.generate_answer_law(user_query, results)
        
        return self._build_response(user_query, {}, results, answer)
 
    def _build_response(
                    self,
                    query: str,
                    filters: Dict[str, Any],
                    results: List[Dict],
                    answer: str,
                    **extra_fields
                ) -> Dict[str, Any]:
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