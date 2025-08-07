from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
import uvicorn
from typing import List
from dotenv import load_dotenv
import os, json, redis, atexit, time
from datetime import datetime
from random import sample

from tools import recommend_songs
from redis_scheduler import start_scheduler, stop_scheduler

load_dotenv()

REDIS_TTL = 60 * 60 * 24 * 7  # 7일

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"), 
    decode_responses=True,
)

print(redis_client.ping())

app = FastAPI()

scheduler = start_scheduler()
    
atexit.register(lambda: stop_scheduler(scheduler))

class RecommendationRequest(BaseModel):
    memberId: str
    favorite_song_ids: List[int] = Field(default_factory=list)

    @field_validator("favorite_song_ids", mode="before")
    @classmethod
    def _cast_str_to_int(cls, v):
        if isinstance(v, list):
            return [int(x) for x in v if isinstance(x, (int, str)) and str(x).isdigit()]
        return v


def check_preference_cache(member_id: str, favorite_song_ids: list[int]) -> tuple[dict, bool]:
    """preference 캐시 확인 및 즐겨찾기 목록 비교 (하루에 한번만 새로 생성)"""
    pref_key = f"preference:{member_id}"
    cached = redis_client.get(pref_key)
    
    if not cached:
        return None, False
    
    try:
        pref_data = json.loads(cached)
        cached_favorites = pref_data.get("favorite_song_ids", [])
        generated_date = pref_data.get("generated_date")
        today = datetime.now().strftime("%Y-%m-%d")
        
        if generated_date == today:
            return pref_data.get("preference"), True
        
        if set(cached_favorites) == set(favorite_song_ids):
            return pref_data.get("preference"), True
        else:
            redis_client.delete(pref_key)
            redis_client.delete(f"recommend:{member_id}")
            return None, False
    except:
        return None, False

def save_preference_cache(member_id: str, favorite_song_ids: list[int], preference: dict):
    """preference 캐시 저장"""
    pref_key = f"preference:{member_id}"
    today = datetime.now().strftime("%Y-%m-%d")
    pref_data = {
        "favorite_song_ids": favorite_song_ids,
        "preference": preference,
        "generated_date": today
    }
    redis_client.setex(pref_key, REDIS_TTL, json.dumps(pref_data, ensure_ascii=False))

@app.get("/")
def read_root():
    return {"message": "AI Song Recommender is running!"}


@app.post("/recommend")
async def recommend(request: RecommendationRequest):
    try:
        memberId = request.memberId
        favorite_song_ids = request.favorite_song_ids
        
        # 1. recommend 캐시 먼저 확인 (모든 사용자에 대해)
        cache_key = f"recommend:{memberId}"
        cached = redis_client.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                recommend_date = data.get("generated_date")
                today = datetime.now().strftime("%Y-%m-%d")
                
                # 같은 날짜에 생성된 추천이면 재사용
                if recommend_date == today:
                    candidates = data.get("candidates", [])
                    random_candidates = sample(candidates, min(12, len(candidates))) if len(candidates) > 0 else []
                    
                    return {
                        "groups": data["recommendations"]["groups"],
                        "candidates": random_candidates
                    }
                else:
                    # 날짜가 다르면 캐시 삭제
                    redis_client.delete(cache_key)
            except:
                # 캐시 파싱 오류시 삭제
                redis_client.delete(cache_key)
        
        # 2. preference 캐시 확인 (좋아요가 있는 사용자만)
        cached_preference = None
        if favorite_song_ids:  # 좋아요가 있는 경우에만
            cached_preference, is_cache_valid = check_preference_cache(memberId, favorite_song_ids)
        
        # 3. 새로운 추천 생성
        if cached_preference:
            # preference 재사용해서 추천만 새로 생성
            result = recommend_songs(favorite_song_ids, cached_preference)
        else:
            # preference부터 새로 분석 (또는 좋아요가 없는 경우)
            result = recommend_songs(favorite_song_ids)
            
            # 새로운 preference가 생성되었으면 캐시 저장
            if "preference" in result and favorite_song_ids:
                save_preference_cache(memberId, favorite_song_ids, result["preference"])
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        # 4. recommend 캐시 저장
        today = datetime.now().strftime("%Y-%m-%d")
        payload = {
            "favorites": favorite_song_ids, 
            "recommendations": {"groups": result["groups"]},
            "candidates": result["candidates"],
            "generated_date": today
        }
        redis_client.setex(cache_key, REDIS_TTL, json.dumps(payload, ensure_ascii=False))
        
        # 5. 응답 반환
        candidates = result["candidates"]
        random_candidates = sample(candidates, min(12, len(candidates))) if len(candidates) > 0 else []
        
        return {
            "groups": result["groups"],
            "candidates": random_candidates
        }

    except Exception as e:
        print(f"An error occurred during recommendation: {e}")
        raise HTTPException(status_code=500, detail=f"Recommendation error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
