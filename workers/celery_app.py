import os
from datetime import datetime, timezone
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
import redis
import json

def _build_redis_url() -> str:
    """
    REDIS_URL이 없으면 REDIS_HOST/PORT/PASSWORD/DB로 조합해서 만듭니다.
    - REDIS_USE_SSL=true면 rediss:// 스킴 사용
    """
    url = os.getenv("REDIS_URL")
    if url:
        return url

    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    password = os.getenv("REDIS_PASSWORD")
    db = os.getenv("REDIS_DB", "0")
    scheme = "rediss" if os.getenv("REDIS_USE_SSL", "false").lower() == "true" else "redis"
    if password:
        return f"{scheme}://:{password}@{host}:{port}/{db}"
    return f"{scheme}://{host}:{port}/{db}"

REDIS_URL = _build_redis_url()

celery = Celery(
    "reco",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.tasks"],
)

# 기본/이벤트 설정
celery.conf.update( 
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=120,
    task_soft_time_limit=90,
    broker_transport_options={"visibility_timeout": 3600},
    broker_connection_retry_on_startup=True,
    timezone="Asia/Seoul",

    # Flower/이벤트를 위해
    task_send_sent_event=True,
    worker_send_task_events=True,

    # 직렬화 통일
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    result_expires=7 * 24 * 3600,  # 결과 TTL
)

rlog = redis.Redis.from_url(REDIS_URL, decode_responses=True)
LOG_TTL = int(os.getenv("REDIS_LOG_TTL_SEC", str(7 * 24 * 3600)))
LOG_STREAM = os.getenv("REDIS_LOG_STREAM", "a:celery:stream")

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _extract_member_id(args, kwargs):
    if isinstance(kwargs.get("member_id", None), (str, int)):
        return str(kwargs["member_id"])
    if args and isinstance(args[0], (str, int)):
        return str(args[0])
    return None

def _shorten(obj, limit=800):
    """로그에 너무 큰 데이터가 들어가지 않도록 잘라서 저장"""
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = str(obj)
    return s if len(s) <= limit else s[:limit] + "...(truncated)"

@task_prerun.connect
def _log_task_start(sender=None, task_id=None, args=None, kwargs=None, **extra):
    member_id = _extract_member_id(args or (), kwargs or {})
    task_name = sender.name if sender else extra.get("task").name
    base_key = f"a:celery:run:{task_id}"
    rlog.hset(base_key, mapping={
        "task_id": task_id,
        "task": task_name,
        "member_id": member_id or "",
        "status": "STARTED",
        "started_at": _now_iso(),
        "args": _shorten(args or ()),
        "kwargs": _shorten(kwargs or {}),
    })
    rlog.expire(base_key, LOG_TTL)

    # 타임라인(Stream)
    rlog.xadd(LOG_STREAM, {
        "event": "start",
        "task_id": task_id,
        "task": task_name,
        "member_id": member_id or "",
        "ts": _now_iso(),
    }, maxlen=10_000, approximate=True)

    # 사용자별 최근 상태(Key)
    if member_id:
        rlog.setex(f"a:celery:user:{member_id}:last", LOG_TTL, json.dumps({
            "task_id": task_id, "task": task_name, "status": "STARTED", "ts": _now_iso()
        }, ensure_ascii=False))

@task_postrun.connect
def _log_task_done(sender=None, task_id=None, retval=None, state=None, **extra):
    task_name = sender.name if sender else ""
    base_key = f"a:celery:run:{task_id}"
    # 기존 hash 업데이트
    rlog.hset(base_key, mapping={
        "status": state or "SUCCESS",
        "ended_at": _now_iso(),
        "result": _shorten(retval),
    })
    rlog.expire(base_key, LOG_TTL)

    # 멤버ID 복원(없으면 공백)
    member_id = rlog.hget(base_key, "member_id") or ""

    rlog.xadd(LOG_STREAM, {
        "event": "done",
        "task_id": task_id,
        "task": task_name,
        "member_id": member_id,
        "status": state or "SUCCESS",
        "ts": _now_iso(),
    }, maxlen=10_000, approximate=True)

@task_failure.connect
def _log_task_fail(task_id=None, exception=None, traceback=None, sender=None, args=None, kwargs=None, einfo=None, **extra):
    task_name = sender.name if sender else ""
    member_id = _extract_member_id(args or (), kwargs or {}) or ""
    base_key = f"a:celery:run:{task_id}"
    rlog.hset(base_key, mapping={
        "status": "FAILURE",
        "ended_at": _now_iso(),
        "error": _shorten(str(exception)),
    })
    rlog.expire(base_key, LOG_TTL)
    rlog.xadd(LOG_STREAM, {
        "event": "fail",
        "task_id": task_id,
        "task": task_name,
        "member_id": member_id,
        "error": _shorten(str(exception), 300),
        "ts": _now_iso(),
    }, maxlen=10_000, approximate=True)
