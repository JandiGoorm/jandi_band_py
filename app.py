from flask import Flask, request, Response
from flask_cors import CORS
from service.scraper import TimetableLoader
import json

# 상수 정의
ALLOWED_URL_PREFIX = "https://everytime.kr/"

app = Flask(__name__)

app.config['JSON_SORT_KEYS'] = False

CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:5173",
            "https://rhythmeet-be.yeonjae.kr",
            "https://*.yeonjae.kr",
            "https://rhythmeet.netlify.app"
        ],
        "supports_credentials": True
    }
})

@app.route("/health", methods=["GET"])
def health_check():
    """헬스체크 엔드포인트"""
    response_data = {
        "status": "healthy",
        "service": "flask-scraper"
    }
    return Response(json.dumps(response_data, ensure_ascii=False),
                   status=200, mimetype='application/json')

@app.route("/timetable", methods=["GET"])
def get_timetable():
    url = request.args.get("url")

    # URL 검증
    if not url:
        response_data = {"success": False, "message": "URL 미제공"}
        return Response(json.dumps(response_data, ensure_ascii=False),
                       status=400, mimetype='application/json')

    if not url.startswith(ALLOWED_URL_PREFIX):
        response_data = {"success": False, "message": "지정되지 않은 URL"}
        return Response(json.dumps(response_data, ensure_ascii=False),
                       status=400, mimetype='application/json')

    # 싱글톤 모드로 시간표 로딩
    try:
        loader = TimetableLoader.get_instance()
        result = loader.load_timetable(url)
    except Exception as e:
        TimetableLoader.reset_instance()
        response_data = {"success": False, "message": f"서버 오류: {str(e)}"}
        return Response(json.dumps(response_data, ensure_ascii=False),
                       status=500, mimetype='application/json')

    # 응답 처리
    if not result.get("success"):
        error_message = result.get("message", "")
        if "공개되지 않은 시간표" in error_message:
            status_code = 400
        elif "서버 오류" in error_message:
            status_code = 500
        else:
            status_code = 400
        return Response(json.dumps(result, ensure_ascii=False),
                       status=status_code, mimetype='application/json')

    return Response(json.dumps(result, ensure_ascii=False),
                   status=200, mimetype='application/json')

@app.teardown_appcontext
def cleanup_singleton(error):
    TimetableLoader.reset_instance()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
