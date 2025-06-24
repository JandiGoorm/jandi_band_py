from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
from contextlib import asynccontextmanager
import uvicorn
import logging

from service.scraper import TimetableLoader, get_browser_manager, cleanup_browser_manager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 상수 정의
ALLOWED_URL_HOST = "everytime.kr"

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("브라우저 시작...")
        browser_manager = await get_browser_manager()
        await browser_manager.start_browser()
        logger.info("애플리케이션 시작 완료")
        yield
    except Exception as e:
        logger.error(f"애플리케이션 시작 오류: {e}")
        raise
    finally:
        logger.info("애플리케이션 종료 중...")
        await cleanup_browser_manager()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://rhythmeet-be.yeonjae.kr",
        "https://*.yeonjae.kr",
        "https://rhythmeet.netlify.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TimetableResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

class HealthCheckResponse(BaseModel):
    status: str
    service: str

@app.get("/health", response_model=HealthCheckResponse)
def health_check():
    return {"status": "healthy", "service": "fastapi-scraper"}

@app.get("/timetable")
async def get_timetable(url: HttpUrl):
    if url.host != ALLOWED_URL_HOST and not url.host.endswith("." + ALLOWED_URL_HOST):
        raise HTTPException(status_code=400, detail="지정되지 않은 URL입니다.")

    try:
        browser_manager = await get_browser_manager()

        if not browser_manager._is_started:
            raise HTTPException(status_code=500, detail="브라우저가 초기화되지 않았습니다.")

        async with browser_manager.get_page() as page:
            loader = TimetableLoader()
            result = await loader.load_timetable(str(url), page)

            if not result.get("success"):
                error_message = result.get("message", "알 수 없는 오류")
                status_code = 500 if "서버 오류" in error_message else 400
                if "data" not in result:
                    result["data"] = {}
                return JSONResponse(status_code=status_code, content=result)

            return JSONResponse(status_code=200, content=result)

    except Exception as e:
        logger.error(f"시간표 요청 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
