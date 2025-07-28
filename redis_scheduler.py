import os
import redis
import logging
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from dotenv import load_dotenv
from recommendation_service import recommend_songs
from database_service import get_all_active_users_with_favorites

load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis 클라이언트 설정
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"), 
    decode_responses=True,
)

def regenerate_all_recommendations():
    """
    매일 새벽 3시에 실행되는 추천 캐시 삭제 및 재생성 함수
    """
    try:
        # 1. 기존 캐시 삭제
        pattern = "recommend:*"
        keys = redis_client.keys(pattern)
        
        if keys:
            deleted_count = redis_client.delete(*keys)
            logger.info(f"🗑️ 기존 캐시 삭제 완료: {deleted_count}개 키 삭제")
        else:
            logger.info("📝 삭제할 기존 캐시가 없습니다")
        
        # 2. DB에서 USER 역할의 활성 사용자 정보 가져오기
        logger.info("🔍 DB에서 활성 사용자 정보 수집 중...")
        user_favorites = get_all_active_users_with_favorites()
        
        if not user_favorites:
            logger.warning("⚠️ DB에서 활성 사용자를 찾을 수 없습니다")
            return
        
        logger.info(f"👥 {len(user_favorites)}명의 활성 사용자 발견")
        
        # 3. 새로운 추천 생성 및 저장
        logger.info(f"🎵 {len(user_favorites)}명의 사용자를 위한 새로운 추천 생성 중...")
        
        success_count = 0
        fail_count = 0
        
        for member_id, favorite_song_ids in user_favorites.items():
            try:
                # 새로운 추천 + 후보곡 생성
                result = recommend_songs(favorite_song_ids)
                
                if "error" not in result:
                    # 새로운 캐시 저장 (1일 TTL) - 후보곡 포함
                    cache_key = f"recommend:{member_id}"
                    payload = {
                        "favorites": favorite_song_ids, 
                        "recommendations": {"groups": result["groups"]},
                        "candidates": result["candidates"]
                    }
                    redis_client.setex(cache_key, 60 * 60 * 24, json.dumps(payload, ensure_ascii=False))
                    success_count += 1
                    logger.debug(f"✅ 사용자 {member_id} 추천+후보곡 생성 완료 (좋아요: {len(favorite_song_ids)}개, 후보곡: {len(result.get('candidates', []))}개)")
                else:
                    logger.warning(f"⚠️ 추천 생성 실패 (사용자: {member_id}): {result.get('error')}")
                    fail_count += 1
                    
            except Exception as e:
                logger.error(f"❌ 추천 생성 중 오류 (사용자: {member_id}): {e}")
                fail_count += 1
        
        logger.info(f"✅ 추천+후보곡 재생성 완료 - 성공: {success_count}명, 실패: {fail_count}명")
        logger.info("🎉 Redis 캐시 갱신 작업 완료!")
            
    except Exception as e:
        logger.error(f"❌ Redis 캐시 갱신 중 전체 오류 발생: {e}")

def clear_recommendation_cache():
    """
    기존 캐시 삭제만 하는 함수 (백업용)
    """
    try:
        pattern = "recommend:*"
        keys = redis_client.keys(pattern)
        
        if keys:
            deleted_count = redis_client.delete(*keys)
            logger.info(f"✅ Redis 추천 캐시 정리 완료: {deleted_count}개 키 삭제")
        else:
            logger.info("📝 삭제할 추천 캐시가 없습니다")
            
    except Exception as e:
        logger.error(f"❌ Redis 캐시 정리 중 오류 발생: {e}")

def start_scheduler():
    """
    스케줄러 시작 함수
    """
    scheduler = BackgroundScheduler(timezone=timezone("Asia/Seoul"))
    
    # 매일 새벽 3시에 캐시 삭제 및 재생성 작업 스케줄링
    scheduler.add_job(
        func=regenerate_all_recommendations,
        trigger=CronTrigger(hour=3, minute=0),  # 매일 오전 3시
        id='regenerate_redis_cache',
        name='Redis 추천+후보곡 캐시 재생성',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("🕐 Redis 스케줄러가 시작되었습니다 (매일 새벽 3시 캐시 재생성)")
    
    return scheduler

def stop_scheduler(scheduler):
    """
    스케줄러 중지 함수
    """
    if scheduler:
        scheduler.shutdown()
        logger.info("⏹️  Redis 스케줄러가 중지되었습니다")

# 테스트용 함수들
def test_cache_clear():
    """
    캐시 정리 함수 테스트 (개발용)
    """
    logger.info("🧪 캐시 정리 테스트 실행...")
    clear_recommendation_cache()

def test_regenerate():
    """
    캐시 재생성 함수 테스트 (개발용)
    """
    logger.info("🧪 캐시 재생성 테스트 실행...")
    regenerate_all_recommendations()

def test_user_fetch():
    """
    사용자 정보 가져오기 테스트 (개발용)
    """
    logger.info("🧪 사용자 정보 가져오기 테스트 실행...")
    users = get_all_active_users_with_favorites()
    logger.info(f"📊 총 {len(users)}명의 활성 사용자 발견")
    for member_id, favorites in list(users.items())[:3]:  # 처음 3명만 출력
        logger.info(f"👤 사용자 {member_id}: {len(favorites)}개 좋아요")

if __name__ == "__main__":
    # 직접 실행 시 테스트
    test_user_fetch() 