import sys
import os
 
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from typing import List, Dict
from bs4 import BeautifulSoup,XMLParsedAsHTMLWarning
from src.backend.vector_db.qdrant_manager_law import QdrantManager
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

def parsing_laws(titles: List[str], date: str, max_count: int = 10):
    API_KEYS = ["subtitle", "chapter", "subchapter", "part", "subpart", "section", "appendix"]

    qdrant_manager = QdrantManager()
    processed_count = 0
    
    for title in titles:
        print(f"Processing title {title}")
        url = f"https://www.ecfr.gov/api/versioner/v1/structure/{date}/title-{title}.json"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to fetch structure for Title {title}", response.status_code)
            continue

        data = response.json()
        
        def strip_html_tags(text: str) -> str:
            soup = BeautifulSoup(text, "lxml")
            return soup.get_text(separator="\n", strip=True)

        def build_params(path: List[Dict[str, str]]) -> Dict[str, str]:
            params = {}
            for node in path:
                t = node.get("type")
                idf = node.get("identifier")
                if not idf:
                    continue
                if t in API_KEYS:
                    params[t] = idf
            return params

        def walk(node: Dict[str, any], path: List[Dict[str, str]]):
            nonlocal processed_count 
            if processed_count >= max_count:
                return
            
            current_path = path + [node]

            if "children" in node and node["children"]:
                for child in node["children"]:
                    if processed_count >= max_count:
                        break
                    walk(child, current_path)
            else:
                if processed_count >= max_count:
                    return
                    
                params = build_params(current_path)
                if not params.get("section") and not params.get("appendix"):
                    return

                query_string = "&".join(f"{k}={v}" for k, v in params.items())
                url_xml = f"https://www.ecfr.gov/api/versioner/v1/full/{date}/title-{title}.xml?{query_string}"

                xml_response = requests.get(url_xml)
                if xml_response.status_code != 200:
                    print("Failed:", url_xml, xml_response.status_code)
                    return

                filename_parts = [title] + [v for v in params.values()]
                law_id = '_'.join(filename_parts)

                response_text = strip_html_tags(xml_response.text)
                print(f"Processing law: {law_id}")
                
                chunks_count = qdrant_manager.process_and_store_law(response_text, law_id)
                print(f"Saved {chunks_count} chunks for {law_id}")
                processed_count += 1

        for chapter in data.get("children", []):
            if processed_count >= max_count:
                break
            walk(chapter, [])

parsing_laws(titles=["26"], date="2025-01-01", max_count=10)
