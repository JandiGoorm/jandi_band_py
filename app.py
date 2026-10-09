import logging
import math
import os
from time import monotonic
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from service.scraper import TimetableLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScrapeBudget:
    def __init__(self, max_concurrent=4, requests_per_minute=60):
        if max_concurrent < 1 or requests_per_minute < 1:
            raise ValueError("시간표 요청 한도는 양수여야 합니다.")
        self.max_concurrent = max_concurrent
        self.requests_per_minute = requests_per_minute
        self.active = 0
        self.requests = 0
        self.window_started = monotonic()

    def acquire(self):
        elapsed = monotonic() - self.window_started
        if elapsed >= 60:
            self.window_started = monotonic()
            self.requests = 0
            elapsed = 0
        if self.active >= self.max_concurrent:
            raise HTTPException(429, "처리 중인 요청이 많습니다.", headers={"Retry-After": "1"})
        if self.requests >= self.requests_per_minute:
            raise HTTPException(429, "요청 한도를 초과했습니다.",
                                headers={"Retry-After": str(max(1, math.ceil(60 - elapsed)))})
        self.active += 1
        self.requests += 1

    def release(self):
        self.active -= 1

@asynccontextmanager
async def lifespan(app: FastAPI):
    loader = None
    try:
        logger.info("TimetableLoader 초기화 중...")
        loader = TimetableLoader()
        app.state.loader = loader
        app.state.scrape_budget = ScrapeBudget(
            int(os.getenv("TIMETABLE_MAX_CONCURRENT", "4")),
            int(os.getenv("TIMETABLE_REQUESTS_PER_MINUTE", "60")),
        )
        yield
    except Exception as e:
        logger.error(f"애플리케이션 시작 오류: {e}")
        raise
    finally:
        if loader:
            try:
                await loader.close()
                logger.info("리소스 정리 완료")
            except Exception as e:
                logger.error(f"리소스 정리 오류: {e}")

app = FastAPI(lifespan=lifespan)

# CORS는 공용 Nginx에서 관리

class HealthCheckResponse(BaseModel):
    status: str
    service: str

@app.get("/health", response_model=HealthCheckResponse)
def health_check():
    return {"status": "healthy", "service": "fastapi-scraper"}

@app.get("/timetable")
async def get_timetable(request: Request, url: HttpUrl):
    if url.host != "everytime.kr" and not url.host.endswith("." + "everytime.kr"):
        raise HTTPException(status_code=400, detail="지정되지 않은 URL입니다.")

    budget = request.app.state.scrape_budget
    budget.acquire()
    try:
        loader = request.app.state.loader
        result = await loader.load_timetable(str(url))

        if not result.get("success"):
            error_message = result.get("message", "알 수 없는 오류")
            status_code = 500 if "서버 오류" in error_message else 400
            if "data" not in result:
                result["data"] = {}
            if status_code == 500:
                result = {**result, "message": "서버 오류"}
            return JSONResponse(status_code=status_code, content=result)

        return JSONResponse(status_code=200, content=result)

    except Exception as e:
        logger.exception("시간표 요청 처리 실패")
        raise HTTPException(status_code=500, detail="서버 오류") from e
    finally:
        budget.release()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
