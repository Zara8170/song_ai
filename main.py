from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
import uvicorn
from typing import List
from dotenv import load_dotenv
import os, json, redis, atexit, time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from tools import recommend_songs

load_dotenv()

REDIS_TTL = 60 * 60 * 24 * 7 # 7 days

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"), 
    decode_responses=True,
)

print(redis_client.ping())

app = FastAPI()

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
            return json.loads(cached)
        
        result = recommend_songs(favorite_song_ids)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        payload = {"favorites": favorite_song_ids, "recommendations": result}
        redis_client.setex(cache_key, REDIS_TTL, json.dumps(payload, ensure_ascii=False))
        return result

    except Exception as e:
        print(f"An error occurred during recommendation: {e}")
        raise HTTPException(status_code=500, detail=f"Recommendation error: {e}")
    
scheduler = BackgroundScheduler(timezone=timezone("Asia/Seoul"))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
