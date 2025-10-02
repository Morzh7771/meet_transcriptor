import os
import json
from typing import Dict, Any, List
from openai import OpenAI
from jinja2 import Environment, FileSystemLoader, select_autoescape
from src.backend.utils.configs import Config

class LLMFilter:
    def __init__(self, template_dir: str = None):
        self.configs = Config().load_config()
        self.api_key = self.configs.openai.API_KEY.get_secret_value()
        self.client = OpenAI(api_key=self.api_key)

        if template_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            template_dir = os.path.join(project_root, 'prompts', 'templates')
        
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape()
        )

    def generate_answer_law(self, user_query: str, search_results: List[Dict]) -> str:
        """Generate answer using Jinja2 template + law search results"""
        
        template = self.jinja_env.get_template("answer_rag_law.j2")
 
        template_content = template.render(
            user_query=user_query,
            fragments=search_results
        )
        
      
        try:
  
            messages = json.loads(template_content)
       
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Template parsing error: {e}")
            #print(f"Template content: {template_content[:500]}...")
            
 
            messages = [
                {
                    "role": "system",
                    "content": "You are a legal analyst assistant. Analyze user queries with provided law fragments. Use ONLY provided fragments. Reference specific laws when available. Be concise and structured."
                },
                {
                    "role": "user",
                    "content": f"User question: {user_query}\n\nLaw fragments:\n" + 
                              "\n".join([f"Fragment {i+1} - ID: {frag['metadata']['id']} - Score: {frag['score']:.3f}\n{frag['text']}\n---" 
                                       for i, frag in enumerate(search_results)])
                }
            ]

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=1500
        )

        return response.choices[0].message.content.strip()