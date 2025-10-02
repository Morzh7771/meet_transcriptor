from typing import Dict, Any, List, Optional
import re
from datetime import datetime
from src.backend.vector_db.vectorizer import TextVectorizer   
from src.backend.vector_db.qdrant_manager import QdrantManager   
from src.backend.utils.configs import Config   
from rank_bm25 import BM25Okapi

class SearchService:
    def __init__(self):
        config = Config.load_config()  # Use the same pattern as other files
        self.vectorizer = TextVectorizer()
        self.qdrant = QdrantManager(config.vectordb.URL, config.vectordb.API_KEY.get_secret_value())
        self.collection_name = "meetings"
        
        # Search configuration
        self.search_limits = {
            "meeting_count": 75,
            "time_filter": lambda limit: (limit * 5) if limit else 500,
            "default": lambda limit: (limit * 3) if limit else 300
        }
    
    def search(self, query: str, limit: int = None, filters: Dict[str, Any] = None) -> List[Dict]:
        """Main search method with hybrid ranking"""
        # Handle tag fallback and build filters
        filters = self._handle_tag_fallback(filters or {})
        qdrant_filter = self._build_qdrant_filters(filters)

 

        # Get semantic search results
        search_limit = self._determine_search_limit(filters, limit)
        results = self._perform_semantic_search(query, search_limit, qdrant_filter)
        
        if not results:
            return []
        
        # Apply BM25 ranking for multiple results
        if len(results) > 1:
            results = self._apply_hybrid_ranking(query, results)
        
        # Apply post-search filters
        results = self._apply_post_filters(results, filters)
        
        return self._format_results(results[:limit] if limit else results)
    
    def _handle_tag_fallback(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Remove tag filter if no matches found"""
        tags_filter = filters.get("tags")
        if tags_filter and not self._tags_exist(tags_filter):
            filters = {k: v for k, v in filters.items() if k != "tags"}
            print(f"No meetings found with tag '{tags_filter}', searching without tag filter")
        return filters
    
    def _determine_search_limit(self, filters: Dict[str, Any], limit: int) -> int:
        """Calculate appropriate search limit"""
        if filters.get("meeting_count"):
            return self.search_limits["meeting_count"]
        elif filters.get("time_filter"):
            return self.search_limits["time_filter"](limit)
        else:
            return self.search_limits["default"](limit)
    
    def _perform_semantic_search(self, query: str, limit: int, qdrant_filter: List[Dict]):
        """Execute semantic search"""
        query_vector = self.vectorizer.vectorize(query)
        return self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_vector.tolist(),
            limit=limit,
            filter_conditions=qdrant_filter if qdrant_filter else None
        )
    
    def _apply_hybrid_ranking(self, query: str, results) -> List:
        """Combine semantic and BM25 scores (70% semantic + 30% BM25)"""
        texts = [result.payload["chunk_text"] for result in results]
        tokenized_texts = [self._tokenize(text) for text in texts]
        
        bm25 = BM25Okapi(tokenized_texts)
        bm25_scores = bm25.get_scores(self._tokenize(query))
        
        # Normalize scores
        max_semantic = max(result.score for result in results)
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1
        
        for i, result in enumerate(results):
            semantic_norm = result.score / max_semantic
            bm25_norm = bm25_scores[i] / max_bm25
            result.score = 0.7 * semantic_norm + 0.3 * bm25_norm
        
        return sorted(results, key=lambda x: x.score, reverse=True)
    
    def _tokenize(self, text: str) -> List[str]:
        """Clean and tokenize text for BM25"""
        return re.sub(r'[^\w\s]', ' ', text.lower()).split()
    
    def _build_qdrant_filters(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build Qdrant filter conditions"""
        if not filters:
            return []

        qdrant_filters = []
        skip_keys = {"time_filter", "search_scope", "meeting_count", "time_start", "time_end", "time_range"}
        
        for key, value in filters.items():
            if value in (None, "") or key in skip_keys:
                continue
            
            filter_condition = self._create_filter_condition(key, value)
            if isinstance(filter_condition, list):
                qdrant_filters.extend(filter_condition)
            else:
                qdrant_filters.append(filter_condition)

        return qdrant_filters
    
    def _create_filter_condition(self, key: str, value: Any) -> Dict[str, Any]:
        """Create individual filter condition"""
        filter_creators = {
            "meeting_id": lambda v: {"key": key, "match": {"value": v}},
            "client_id": lambda v: {"key": "client_id", "match": {"value": v}},
            "consultant_id": lambda v: {"key": "consultant_id", "match": {"value": v}},
            "date_start": lambda v: {"key": "date_start", "range": {"gte": self._normalize_date(v)}},
            "date_end": lambda v: {"key": "date_start", "range": {"lte": self._normalize_date(v, True)}},
            "title": lambda v: {"key": key, "match": {"text": v}},
        }
        
        if key in filter_creators:
            return filter_creators[key](value)
        elif key in ["participants", "tags"]:
            return self._create_list_filter(key, value)
        else:
            # Generic filter
            match_type = {"any": value} if isinstance(value, list) else {"value": value}
            return {"key": key, "match": match_type}
    
    def _create_list_filter(self, key: str, value: Any) -> List[Dict]:
        """Create filters for list-type fields"""
        items = value if isinstance(value, list) else re.split(r"[,\|\;]+", str(value))
        items = [item.strip() for item in items if item.strip()]
        
        if key == "participants":
            # AND logic for participants
            return [{"key": key, "match": {"value": item}} for item in items]
        else:  # tags
            # OR logic for tags
            match_type = {"value": items[0]} if len(items) == 1 else {"any": items}
            return [{"key": key, "match": match_type}]
    
    def _normalize_date(self, value: Any, end: bool = False) -> str:
        """Convert date to ISO format"""
        date_str = str(value)
        if "T" in date_str:
            return date_str
        return f"{date_str}T{'23:59:59' if end else '00:00:00'}"
    
    def _apply_post_filters(self, results, filters: Dict[str, Any]):
        """Apply time and meeting count filters after search"""
        results = self._filter_by_time(results, filters)
        
        if filters.get("time_filter") or filters.get("meeting_count"):
            results = self._filter_by_meeting_count(results, filters)
        
        return results
    
    def _filter_by_time(self, results, filters: Dict[str, Any]):
        """Filter results by meeting time"""
        time_start = filters.get("time_start")
        time_end = filters.get("time_end")
        
        if not time_start and not time_end:
            return results
        
        return [r for r in results if self._meeting_matches_time(r.payload, time_start, time_end)]
    
    def _meeting_matches_time(self, payload: Dict, time_start: str, time_end: str) -> bool:
        """Check if meeting time matches filter criteria"""
        date_start = payload.get("date_start")
        if not date_start:
            return False
        
        try:
            meeting_start = datetime.fromisoformat(date_start.replace('Z', '+00:00'))
            meeting_start_time = meeting_start.strftime("%H:%M")
            
            meeting_end_time = None
            if payload.get("date_end"):
                meeting_end = datetime.fromisoformat(payload["date_end"].replace('Z', '+00:00'))
                meeting_end_time = meeting_end.strftime("%H:%M")
            
            return self._time_overlaps(meeting_start_time, meeting_end_time, time_start, time_end)
            
        except Exception:
            return True  # Include if parsing fails
    
    def _time_overlaps(self, meeting_start: str, meeting_end: str, filter_start: str, filter_end: str) -> bool:
        """Check if meeting time overlaps with filter time"""
        if filter_start and filter_end:
            if filter_start == filter_end:   
                if meeting_end:
                    return meeting_start <= filter_start <= meeting_end
                else:
                    return meeting_start == filter_start
            else:   
                if meeting_end:
                    return meeting_start <= filter_end and meeting_end >= filter_start
                else:
                    return filter_start <= meeting_start <= filter_end
        elif filter_start:
            return meeting_start >= filter_start
        elif filter_end:
            if meeting_end:
                return meeting_end <= filter_end
            else:
                return meeting_start <= filter_end
        return True
    
    def _filter_by_meeting_count(self, results, filters: Dict[str, Any]):
        """Apply meeting count and temporal ordering"""
        if not results:
            return results
        
        # Group results by meeting_id
        meetings = {}
        for result in results:
            meeting_id = result.payload["meeting_id"]
            meetings.setdefault(meeting_id, []).append(result)
        
        # Sort meetings by date
        time_filter = filters.get("time_filter")
        meeting_count = filters.get("meeting_count", 1)
        
        reverse_sort = time_filter != "earliest"
        sorted_meeting_ids = sorted(
            meetings.keys(),
            key=lambda mid: meetings[mid][0].payload.get("date_start", "1900-01-01T00:00:00"),
            reverse=reverse_sort
        )
        
        # Apply meeting count limit
        if time_filter in ["latest", "earliest"] or meeting_count > 1:
            selected_meetings = sorted_meeting_ids[:meeting_count]
            return [chunk for mid in selected_meetings for chunk in meetings[mid]]
        
        # Return all results sorted by date
        all_results = [chunk for chunks in meetings.values() for chunk in chunks]
        return sorted(all_results, 
                     key=lambda r: r.payload.get("date_start", "1900-01-01T00:00:00"), 
                     reverse=True)
    
    def _tags_exist(self, tags: str) -> bool:
        """Check if meetings exist with specified tags"""
        if not tags:
            return True
        
        tag_filter = [{"key": "tags", "match": {"value": tags}}]
        results = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=[0.0] * 1536,   
            limit=1,
            filter_conditions=tag_filter
        )
        return len(results) > 0
    
    def _format_results(self, results) -> List[Dict]:
        """Format search results for output"""
        formatted = []
        for result in results:
            payload = result.payload
            formatted.append({
                "score": result.score,
                "text": payload["chunk_text"],
                "metadata": {
                    "meeting_id": payload["meeting_id"],
                    "client_id": payload.get("client_id", ""),
                    "consultant_id": payload.get("consultant_id", ""),
                    "title": payload.get("title", ""),
                    "summary": payload.get("summary", ""),
                    "date_start": payload.get("date_start", ""),
                    "date_end": payload.get("date_end", ""),
                    "duration": payload.get("duration"),
                    "overview": payload.get("overview", ""),
                    "notes": payload.get("notes", ""),
                    "action_items": payload.get("action_items", ""),
                    "language": payload.get("language", ""),
                    "tags": payload.get("tags", ""),
                    "participants": payload.get("participants", ""),
                    "chunk": payload.get("chunk", 0),
                    "total_chunks": payload.get("total_chunks", 1),
                }
            })
        return formatted