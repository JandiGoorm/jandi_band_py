FROM python:3.12-slim

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_ENV=production

# 시스템 패키지 설치 (Playwright 의존성)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 사용자 생성
RUN useradd -m -u 1000 scraper && \
    mkdir -p /app && \
    chown scraper:scraper /app

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 패키지 설치 (캐시 효율성을 위해 먼저 복사)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치 (사용자로 실행)
USER scraper
RUN playwright install chromium && \
    playwright install-deps chromium

# 소스 코드 복사
COPY --chown=scraper:scraper . .

# 포트 노출
EXPOSE 5001

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5001/timetable?url=test || exit 1

# 애플리케이션 실행
CMD ["python", "app.py"]
