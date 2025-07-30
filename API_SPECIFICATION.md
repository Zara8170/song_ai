# AI Songs Recommendation Service - Backend API 명세서

## 개요

AI 기반 노래 추천 서비스의 백엔드 API 서버입니다. 사용자의 선호 노래를 분석하여 개인 맞춤형 노래를 추천하는 서비스를 제공합니다.

## 기술 스택

- **Framework**: FastAPI
- **AI Engine**: OpenAI GPT-4o-mini
- **Database**: MySQL (PyMySQL)
- **Cache**: Redis
- **Search Engine**: Elasticsearch
- **Language**: Python 3.11
- **Deployment**: Docker Compose

## 서버 정보

- **Base URL**: `http://localhost:8000`
- **Port**: 8000
- **Protocol**: HTTP

## API 엔드포인트

### 1. 헬스체크

서버 상태를 확인하는 엔드포인트입니다.

```http
GET /
```

#### 응답

```json
{
  "message": "AI Song Recommender is running!"
}
```

### 2. 노래 추천

사용자의 선호 노래를 기반으로 AI가 분석한 맞춤형 노래를 추천합니다.

```http
POST /recommend
```

#### 요청 Body

```json
{
  "memberId": "string",
  "favorite_song_ids": [int]
}
```

| 필드                | 타입       | 필수 | 설명                                             |
| ------------------- | ---------- | ---- | ------------------------------------------------ |
| `memberId`          | string     | O    | 사용자 고유 식별자                               |
| `favorite_song_ids` | array[int] | X    | 사용자가 좋아하는 노래 ID 목록 (기본값: 빈 배열) |

#### 응답

```json
{
  "groups": [
    {
      "label": "string",
      "tagline": "string",
      "songs": [
        {
          "title_jp": "string",
          "title_kr": "string",
          "artist": "string",
          "artist_kr": "string",
          "tj_number": "string",
          "ky_number": "string"
        }
      ]
    }
  ],
  "candidates": [
    {
      "song_id": int,
      "title_jp": "string",
      "title_kr": "string",
      "artist": "string",
      "artist_kr": "string",
      "genre": "string",
      "mood": "string",
      "tj_number": "string",
      "ky_number": "string",
      "recommendation_type": "string",
      "matched_criteria": ["string"]
    }
  ]
}
```

#### 응답 필드 설명

**groups** - 추천 노래 그룹 (최대 4개)

- `label`: 그룹 이름 (분위기 또는 장르)
- `tagline`: AI가 생성한 그룹 설명 태그라인
- `songs`: 해당 그룹의 노래 목록 (3-6곡)

**candidates** - 후보 노래 목록 (12곡 랜덤 선택)

- `song_id`: 노래 고유 ID
- `recommendation_type`: 추천 유형 (`preference` | `random`)
- `matched_criteria`: 매칭된 기준 (`genre` | `artist`)

#### 오류 응답

```json
{
  "detail": "string"
}
```

| 상태 코드 | 설명           |
| --------- | -------------- |
| 200       | 성공           |
| 500       | 서버 내부 오류 |

## 캐시 정책

- **Redis 캐시 TTL**: 24시간
- **캐시 키 형식**: `recommend:{memberId}`
- **캐시 적용**: 추천 결과 전체 (groups + candidates)

## AI 추천 로직

### 1. 사용자 취향 분석

- 선호 노래의 장르, 분위기, 아티스트 분석
- GPT-4o-mini를 활용한 음악 취향 프로파일링

### 2. 후보곡 선별

- 취향 기반 유사 노래 (50%)
- 랜덤 노래 (50%)
- 총 100곡 후보군 생성

### 3. AI 추천 선별

- 후보곡 중 20곡을 AI가 선별
- 사용자 취향과의 매칭도 기반

### 4. 그룹화

- 분위기 기반 그룹 2개
- 장르 기반 그룹 2개
- 각 그룹당 3-6곡 구성

## 데이터베이스 스키마

### song 테이블

```sql
song (
  song_id INT PRIMARY KEY,
  title_jp VARCHAR,
  title_kr VARCHAR,
  artist VARCHAR,
  artist_kr VARCHAR,
  genre VARCHAR,
  mood VARCHAR,
  tj_number VARCHAR,
  ky_number VARCHAR
)
```

### member 테이블

```sql
member (
  member_id INT PRIMARY KEY,
  ...
)
```

### song_like 테이블

```sql
song_like (
  member_id INT,
  song_id INT,
  ...
)
```

## 환경 변수

```env
# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Database
DB_HOST=your_db_host
DB_PORT=3306
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Elasticsearch
ELASTICSEARCH_HOSTS=your_es_host
ELASTICSEARCH_INDEX=your_es_index
```

## 배포 방법

### Docker Compose 실행

```bash
docker-compose up -d
```

### 로컬 개발 실행

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 모니터링

- **로그 파일**: `recommend_api.log`
- **Redis 연결 상태**: 서버 시작 시 ping 테스트
- **스케줄러**: APScheduler 백그라운드 작업

## 성능 특징

- **캐싱**: Redis 기반 24시간 캐시로 응답 속도 최적화
- **AI 추천**: OpenAI API 호출로 고품질 추천 제공
- **백그라운드 작업**: 스케줄러를 통한 비동기 처리
- **오류 처리**: AI 실패 시 랜덤 추천으로 폴백

