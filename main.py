from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
import uvicorn
from typing import List, Optional
from dotenv import load_dotenv
import os, json, redis, atexit
from datetime import datetime

from recommendation_service import recommend_songs
from redis_scheduler import start_scheduler, stop_scheduler
from tasks import task_analyze_preference, task_generate_recommendations, task_warm_active_users

# ==== Env & Redis 설정 ====
load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_TTL = 60 * 60 * 24 * 7  # 7일 캐시

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    db=REDIS_DB,
    decode_responses=True,
)

try:
    redis_client.ping()
except Exception as e:
    print(f"[WARN] Redis ping failed: {e}")

app = FastAPI(title="AI Recommendation Server", version="1.1.0")

scheduler = start_scheduler()
atexit.register(lambda: stop_scheduler(scheduler))

def save_preference_cache(member_id: str, favorite_song_ids: List[int], preference: dict):
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
    try:
        raw = redis_client.get(f"pref:{member_id}")
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        print(f"[CACHE] load_preference_cache error: {e}")
        return None

def load_recommendation_cache(member_id: str) -> Optional[dict]:
    try:
        raw = redis_client.get(f"recommend:{member_id}")
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        print(f"[CACHE] load_recommendation_cache error: {e}")
        return None

class RecommendationRequest(BaseModel):
    memberId: str
    favorite_song_ids: List[int] = Field(default_factory=list)

    @field_validator("favorite_song_ids", mode="before")
    @classmethod
    def _normalize_ids(cls, v):
        if v is None:
            return []
        return list(dict.fromkeys(int(x) for x in v))

class RecommendationResponse(BaseModel):
    status: str = "completed"
    message: str = "추천 분석 및 생성이 완료되었습니다."
    generated_date: str = ""

class FavoriteUpdate(BaseModel):
    memberId: str
    favorite_song_ids: List[int] = Field(default_factory=list)

class CachedRecommendationRequest(BaseModel):
    memberId: str

class CachedRecommendationResponse(BaseModel):
    favorite_song_ids: List[int] = Field(default_factory=list)
    groups: list = Field(default_factory=list)
    candidates: list = Field(default_factory=list)
    generated_date: str = ""
    cached: bool = True

@app.post("/recommend", response_model=RecommendationResponse)
async def recommend(req: RecommendationRequest):
    try:
        result = recommend_songs(req.favorite_song_ids)
        today = datetime.now().strftime("%Y-%m-%d")
        
        cache_data = {
            "favorite_song_ids": result.get("favorite_song_ids", []),
            "groups": result.get("groups", []),
            "candidates": result.get("candidates", []),
            "generated_date": today,
        }
        try:
            redis_client.setex(f"recommend:{req.memberId}", REDIS_TTL, json.dumps(cache_data, ensure_ascii=False))
        except Exception as ce:
            print(f"[CACHE] recommend cache error: {ce}")
        
        return RecommendationResponse(
            status="completed",
            message="추천 분석 및 생성이 완료되었습니다.",
            generated_date=today
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommend error: {e}")

@app.post("/recommend/cached", response_model=CachedRecommendationResponse)
async def get_cached_recommendation(req: CachedRecommendationRequest):
    try:
        cached_data = load_recommendation_cache(req.memberId)
        if not cached_data:
            raise HTTPException(status_code=404, detail="캐시된 추천 결과가 없습니다. /recommend API를 먼저 호출해주세요.")
        
        return CachedRecommendationResponse(
            favorite_song_ids=cached_data.get("favorite_song_ids", []),
            groups=cached_data.get("groups", []),
            candidates=cached_data.get("candidates", []),
            generated_date=cached_data.get("generated_date", ""),
            cached=True
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cached recommendation error: {e}")



@app.post("/favorites/updated")
async def favorites_updated(req: FavoriteUpdate):
    try:
        task_analyze_preference.delay(req.memberId, req.favorite_song_ids)
        task_generate_recommendations.delay(req.memberId, req.favorite_song_ids)
        return {"status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Queue error: {e}")

@app.post("/warm/active")
async def warm_active(limit: int = 500):
    try:
        task = task_warm_active_users.delay(limit)
        return {"task_id": task.id, "status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Warm queue error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
