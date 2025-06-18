from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional

from service.scraper import TimetableLoader

# 상수 정의
ALLOWED_URL_HOST = "everytime.kr"

app = FastAPI()

# CORS 미들웨어 설정
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
    """헬스체크 엔드포인트"""
    return {"status": "healthy", "service": "fastapi-scraper"}

@app.get("/timetable")
def get_timetable(url: HttpUrl):
    # URL 호스트 검증 (Pydantic의 HttpUrl이 기본적인 URL 형식을 검증)
    if url.host != ALLOWED_URL_HOST and not url.host.endswith("." + ALLOWED_URL_HOST):
        raise HTTPException(status_code=400, detail="지정되지 않은 URL입니다.")

    # 싱글톤 모드로 시간표 로딩
    loader = TimetableLoader.get_instance()
    try:
        result = loader.load_timetable(str(url))

        if not result.get("success"):
            error_message = result.get("message", "알 수 없는 오류")
            status_code = 500 if "서버 오류" in error_message else 400
            # timetableData가 없는 경우, 빈 객체로 설정하여 응답 모델을 만족시킴
            if "data" not in result:
                result["data"] = {}
            return JSONResponse(status_code=status_code, content=result)

        return JSONResponse(status_code=200, content=result)

    except Exception as e:
        # 예상치 못한 에러 발생 시 항상 리소스 정리
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")
    finally:
        # 성공/실패 여부와 관계없이 항상 싱글톤 인스턴스 정리
        TimetableLoader.reset_instance()


# uvicorn으로 실행하기 위한 설정
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
