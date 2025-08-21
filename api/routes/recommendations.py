from fastapi import APIRouter, HTTPException
from datetime import datetime

from core.recommendation_service import recommend_songs
from models.api_models import (
    RecommendationRequest, 
    RecommendationResponse,
    CachedRecommendationRequest,
    CachedRecommendationResponse
)
from services.cache_service import load_recommendation_cache, save_recommendation_cache

router = APIRouter(prefix="/recommend", tags=["recommendations"])

@router.post("", response_model=RecommendationResponse)
async def recommend(req: RecommendationRequest):
    """사용자의 좋아하는 곡을 기반으로 추천을 생성합니다."""
    try:
        result = recommend_songs(req.favorite_song_ids)
        today = datetime.now().strftime("%Y-%m-%d")
        
        cache_data = {
            "favorite_song_ids": result.get("favorite_song_ids", []),
            "groups": result.get("groups", []),
            "candidates": result.get("candidates", []),
            "generated_date": today,
        }
        
        # 캐시에 저장
        save_recommendation_cache(req.memberId, cache_data)
        
        return RecommendationResponse(
            status="completed",
            message="추천 분석 및 생성이 완료되었습니다.",
            generated_date=today
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommend error: {e}")

@router.post("/cached", response_model=CachedRecommendationResponse)
async def get_cached_recommendation(req: CachedRecommendationRequest):
    """캐시된 추천 결과를 조회합니다."""
    try:
        cached_data = load_recommendation_cache(req.memberId)
        if not cached_data:
            raise HTTPException(
                status_code=404, 
                detail="캐시된 추천 결과가 없습니다. /recommend API를 먼저 호출해주세요."
            )
        
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