## API 사용 예시

### cURL 예제

#### 헬스체크

```bash
curl -X GET "http://localhost:8000/"
```

#### 노래 추천 요청

```bash
curl -X POST "http://localhost:8000/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "memberId": "user123",
    "favorite_song_ids": [1001, 1002, 1003]
  }'
```

### 실제 응답 예시

#### 성공 응답

```json
{
  "groups": [
    {
      "label": "차분한",
      "tagline": "마음을 편안하게 해주는 감성적인 선곡 🎵",
      "songs": [
        {
          "title_jp": "아이유 - 밤편지",
          "title_kr": "밤편지",
          "artist": "IU",
          "artist_kr": "아이유",
          "tj_number": "35090",
          "ky_number": "45123"
        },
        {
          "title_jp": "볼빨간사춘기 - 우주를 줄게",
          "title_kr": "우주를 줄게",
          "artist": "Bolbbalgan4",
          "artist_kr": "볼빨간사춘기",
          "tj_number": "35234",
          "ky_number": "45267"
        }
      ]
    },
    {
      "label": "발라드",
      "tagline": "깊은 감동을 전하는 아름다운 멜로디 🎶",
      "songs": [
        {
          "title_jp": "임재현 - 너를 만나",
          "title_kr": "너를 만나",
          "artist": "Lim Jaehyun",
          "artist_kr": "임재현",
          "tj_number": "32567",
          "ky_number": "42891"
        }
      ]
    }
  ],
  "candidates": [
    {
      "song_id": 2001,
      "title_jp": "BTS - Dynamite",
      "title_kr": "Dynamite",
      "artist": "BTS",
      "artist_kr": "방탄소년단",
      "genre": "팝",
      "mood": "신나는",
      "tj_number": "36789",
      "ky_number": "46912",
      "recommendation_type": "preference",
      "matched_criteria": ["genre"]
    }
  ]
}
```

## 테스트 방법

### 1. 로컬 환경 구성

```bash
# 환경 변수 설정
cp .env.example .env
# .env 파일에 실제 값 입력

# Docker 컨테이너 실행
docker-compose up -d

# 서버 상태 확인
curl http://localhost:8000/
```

### 2. API 테스트 시나리오

#### 시나리오 1: 첫 사용자 (선호곡 없음)

```bash
curl -X POST "http://localhost:8000/recommend" \
  -H "Content-Type: application/json" \
  -d '{"memberId": "new_user", "favorite_song_ids": []}'
```

#### 시나리오 2: 기존 사용자 (선호곡 있음)

```bash
curl -X POST "http://localhost:8000/recommend" \
  -H "Content-Type: application/json" \
  -d '{"memberId": "existing_user", "favorite_song_ids": [1, 15, 23, 67]}'
```

#### 시나리오 3: 캐시 확인 (동일 요청 재전송)

```bash
# 첫 번째 요청
curl -X POST "http://localhost:8000/recommend" \
  -H "Content-Type: application/json" \
  -d '{"memberId": "cache_test", "favorite_song_ids": [100]}'

# 두 번째 요청 (캐시에서 응답)
curl -X POST "http://localhost:8000/recommend" \
  -H "Content-Type: application/json" \
  -d '{"memberId": "cache_test", "favorite_song_ids": [100]}'
```

## 트러블슈팅

### 일반적인 오류

#### 1. Redis 연결 오류

```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**해결방법**: Redis 서버 상태 확인 및 환경변수 점검

#### 2. MySQL 연결 오류

```
pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")
```

**해결방법**: MySQL 서버 상태 확인 및 DB 접속 정보 점검

#### 3. OpenAI API 오류

```
openai.error.AuthenticationError: Invalid API key
```

**해결방법**: OpenAI API 키 확인 및 사용량 한도 점검

### 로그 확인

```bash
# 애플리케이션 로그
tail -f recommend_api.log

# Docker 컨테이너 로그
docker-compose logs -f ai-server

# Redis 로그
docker-compose logs -f redis
```

## 자동화된 테스트

프로젝트에 포함된 `test_api.py` 스크립트를 사용하여 API를 자동으로 테스트할 수 있습니다.

### 테스트 스크립트 실행

```bash
# 의존성 설치
pip install requests

# 테스트 실행
python test_api.py
```

### 테스트 항목

- ✅ 헬스체크 API 동작 확인
- ✅ 기본 추천 API 동작 확인
- ✅ Redis 캐시 성능 테스트
- ✅ 다양한 사용자 시나리오 테스트
- ✅ 데이터 타입 검증 테스트

### 테스트 결과

테스트 완료 후 `api_test_results.json` 파일에 상세한 결과가 저장됩니다.

## 주의사항

- OpenAI API 키가 필요합니다
- MySQL, Redis, Elasticsearch 인프라가 구성되어야 합니다
- 사용자별 캐시로 인해 Redis 메모리 사용량을 모니터링해야 합니다
- OpenAI API 사용량과 비용을 모니터링해야 합니다
- favorite_song_ids는 문자열이나 숫자 모두 허용하며 자동으로 정수로 변환됩니다
