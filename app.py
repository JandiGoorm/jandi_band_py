import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from service.scraper import TimetableLoader
from pydantic import ValidationError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
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

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,  # type: ignore
    allow_origins=[
        "http://localhost:5173",
        "https://rhythmeet-be.yeonjae.kr",
        "https://*.yeonjae.kr",
        "https://rhythmeet.netlify.app",
        "https://rhythmeet.site"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HealthCheckResponse(BaseModel):
    status: str
    service: str

@app.get("/health", response_model=HealthCheckResponse)
def health_check():
    return {"status": "healthy", "service": "fastapi-scraper"}

@app.get("/timetable")
async def get_timetable(request: Request): # url: HttpUrl 부분을 제거합니다.
    # 1. request.query_params에서 'url'을 직접 가져옵니다.
    url_str = request.query_params.get("url")
    if not url_str:
        raise HTTPException(status_code=400, detail="url 파라미터가 필요합니다.")

    # 2. 가져온 url 문자열의 유효성을 수동으로 검사합니다.
    try:
        # HttpUrl 타입으로 변환 시도
        validated_url = HttpUrl(url_str)
    except ValidationError:
        raise HTTPException(status_code=400, detail="유효하지 않은 URL 형식입니다.")

    # 3. 기존의 도메인 검사 로직을 수행합니다.
    if validated_url.host != "everytime.kr" and not validated_url.host.endswith("." + "everytime.kr"):
        raise HTTPException(status_code=400, detail="지정되지 않은 URL입니다.")

    # 4. 이후 비즈니스 로직은 동일합니다.
    try:
        loader = request.app.state.loader
        result = await loader.load_timetable(str(validated_url)) # validated_url 사용

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
