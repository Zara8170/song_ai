from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
import uvicorn
from typing import List, Optional
from dotenv import load_dotenv
import os, json, redis, atexit
from datetime import datetime

# 내부 모듈
from recommendation_service import recommend_songs
from database_service import get_favorite_songs_info
from ai_service import _analyze_user_preference, _make_tagline
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

# Redis 연결 체크
try:
    redis_client.ping()
except Exception as e:
    print(f"[WARN] Redis ping failed: {e}")

# ==== FastAPI 앱 ====
app = FastAPI(title="AI Recommendation Server", version="1.1.0")

scheduler = start_scheduler()
atexit.register(lambda: stop_scheduler(scheduler))

# ==== 캐시 함수 ====
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

# ==== 모델 ====
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
    favorite_song_ids: List[int] = Field(default_factory=list)
    groups: list = Field(default_factory=list)
    candidates: list = Field(default_factory=list)
    generated_date: str = ""

class AnalyzePreferenceRequest(BaseModel):
    memberId: str
    favorite_song_ids: List[int] = Field(default_factory=list)

class AnalyzePreferenceResponse(BaseModel):
    preferred_genres: List[str] = Field(default_factory=list)
    preferred_moods: List[str] = Field(default_factory=list)
    overall_taste: str = ""
    favorite_artists: List[str] = Field(default_factory=list)

class SongLite(BaseModel):
    title_kr: Optional[str] = ""
    title_en: Optional[str] = ""
    title_jp: Optional[str] = ""
    artist_kr: Optional[str] = ""
    artist: Optional[str] = ""

class GenerateTaglineRequest(BaseModel):
    label: str = Field(..., description="그룹 라벨 (예: '서정적', 'J-pop')")
    songs: List[SongLite] = Field(default_factory=list)
    user_preference: Optional[AnalyzePreferenceResponse] = None

class GenerateTaglineResponse(BaseModel):
    label: str
    tagline: str

class FavoriteUpdate(BaseModel):
    memberId: str
    favorite_song_ids: List[int] = Field(default_factory=list)

# ==== API 엔드포인트 ====
@app.post("/recommend", response_model=RecommendationResponse)
async def recommend(req: RecommendationRequest):
    try:
        result = recommend_songs(req.favorite_song_ids)
        today = datetime.now().strftime("%Y-%m-%d")
        payload = RecommendationResponse(
            favorite_song_ids=result.get("favorite_song_ids", []),
            groups=result.get("groups", []),
            candidates=result.get("candidates", []),
            generated_date=today,
        )
        try:
            redis_client.setex(f"recommend:{req.memberId}", REDIS_TTL, payload.model_dump_json())
        except Exception as ce:
            print(f"[CACHE] recommend cache error: {ce}")
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommend error: {e}")

@app.post("/preference/analyze", response_model=AnalyzePreferenceResponse)
async def analyze_preference_api(req: AnalyzePreferenceRequest):
    try:
        if not req.favorite_song_ids:
            raise HTTPException(status_code=400, detail="favorite_song_ids가 비어 있습니다.")
        fav_songs = get_favorite_songs_info(req.favorite_song_ids)
        pref = _analyze_user_preference(fav_songs)
        if not pref or not isinstance(pref, dict):
            raise HTTPException(status_code=500, detail="취향분석 실패")
        save_preference_cache(req.memberId, req.favorite_song_ids, pref)
        return AnalyzePreferenceResponse(**pref)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preference analyze error: {e}")

@app.post("/tagline/generate", response_model=GenerateTaglineResponse)
async def generate_tagline_api(req: GenerateTaglineRequest):
    try:
        if not req.label:
            raise HTTPException(status_code=400, detail="label은 필수입니다.")
        songs_payload = [s.model_dump() for s in req.songs]
        upref = req.user_preference.model_dump() if req.user_preference else None
        tagline = _make_tagline(req.label, songs_payload, upref)
        if not tagline or not isinstance(tagline, str):
            raise HTTPException(status_code=500, detail="태그라인 생성 실패")
        return GenerateTaglineResponse(label=req.label, tagline=tagline)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tagline generate error: {e}")

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
