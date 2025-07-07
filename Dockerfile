# 1. Builder Stage: 의존성 설치
FROM python:3.12-slim as builder

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 빌드에 필요한 도구 설치
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 가상 환경 생성 및 활성화
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------

# 2. Final Stage: 실제 실행될 이미지
FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl --no-install-recommends && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 사용자 생성 및 권한 설정
RUN useradd -m -u 1000 scraper && \
    mkdir -p /app /app/logs && \
    chown -R scraper:scraper /app

WORKDIR /app

# Builder 스테이지에서 가상 환경과 설치된 패키지만 복사
COPY --from=builder /opt/venv /opt/venv
# Builder 스테이지에서 애플리케이션 코드 복사
COPY --chown=scraper:scraper . .

# PATH 환경 변수 설정
ENV PATH="/opt/venv/bin:$PATH"

USER scraper

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:5001/health || exit 1

# 애플리케이션 실행
CMD ["python", "app.py"]
