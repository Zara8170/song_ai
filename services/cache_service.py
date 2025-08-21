import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from config.redis import redis_client, REDIS_TTL

def save_preference_cache(member_id: str, favorite_song_ids: List[int], preference: dict) -> None:
    """사용자 취향 정보를 캐시에 저장합니다."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        payload = {
            "favorite_song_ids": favorite_song_ids or [],
            "preference": preference or {},
            "generated_date": today,
        }
        redis_client.setex(f"pref:{member_id}", REDIS_TTL, json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        print(f"[CACHE] save_preference_cache error: {e}")

def load_preference_cache(member_id: str) -> Optional[dict]:
    """사용자 취향 정보를 캐시에서 로드합니다."""
    try:
        raw = redis_client.get(f"pref:{member_id}")
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        print(f"[CACHE] load_preference_cache error: {e}")
        return None

def load_recommendation_cache(member_id: str) -> Optional[dict]:
    """사용자 추천 결과를 캐시에서 로드합니다."""
    try:
        raw = redis_client.get(f"recommend:{member_id}")
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        print(f"[CACHE] load_recommendation_cache error: {e}")
        return None

def save_recommendation_cache(member_id: str, cache_data: Dict[str, Any]) -> None:
    """사용자 추천 결과를 캐시에 저장합니다."""
    try:
        redis_client.setex(f"recommend:{member_id}", REDIS_TTL, json.dumps(cache_data, ensure_ascii=False))
    except Exception as e:
        print(f"[CACHE] save_recommendation_cache error: {e}")

def clear_user_cache(member_id: str, cache_type: str = "all") -> None:
    """사용자의 특정 캐시를 삭제합니다."""
    try:
        if cache_type == "all" or cache_type == "preference":
            redis_client.delete(f"pref:{member_id}")
        if cache_type == "all" or cache_type == "recommendation":
            redis_client.delete(f"recommend:{member_id}")
    except Exception as e:
        print(f"[CACHE] clear_user_cache error: {e}")

def get_cache_stats() -> Dict[str, int]:
    """캐시 통계 정보를 반환합니다."""
    try:
        pref_keys = redis_client.keys("pref:*")
        rec_keys = redis_client.keys("recommend:*")
        return {
            "preference_cache_count": len(pref_keys),
            "recommendation_cache_count": len(rec_keys),
            "total_cache_count": len(pref_keys) + len(rec_keys)
        }
    except Exception as e:
        print(f"[CACHE] get_cache_stats error: {e}")
        return {"preference_cache_count": 0, "recommendation_cache_count": 0, "total_cache_count": 0}
