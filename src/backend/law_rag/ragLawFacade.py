import os
from typing import Dict, Any, List

from src.backend.law_rag.llm_filter import LLMFilter
from src.backend.law_rag.search_law import SearchLawService

class RAGFacade:
    def __init__(self):
        self.search_law_service = SearchLawService()
        
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