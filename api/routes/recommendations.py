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
        # 먼저 Redis 캐시에서 기존 추천 결과 확인
        cached_data = load_recommendation_cache(req.memberId)
        
        if cached_data:
            # 캐시된 데이터의 favorite_song_ids와 현재 요청이 동일한지 확인
            cached_favorites = cached_data.get("favorite_song_ids", [])
            current_favorites = req.favorite_song_ids or []
            
            # 정렬하여 비교 (순서 무관)
            if sorted(cached_favorites) == sorted(current_favorites):
                # 캐시된 데이터가 유효하면 바로 반환
                return RecommendationResponse(
                    status="completed",
                    message="캐시된 추천 결과를 반환합니다.",
                    generated_date=cached_data.get("generated_date", datetime.now().strftime("%Y-%m-%d"))
                )
        
        # 캐시된 데이터가 없으면 새로 분석 수행
        result = recommend_songs(req.favorite_song_ids)
        today = datetime.now().strftime("%Y-%m-%d")
        
        cache_data = {
            "favorite_song_ids": result.get("favorite_song_ids", []),
            "groups": result.get("groups", []),
            "candidates": result.get("candidates", []),
            "generated_date": today,
        }
        
        # 새로 생성한 결과를 캐시에 저장
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
