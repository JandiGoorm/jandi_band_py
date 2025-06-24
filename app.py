import logging
import uvicorn
import os
from contextlib import asynccontextmanager
from mangum import Mangum

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl

from service.scraper import TimetableLoader

# 환경변수에서 로그 레벨 설정
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(level=getattr(logging, log_level))
logger = logging.getLogger(__name__)

# Lambda 환경 확인
IS_LAMBDA = os.getenv('AWS_LAMBDA_FUNCTION_NAME') is not None

# Lambda 환경에서는 전역 변수로 관리
_global_loader = None

def get_loader() -> TimetableLoader:
    """Lambda 안전 로더 가져오기"""
    global _global_loader
    if _global_loader is None:
        logger.info("글로벌 TimetableLoader 초기화")
        _global_loader = TimetableLoader()
    return _global_loader


@asynccontextmanager
async def lifespan(app: FastAPI):
    """로컬 환경에서만 사용되는 lifespan"""
    loader = None
    try:
        logger.info("TimetableLoader 초기화 중...")
        loader = TimetableLoader()
        app.state.loader = loader
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


# Lambda 환경에서는 lifespan 없이 FastAPI 생성
if IS_LAMBDA:
    app = FastAPI(
        title="Jandi Band Scraper API",
        description="에브리타임 시간표 스크래핑 API",
        version="1.0.0"
    )
else:
    app = FastAPI(
        lifespan=lifespan,
        title="Jandi Band Scraper API",
        description="에브리타임 시간표 스크래핑 API",
        version="1.0.0"
    )

app.add_middleware(
    CORSMiddleware,  # type: ignore
    allow_origins=[
        "http://localhost:5173",
        "https://rhythmeet-be.yeonjae.kr",
        "https://rhythmeet.netlify.app"
    ],
    allow_origin_regex=r"https://.*\.yeonjae\.kr",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthCheckResponse(BaseModel):
    status: str
    service: str
    environment: str


@app.get("/health", response_model=HealthCheckResponse)
def health_check():
    return {
        "status": "healthy",
        "service": "fastapi-scraper",
        "environment": "lambda" if IS_LAMBDA else "local"
    }


@app.get("/timetable")
async def get_timetable(request: Request, url: HttpUrl):
    if not url.host.endswith("everytime.kr"):
        raise HTTPException(status_code=400, detail="지정되지 않은 URL입니다.")

    try:
        # Lambda 환경에서는 글로벌 로더 사용, 로컬에서는 app.state 사용
        if IS_LAMBDA:
            loader = get_loader()
        else:
            loader = request.app.state.loader

        result = await loader.load_timetable(str(url))

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


# Lambda 핸들러 (Mangum 사용)
handler = Mangum(app, lifespan="off")  # Lambda에서는 lifespan을 off로 설정


if __name__ == "__main__":
    # 로컬 개발 환경에서만 실행
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
