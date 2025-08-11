import os
from celery import Celery

def _build_redis_url() -> str:
    """
    REDIS_URL이 없으면 REDIS_HOST/PORT/PASSWORD/DB로 조합해서 만듭니다.
    - REDIS_USE_SSL=true면 rediss:// 스킴 사용
    """
    url = os.getenv("REDIS_URL")
    if url:
        return url

    host = os.getenv("REDIS_HOST")
    port = os.getenv("REDIS_PORT")
    password = os.getenv("REDIS_PASSWORD")
    db = os.getenv("REDIS_DB", "0")
    use_ssl = str(os.getenv("REDIS_USE_SSL", "false")).lower() in ("1", "true", "yes")

    scheme = "rediss" if use_ssl else "redis"
    # 비밀번호가 있으면 :password@ 형식 적용
    auth = f":{password}@" if password else ""
    return f"{scheme}://{auth}{host}:{port}/{db}"

REDIS_URL = _build_redis_url()

celery = Celery(
    "reco",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"],
)

# 기본 설정
celery.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=120,
    task_soft_time_limit=90,
    broker_transport_options={"visibility_timeout": 3600},
    broker_connection_retry_on_startup=True,
    timezone="Asia/Seoul",
)

PREFIX = os.getenv("CELERY_KEY_PREFIX", "celery") + ":"

celery.conf.update(
    broker_transport_options={
        **(celery.conf.broker_transport_options or {}),
        "visibility_timeout": 3600,
        "global_keyprefix": PREFIX,
    },
    result_backend_transport_options={
        **(getattr(celery.conf, "result_backend_transport_options", {}) or {}),
        "global_keyprefix": PREFIX,
    },
)