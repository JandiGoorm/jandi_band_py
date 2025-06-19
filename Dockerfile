FROM python:3.12-slim

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 레이블 추가 (컨테이너 관리용)
LABEL maintainer="jandi-band"
LABEL service="fastapi-scraper"

# 시스템 패키지 설치 (Playwright 의존성)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 사용자 생성
RUN useradd -m -u 1000 scraper && \
    mkdir -p /app /app/logs && \
    chown -R scraper:scraper /app

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 패키지 설치 (캐시 효율성을 위해 먼저 복사)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Playwright 시스템 의존성을 root로 설치
RUN playwright install-deps chromium

# 사용자로 전환 후 Playwright 브라우저만 설치
USER scraper
RUN playwright install chromium

# 소스 코드 복사
COPY --chown=scraper:scraper . .

# 포트 노출
EXPOSE 5001

# 헬스체크 추가 (호스트에서 접근 가능하도록)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# 시작 스크립트 생성 (로깅 개선)
RUN echo '#!/bin/bash\necho "Starting FastAPI Scraper..."\necho "Port: 5001"\npython app.py' > start.sh && \
    chmod +x start.sh

# 애플리케이션 실행
CMD ["./start.sh"]
