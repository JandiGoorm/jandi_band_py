FROM python:3.12-slim

# 환경 변수 설정
ENV PATH="/usr/lib/chromium/:/usr/bin/chromium:${PATH}"
ENV CHROME_HEADLESS=1
ENV CHROME_BIN="/usr/bin/chromium"
ENV CHROMEDRIVER_PATH="/usr/bin/chromedriver"

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    curl unzip \
    chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# 사용자 생성
RUN useradd -m scraper

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

CMD ["python", "app.py"]
