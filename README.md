# Songs AI - 음악 추천 시스템

AI 기반 노래 추천 서비스입니다. 사용자의 음악 취향을 분석하여 개인화된 노래를 추천합니다.

## 📁 프로젝트 구조

```
songs_ai/
├── api/                    # 🌐 FastAPI 웹 애플리케이션
│   ├── __init__.py
│   ├── main.py            # API 애플리케이션 진입점
│   ├── app.py             # FastAPI 앱 팩토리
│   └── routes/            # API 라우터들
│       ├── __init__.py
│       ├── recommendations.py  # 추천 관련 API
│       └── tasks.py       # 백그라운드 작업 API
│
├── core/                   # 🧠 핵심 비즈니스 로직
│   ├── __init__.py
│   └── recommendation_service.py  # 추천 알고리즘 및 로직
│
├── services/               # 🔌 외부 서비스 연동
│   ├── __init__.py
│   ├── database_service.py # 데이터베이스 연동
│   ├── ai_service.py       # OpenAI/LangChain AI 서비스
│   ├── cache_service.py    # Redis 캐시 서비스
│   └── redis_scheduler.py  # Redis 스케줄링
│
├── workers/                # ⚙️ Celery 백그라운드 작업
│   ├── __init__.py
│   ├── celery_app.py       # Celery 앱 설정
│   └── tasks.py            # 백그라운드 작업 정의
│
├── models/                 # 📊 데이터 모델
│   ├── __init__.py
│   ├── data_models.py      # 비즈니스 데이터 모델
│   └── api_models.py       # API 요청/응답 모델
│
├── config/                 # ⚙️ 설정 파일
│   ├── __init__.py
│   ├── settings.py         # 환경 변수 및 설정
│   ├── prompts.py          # AI 프롬프트 템플릿
│   └── redis.py            # Redis 연결 설정
│
├── utils/                  # 🛠 유틸리티 함수
│   ├── __init__.py
│   └── helpers.py          # 공통 헬퍼 함수
│
├── main.py                 # 🚀 애플리케이션 진입점
├── tools.py                # 🔄 하위 호환성을 위한 레거시 인터페이스
├── requirements.txt        # Python 의존성
├── Dockerfile             # Docker 이미지 빌드
├── docker-compose.yml     # Docker Compose 설정
└── README.md              # 이 파일
```

## 🚀 실행 방법

### 1. 개발 환경 설정

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정 (.env 파일 생성)
cp .env.example .env
# .env 파일을 편집하여 필요한 환경 변수 설정

# API 서버 실행
python main.py
```

### 2. Docker로 실행

```bash
# Docker Compose로 전체 스택 실행
docker-compose up -d

# 개별 서비스 빌드
docker build -t songs-ai .
```

### 3. Celery Worker 실행

```bash
# Celery Worker 실행 (백그라운드 작업 처리)
celery -A workers.celery_app worker --loglevel=info

# Celery Beat 실행 (스케줄링)
celery -A workers.celery_app beat --loglevel=info
```

## 📚 API 엔드포인트

### POST /recommend

사용자의 좋아하는 곡을 기반으로 추천 생성

### POST /recommend/cached

캐시된 추천 결과 조회

### POST /favorites/updated

사용자 좋아요 업데이트 시 백그라운드 분석 작업 큐잉

### POST /warm/active

활성 사용자들의 추천 캐시 워밍

## 🛠 주요 기능

- **AI 기반 취향 분석**: OpenAI GPT를 활용한 음악 취향 분석
- **개인화 추천**: 사용자별 맞춤 노래 추천
- **캐시 시스템**: Redis를 활용한 고성능 캐시
- **백그라운드 작업**: Celery를 활용한 비동기 처리
- **자동 스케줄링**: 정기적인 캐시 갱신

## 🔧 기술 스택

- **Backend**: FastAPI, Python 3.11+
- **AI/ML**: OpenAI GPT, LangChain
- **Database**: MySQL, PyMySQL
- **Cache**: Redis
- **Task Queue**: Celery
- **Container**: Docker, Docker Compose

## 📝 개발 가이드

### 폴더별 역할

- `api/`: 웹 API 레이어, HTTP 요청/응답 처리
  - `routes/`: API 엔드포인트별 라우터 분리
  - `app.py`: FastAPI 앱 팩토리 패턴
- `core/`: 비즈니스 로직, 추천 알고리즘
- `services/`: 외부 시스템 연동 (DB, AI, Redis 등)
  - `cache_service.py`: Redis 캐시 전용 서비스
- `workers/`: 백그라운드 작업 및 스케줄링
- `models/`: 데이터 구조 정의
  - `data_models.py`: 비즈니스 도메인 모델
  - `api_models.py`: API 요청/응답 모델
- `config/`: 설정 및 환경변수 관리
  - `redis.py`: Redis 연결 전용 설정
- `utils/`: 공통 유틸리티 함수

### 새로운 기능 추가 시

1. 적절한 폴더에 모듈 추가
2. `__init__.py`에 export 추가
3. 필요시 `tools.py`에 하위 호환성 인터페이스 추가

## 📄 라이센스

이 프로젝트는 MIT 라이센스 하에 있습니다.
