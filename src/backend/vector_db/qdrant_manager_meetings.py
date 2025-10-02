from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union
from datetime import datetime, time, timezone
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams,PointStruct,PayloadSchemaType

def _to_datetime(value: Union[str, datetime]) -> datetime:
 
    if isinstance(value, datetime):
        return value

    s = str(value).strip()
    if not s:
        raise ValueError("Empty datetime string")

    # 'Z' -> '+00:00'
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    # If only the date has arrived, we will add the start time of the day
    if "T" not in s:
        # YYYY-MM-DD
        return datetime.fromisoformat(s + "T00:00:00")

    return datetime.fromisoformat(s)


def _is_datetime_key(key: str) -> bool:
    """
    Heuristic: For keys containing 'date', use DatetimeRange.
    Suitable for 'date_start', 'date_end', 'date', etc.
    """
    return "date" in key.lower()


class QdrantManager:
    def __init__(self, url: str, timeout: int = 60) -> None:
        self.client = QdrantClient(url=url, timeout=timeout)
 

    def create_collection(self, collection_name: str, vector_size: int) -> None:
        """
        Creates a collection (if it doesn't exist) and indexes on useful fields.
        """
        # Idempotent: if the collection already exists, Qdrant will return 409, which is ok.
        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        except Exception:
           # Already exists - skip
            pass

        self._create_payload_indexes(collection_name)

    def _create_payload_indexes(self, collection_name: str) -> None:
        """
        Indexes on frequently used fields in payload.
        """
        index_fields: List[Tuple[str, PayloadSchemaType]] = [
            ("meeting_id", PayloadSchemaType.KEYWORD),
            ("client_id", PayloadSchemaType.KEYWORD),
            ("consultant_id", PayloadSchemaType.KEYWORD),
            ("date_start", PayloadSchemaType.DATETIME),
            ("date_end", PayloadSchemaType.DATETIME),
            ("duration", PayloadSchemaType.INTEGER),
            ("title", PayloadSchemaType.TEXT),
            ("tags", PayloadSchemaType.KEYWORD),
            ("summary", PayloadSchemaType.TEXT),
            ("overview", PayloadSchemaType.TEXT),
            ("notes", PayloadSchemaType.TEXT),
            ("action_items", PayloadSchemaType.TEXT),
            ("participants", PayloadSchemaType.KEYWORD),
            ("chunk", PayloadSchemaType.INTEGER),
            ("total_chunks", PayloadSchemaType.INTEGER),
            ("language", PayloadSchemaType.KEYWORD),
            ("chunk_text", PayloadSchemaType.TEXT),
        ]

        for field_name, field_type in index_fields:
            try:
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=models.PayloadSchemaType(field_type),
                )
            except Exception:
                # The index already exists or the field is missing in some points - this is not critical.
                pass
 
    def upsert_points(
        self,
        collection_name: str,
        embeddings: Sequence[Sequence[float]],
        payloads: Sequence[Dict[str, Any]],
        ids: Optional[Sequence[Union[str, int]]] = None,
        wait: bool = True,
    ) -> None:
        """
        Writes a batch of points. IDs are optional (if not passed - will be UUID4).
        """
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in embeddings]
        if len(ids) != len(embeddings) or len(payloads) != len(embeddings):
            raise ValueError("Lengths of ids, embeddings, and payloads must match")

        points: List[PointStruct] = []
        for pid, vec, pl in zip(ids, embeddings, payloads):
            points.append(PointStruct(id=pid, vector=list(vec), payload=pl))

        self.client.upsert(
            collection_name=collection_name,
            points=points,
            wait=wait,
        )

 
    def search(
        self,
        collection_name: str,
        query_vector: Sequence[float],
        limit: int = 50,
        filter_conditions: Optional[List[Dict[str, Any]]] = None,
        with_payload: Union[bool, List[str]] = True,
        with_vectors: bool = False,
        score_threshold: Optional[float] = None,
    ):
 
 
        query_filter = self._build_filter(filter_conditions) if filter_conditions else None

        return self.client.search(
            collection_name=collection_name,
            query_vector=list(query_vector),
            limit=limit,
            with_payload=with_payload,
            with_vectors=with_vectors,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )
 

    def delete_by_filter(
        self,
        collection_name: str,
        filter_conditions: List[Dict[str, Any]],
    ) -> bool:
 
        try:
            flt = self._build_filter(filter_conditions)
            if flt is None:
                return False
            self.client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(filter=flt),
                wait=True,
            )
            return True
        except Exception as e:
            print(f"Error deleting points: {e}")
            return False

 
    def _build_filter(self, filter_conditions: List[Dict[str, Any]]) -> Optional[models.Filter]:
 
        if not filter_conditions:
            return None

        must_conditions: List[models.FieldCondition] = []

        for cond in filter_conditions:
            key = cond.get("key")
            if not key:
                continue

            # Match
            if "match" in cond and isinstance(cond["match"], dict):
                match_dict = cond["match"]
                if "any" in match_dict:
                    
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchAny(any=match_dict["any"]),
                        )
                    )
                elif "value" in match_dict:
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=match_dict["value"]),
                        )
                    )
                else:
                    # unknown match format - skip
                    continue
                continue

            # Range
            if "range" in cond and isinstance(cond["range"], dict):
                range_dict = cond["range"]

                # Determining the type of range
                if _is_datetime_key(key):
                    # We convert all boundaries to datetime
                    dt_kwargs: Dict[str, datetime] = {}
                    for bound in ("gte", "lte", "gt", "lt"):
                        if bound in range_dict and range_dict[bound] is not None:
                            dt_kwargs[bound] = _to_datetime(range_dict[bound])

                    # If only 'YYYY-MM-DD' was transmitted and this is the upper limit (lte),
                    # we will extend it to the end of the day.
                    if "lte" in dt_kwargs and isinstance(range_dict.get("lte"), str):
                        s = range_dict["lte"]
                        if "T" not in s:   
                            end_of_day = dt_kwargs["lte"].replace(
                                hour=23, minute=59, second=59, microsecond=999000
                            )
                            dt_kwargs["lte"] = end_of_day

                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            range=models.DatetimeRange(**dt_kwargs),
                        )
                    )
                else:
                    num_kwargs: Dict[str, Union[int, float]] = {}
                    for bound in ("gte", "lte", "gt", "lt"):
                        if bound in range_dict and range_dict[bound] is not None:
                            num_kwargs[bound] = range_dict[bound]
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            range=models.Range(**num_kwargs),
                        )
                    )

        return models.Filter(must=must_conditions) if must_conditions else None
