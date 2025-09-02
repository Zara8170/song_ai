import os
import redis
import logging
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from dotenv import load_dotenv
from services.database_service import get_all_active_users_with_favorites

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    start_time = datetime.now()
    logger.info("🚀 Redis 추천+취향 캐시 재생성 작업 시작")
    logger.info(f"⏰ 작업 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 1단계: 추천 캐시 삭제
        logger.info("📋 1단계: 기존 추천 캐시 삭제 중...")
        recommend_keys = redis_client.keys("recommend:*")
        
        if recommend_keys:
            deleted_count = redis_client.delete(*recommend_keys)
            logger.info(f"🗑️ 추천 캐시 삭제 완료: {deleted_count}개 키 삭제")
        else:
            logger.info("📝 삭제할 추천 캐시가 없습니다")
        
        # 2단계: 취향 캐시 확인
        logger.info("📋 2단계: 기존 취향 캐시 확인 중...")
        preference_keys = redis_client.keys("preference:*")
        logger.info(f"💾 취향 캐시 유지: {len(preference_keys)}개 (최대 7일간 재사용)")
        
        # 3단계: 활성 사용자 수집
        logger.info("📋 3단계: DB에서 활성 사용자 정보 수집 중...")
        user_favorites = get_all_active_users_with_favorites()
        
        if not user_favorites:
            logger.warning("⚠️ DB에서 활성 사용자를 찾을 수 없습니다")
            return
        
        logger.info(f"👥 {len(user_favorites)}명의 활성 사용자 발견")
        
        # 4단계: 추천 생성 시작
        logger.info("📋 4단계: 사용자별 추천 생성 시작")
        logger.info(f"🎵 {len(user_favorites)}명의 사용자를 위한 새로운 추천 생성 중...")
        
        success_count = 0
        fail_count = 0
        
        for i, (member_id, favorite_song_ids) in enumerate(user_favorites.items(), 1):
            try:
                logger.info(f"👤 [{i}/{len(user_favorites)}] 사용자 {member_id} 처리 시작 (좋아요: {len(favorite_song_ids)}개)")
                
                # 취향 캐시 확인
                cached_preference = None
                pref_key = f"preference:{member_id}"
                cached_pref_data = redis_client.get(pref_key)
                
                if cached_pref_data:
                    try:
                        pref_data = json.loads(cached_pref_data)
                        cached_favorites = pref_data.get("favorite_song_ids", [])
                        if set(cached_favorites) == set(favorite_song_ids):
                            cached_preference = pref_data.get("preference")
                            logger.info(f"   💾 사용자 {member_id}: 기존 취향 분석 재사용")
                        else:
                            redis_client.delete(pref_key)
                            logger.info(f"   🔄 사용자 {member_id}: 즐겨찾기 변경으로 취향 재분석 필요")
                    except Exception as e:
                        logger.warning(f"   ⚠️ 사용자 {member_id}: 취향 캐시 파싱 오류 - {e}")
                        pass
                else:
                    logger.info(f"   🆕 사용자 {member_id}: 신규 취향 분석 필요")
                
                # AI 추천 생성
                logger.info(f"   🤖 사용자 {member_id}: AI 추천 생성 중...")
                from core.recommendation_service import recommend_songs
                result = recommend_songs(favorite_song_ids, cached_preference)
                
                if result is None:
                    logger.error(f"   ❌ 사용자 {member_id}: 추천 서비스가 None을 반환했습니다")
                    fail_count += 1
                    continue
                    
                if "error" not in result:
                    logger.info(f"   ✅ 사용자 {member_id}: AI 추천 생성 성공")
                    
                    CACHE_TTL = 60 * 60 * 24 * 7
                    
                    # 취향 캐시 저장
                    if "preference" in result:
                        logger.info(f"   💾 사용자 {member_id}: 취향 분석 결과 캐시 저장 중...")
                        pref_key = f"preference:{member_id}"
                        today = datetime.now().strftime("%Y-%m-%d")
                        pref_data = {
                            "favorite_song_ids": favorite_song_ids,
                            "preference": result["preference"],
                            "generated_date": today
                        }
                        redis_client.setex(pref_key, CACHE_TTL, json.dumps(pref_data, ensure_ascii=False))
                        logger.info(f"   💾 사용자 {member_id}: 취향 캐시 저장 완료")
                    
                    # 추천 캐시 저장
                    logger.info(f"   💾 사용자 {member_id}: 추천 결과 캐시 저장 중...")
                    cache_key = f"recommend:{member_id}"
                    today = datetime.now().strftime("%Y-%m-%d")
                    payload = {
                        "favorites": favorite_song_ids, 
                        "recommendations": {"groups": result["groups"]},
                        "candidates": result["candidates"],
                        "generated_date": today
                    }
                    redis_client.setex(cache_key, CACHE_TTL, json.dumps(payload, ensure_ascii=False))
                    
                    groups_count = len(result.get('groups', []))
                    candidates_count = len(result.get('candidates', []))
                    logger.info(f"   ✅ 사용자 {member_id}: 모든 처리 완료 (추천그룹: {groups_count}개, 후보곡: {candidates_count}개)")
                    success_count += 1
                else:
                    logger.error(f"   ❌ 사용자 {member_id}: 추천 생성 실패 - {result.get('error')}")
                    fail_count += 1
                    
            except Exception as e:
                logger.error(f"   ❌ 사용자 {member_id}: 처리 중 예외 발생 - {e}")
                logger.error(f"   📍 예외 유형: {type(e).__name__}")
                import traceback
                logger.error(f"   🔍 상세 스택 트레이스: {traceback.format_exc()}")
                fail_count += 1
        
        # 5단계: 작업 완료 및 통계
        end_time = datetime.now()
        duration = end_time - start_time
        logger.info("📋 5단계: 작업 완료 및 통계")
        logger.info(f"✅ 추천+취향 재생성 완료 - 성공: {success_count}명, 실패: {fail_count}명")
        logger.info(f"⏱️ 총 소요 시간: {duration.total_seconds():.1f}초")
        logger.info(f"📊 평균 처리 시간: {duration.total_seconds() / len(user_favorites):.1f}초/명")
        logger.info("🎉 Redis 캐시 갱신 작업 완료!")
            
    except Exception as e:
        logger.error(f"❌ Redis 캐시 갱신 중 전체 오류 발생: {e}")
        logger.error(f"⏰ 오류 발생 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def clear_recommendation_cache():
    """
    추천 캐시만 삭제하는 함수
    """
    try:
        recommend_keys = redis_client.keys("recommend:*")
        
        if recommend_keys:
            deleted_count = redis_client.delete(*recommend_keys)
            logger.info(f"✅ Redis 추천 캐시 정리 완료: {deleted_count}개 키 삭제")
        else:
            logger.info("📝 삭제할 추천 캐시가 없습니다")
            
    except Exception as e:
        logger.error(f"❌ Redis 캐시 정리 중 오류 발생: {e}")

def clear_all_cache():
    """
    모든 캐시 삭제하는 함수
    """
    try:
        recommend_keys = redis_client.keys("recommend:*")
        preference_keys = redis_client.keys("preference:*")
        all_keys = recommend_keys + preference_keys
        
        if all_keys:
            deleted_count = redis_client.delete(*all_keys)
            logger.info(f"✅ Redis 전체 캐시 정리 완료: {deleted_count}개 키 삭제 (추천: {len(recommend_keys)}개, 취향: {len(preference_keys)}개)")
        else:
            logger.info("📝 삭제할 캐시가 없습니다")
            
    except Exception as e:
        logger.error(f"❌ Redis 캐시 정리 중 오류 발생: {e}")

def start_scheduler():
    """
    스케줄러 시작 함수
    """
    scheduler = BackgroundScheduler(timezone=timezone("Asia/Seoul"))
    
    scheduler.add_job(
        func=regenerate_all_recommendations,
        trigger=CronTrigger(hour=3, minute=0, timezone=timezone("Asia/Seoul")),
        id='regenerate_redis_cache',
        name='Redis 추천+취향 캐시 재생성',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("🕐 Redis 스케줄러가 시작되었습니다 (매일 새벽 3시 추천+취향 캐시 재생성)")
    
    return scheduler

def stop_scheduler(scheduler):
    """
    스케줄러 중지 함수
    """
    if scheduler:
        scheduler.shutdown()
        logger.info("⏹️  Redis 스케줄러가 중지되었습니다")

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
    for member_id, favorites in list(users.items())[:3]:
        logger.info(f"👤 사용자 {member_id}: {len(favorites)}개 좋아요")

if __name__ == "__main__":
    test_user_fetch()
