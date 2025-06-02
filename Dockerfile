FROM python:3.12-slim

# 시스템 패키지 설치 (Playwright 의존성)
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# 사용자 생성
RUN useradd -m scraper

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치
RUN playwright install chromium
RUN playwright install-deps chromium

# 소스 코드 복사
COPY . .

CMD ["python", "app.py"]
