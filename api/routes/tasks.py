from fastapi import APIRouter, HTTPException

from models.api_models import FavoriteUpdate
from workers.tasks import task_analyze_preference, task_generate_recommendations, task_warm_active_users

router = APIRouter(tags=["tasks"])

@router.post("/favorites/updated")
async def favorites_updated(req: FavoriteUpdate):
    """사용자 좋아요 업데이트 시 백그라운드 분석 작업을 큐에 추가합니다."""
    try:
        task_analyze_preference.delay(req.memberId, req.favorite_song_ids)
        task_generate_recommendations.delay(req.memberId, req.favorite_song_ids)
        return {"status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Queue error: {e}")

@router.post("/warm/active")
async def warm_active(limit: int = 500):
    """활성 사용자들의 추천 캐시를 워밍합니다."""
    try:
        task = task_warm_active_users.delay(limit)
        return {"task_id": task.id, "status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Warm queue error: {e}")
