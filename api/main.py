"""
FastAPI 애플리케이션 메인 모듈
"""

from api.app import create_app

# FastAPI 앱 생성
app = create_app()