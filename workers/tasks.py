import json, os, redis
from datetime import datetime
from workers.celery_app import celery
from core.recommendation_service import recommend_songs
from services.database_service import get_all_active_users_with_favorites, get_favorite_songs_info
from services.ai_service import _analyze_user_preference

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True,
)

REDIS_TTL = 60 * 60 * 24 * 7

def _cache_recommendations(member_id: str, favorite_song_ids: list[int], result: dict):
    today = datetime.now().strftime("%Y-%m-%d")
    payload = {
        "favorite_song_ids": result.get("favorite_song_ids", []),
        "groups": result.get("groups", []),
        "candidates": result.get("candidates", []),
        "generated_date": today,
    }
    redis_client.setex(f"recommend:{member_id}", REDIS_TTL, json.dumps(payload, ensure_ascii=False))

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def task_analyze_preference(self, member_id: str, favorite_song_ids: list[int]):
    if not favorite_song_ids:
        return None
    fav_songs = get_favorite_songs_info(favorite_song_ids)
    pref = _analyze_user_preference(fav_songs)
    if pref:
        try:
            from services.cache_service import save_preference_cache
            save_preference_cache(member_id, favorite_song_ids, pref)
        except Exception:
            pass
    return pref

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def task_generate_recommendations(self, member_id: str, favorite_song_ids: list[int]):
    result = recommend_songs(favorite_song_ids)
    if isinstance(result, dict) and "groups" in result:
        _cache_recommendations(member_id, favorite_song_ids, result)
    return True

@celery.task
def task_warm_active_users(limit: int = 1000):
    user_map = get_all_active_users_with_favorites()
    count = 0
    for member_id, fav_ids in user_map.items():
        if count >= limit:
            break
        (task_analyze_preference.s(member_id, fav_ids) | task_generate_recommendations.s(member_id, fav_ids)).apply_async()
        count += 1
    return {"scheduled": count}
