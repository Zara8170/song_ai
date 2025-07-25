from dotenv import load_dotenv
import os
import redis

load_dotenv()

host = os.getenv('REDIS_HOST')
port = int(os.getenv('REDIS_PORT'))
password = os.getenv('REDIS_PASSWORD')

try:
    client = redis.Redis(host=host, port=port, password=password)
    if client.ping():
        print("✅ Redis 연결 성공")
    else:
        print("❌ Redis 연결 실패")
except redis.ConnectionError as e:
    print("❌ Redis 연결 오류:", e)
