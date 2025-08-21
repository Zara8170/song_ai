#!/usr/bin/env python3
"""
메인 애플리케이션 진입점
새로운 폴더 구조에서 API 서버를 실행합니다.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
