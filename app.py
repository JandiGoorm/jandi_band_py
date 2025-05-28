from flask import Flask, request, Response
from flask_cors import CORS
from service.scraper import TimetableLoader
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.config['JSON_SORT_KEYS'] = False

CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:5173"
            # 운영 환경에 맞게 기입
        ],
        "supports_credentials": True
    }
})

@app.route("/timetable", methods=["GET"])
def get_timetable():
    url = request.args.get("url")

    # URL 검증
    if not url:
        response_data = {"success": False, "message": "URL 미제공"}
        return Response(json.dumps(response_data, ensure_ascii=False),
                       status=400, mimetype='application/json')

    allowed_url_prefix = os.getenv('ALLOWED_URL_PREFIX')
    if not url.startswith(allowed_url_prefix):
        response_data = {"success": False, "message": "지정되지 않은 URL"}
        return Response(json.dumps(response_data, ensure_ascii=False),
                       status=400, mimetype='application/json')

    # TimetableLoader 인스턴스 생성 및 시간표 불러오기
    loader = TimetableLoader()
    result = loader.load_timetable(url)

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
