from openai import OpenAI
import json
import re
from typing import Dict, Any, List
from datetime import datetime
from src.backend.utils.configs import Config
from src.backend.prompts.promptFacade import PromptFacade

class LLMFilter:
    def __init__(self, api_key: str, templates_dir: str = "prompts"):
        self.client = OpenAI(api_key=api_key)
 
    def extract_filters(self, user_query: str) -> Dict[str, Any]:
        """Extract filters from user query"""
        try:
       
            prompt = PromptFacade.get_prompt(
                "filter_rag_ch",
                user_query=user_query,
                current_date=datetime.now().isoformat()
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            result = response.choices[0].message.content.strip()
            return self._parse_json_response(result)
            
        except Exception:
            return {}
    
    def generate_answer(self, user_query: str, search_results: List[Dict]) -> str:
        """Generate answer based on search results"""
        if not search_results:
            return "No relevant results found for your query."
        
        try:
   
            chunks = self._prepare_chunks_for_template(search_results)
            prompt = PromptFacade.get_prompt(
                "answer_rag_ch", 
                user_query=user_query, 
                chunks=chunks
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=16000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"Sorry, an error occurred while processing your request: {str(e)}"
    
    def _parse_json_response(self, result: str) -> Dict[str, Any]:
        """Parse JSON response with fallback"""
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {}
    
    def _prepare_chunks_for_template(self, search_results: List[Dict]) -> List[Dict]:
        """Prepare chunks data for template"""
        chunks = []
        for result in search_results:
            metadata = result['metadata']
            chunk_data = {
                'text': result['text'],
                'metadata': {
                    'meeting_id': metadata.get('meeting_id', ''),
                    'title': metadata.get('title', ''),
                    'date': metadata.get('date_start', ''),
                    'duration': metadata.get('duration', 0),
                    'language': metadata.get('language', ''),
                    'tags': metadata.get('tags', ''),
                    'summary': metadata.get('summary', ''),
                    'action_items': metadata.get('action_items', ''),
                    'notes': metadata.get('notes', ''),
                    'overview': metadata.get('overview', ''),
                    'participants': metadata.get('participants', ''),
                    'chunk': metadata.get('chunk', 0),
                    'total_chunks': metadata.get('total_chunks', 1)
                }
            }
            chunks.append(chunk_data)
        return chunks