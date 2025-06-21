import logging
import uvicorn

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl

from service.scraper import TimetableLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,  # type: ignore
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


class HealthCheckResponse(BaseModel):
    status: str
    service: str


@app.get("/health", response_model=HealthCheckResponse)
def health_check():
    return {"status": "healthy", "service": "fastapi-scraper"}


@app.get("/timetable")
async def get_timetable(url: HttpUrl):
    if url.host != "everytime.kr" and not url.host.endswith("." + "everytime.kr"):
        raise HTTPException(status_code=400, detail="지정되지 않은 URL입니다.")

    try:
        loader = TimetableLoader()
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
