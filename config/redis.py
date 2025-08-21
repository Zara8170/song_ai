import os
import redis
from dotenv import load_dotenv

load_dotenv()

# Redis 설정
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_TTL = 60 * 60 * 24 * 7  # 7일 캐시

def get_redis_client() -> redis.Redis:
    """Redis 클라이언트를 생성하고 반환합니다."""
    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        db=REDIS_DB,
        decode_responses=True,
    )
    
    try:
        client.ping()
    except Exception as e:
        print(f"[WARN] Redis ping failed: {e}")
    
    return client

# 전역 Redis 클라이언트 인스턴스
redis_client = get_redis_client()
