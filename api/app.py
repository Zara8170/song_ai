import atexit
from fastapi import FastAPI

from services.redis_scheduler import start_scheduler, stop_scheduler
from api.routes import recommendations_router, tasks_router

def create_app() -> FastAPI:
    """FastAPI 애플리케이션을 생성하고 설정합니다."""
    
    # FastAPI 앱 생성
    app = FastAPI(
        title="AI Recommendation Server", 
        version="1.1.0",
        description="AI 기반 음악 추천 서비스"
    )
    
    # 라우터 등록
    app.include_router(recommendations_router)
    app.include_router(tasks_router)
    
    # 스케줄러 시작
    scheduler = start_scheduler()
    atexit.register(lambda: stop_scheduler(scheduler))
    
    return app
