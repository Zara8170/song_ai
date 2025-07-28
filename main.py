from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
import uvicorn
from typing import List
from dotenv import load_dotenv
import os, json, redis, atexit, time
from random import sample

from tools import recommend_songs
from redis_scheduler import start_scheduler, stop_scheduler

load_dotenv()

REDIS_TTL = 60 * 60 * 24  # 1일 (24시간)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"), 
    decode_responses=True,
)

print(redis_client.ping())

app = FastAPI()

# Redis 스케줄러 시작
scheduler = start_scheduler()

# 애플리케이션 종료 시 스케줄러도 중지
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


@app.get("/")
def read_root():
    return {"message": "AI Song Recommender is running!"}


@app.post("/recommend")
async def recommend(request: RecommendationRequest):
    try:
        memberId = request.memberId
        favorite_song_ids = request.favorite_song_ids
        cache_key = f"recommend:{memberId}"

        cached = redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            candidates = data.get("candidates", [])
            
            # 후보곡 중 9개 랜덤 선택 (후보곡이 9개 미만이면 전체 반환)
            random_candidates = sample(candidates, min(9, len(candidates))) if len(candidates) > 0 else []
            
            return {
                "groups": data["recommendations"]["groups"],
                "candidates": random_candidates
            }
        
        result = recommend_songs(favorite_song_ids)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        # 후보곡을 포함한 payload로 캐시 저장
        payload = {
            "favorites": favorite_song_ids, 
            "recommendations": {"groups": result["groups"]},
            "candidates": result["candidates"]
        }
        redis_client.setex(cache_key, REDIS_TTL, json.dumps(payload, ensure_ascii=False))
        
        # 응답에 후보곡 9개 랜덤 선택해서 포함
        candidates = result["candidates"]
        random_candidates = sample(candidates, min(9, len(candidates))) if len(candidates) > 0 else []
        
        return {
            "groups": result["groups"],
            "candidates": random_candidates
        }

    except Exception as e:
        print(f"An error occurred during recommendation: {e}")
        raise HTTPException(status_code=500, detail=f"Recommendation error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
