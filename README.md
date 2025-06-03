# Flask 에브리타임 시간표 스크래핑 서버

에브리타임 시간표 URL을 받아서 시간표 데이터를 스크래핑하는 REST API 서버입니다.  
Playwright를 사용하여 동적 웹페이지를 안정적으로 스크래핑하며, Docker 컨테이너와 Jenkins CI/CD를 통해 자동 배포됩니다.

## 주요 기능

- 에브리타임 시간표 URL 스크래핑
- CORS 지원으로 웹 애플리케이션에서 직접 호출 가능
- Docker 컨테이너 기반 배포
- Jenkins CI/CD 자동 배포
- Playwright 헤드리스 브라우저 사용
- 에러 처리 및 상태 코드 관리

## 기술 스택

- **Backend**: Python 3.12, Flask, Flask-CORS
- **Scraping**: Playwright (Chromium)
- **Containerization**: Docker
- **CI/CD**: Jenkins
- **Reverse Proxy**: Nginx

## 프로젝트 구조

```
jandi_band_py/
├── app.py                      # Flask 애플리케이션 메인 파일
├── requirements.txt            # Python 의존성
├── Dockerfile                  # Docker 이미지 빌드 설정
├── Jenkinsfile                 # CI/CD 파이프라인 설정
├── docker-compose.yml          # Docker Compose 설정 (참고용)
├── service/                    # 비즈니스 로직
│   ├── __init__.py
│   └── scraper.py              # 시간표 스크래핑 로직
├── DEPLOYMENT.md               # 배포 가이드
└── README.md                   # 프로젝트 문서
```

## API 명세서

### Base URL
```
Production: https://rhythmeet-be.yeonjae.kr/scraper
Development: http://localhost:5001
```

### GET /health
서비스 상태를 확인하는 헬스체크 엔드포인트입니다.

**Response:**
```json
{
  "status": "healthy",
  "service": "flask-scraper"
}
```

### GET /timetable
에브리타임 시간표 데이터를 스크래핑합니다.

#### Request
**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | 에브리타임 시간표 공유 URL |

**Example Request:**
```bash
curl "https://rhythmeet-be.yeonjae.kr/scraper/timetable?url=https://everytime.kr/timetable/12345"
```

#### Response

**Success Response (200)**
```json
{
  "success": true,
  "message": "유저 시간표 불러오기 성공",
  "data": {
    "timetableData": {
      "Mon": ["09:00", "09:30", "10:00", "10:30"],
      "Tue": ["10:00", "10:30", "11:00"],
      "Wed": ["14:00", "14:30", "15:00"],
      "Thu": [],
      "Fri": ["13:00", "13:30", "14:00"],
      "Sat": [],
      "Sun": []
    }
  }
}
```

**Error Responses**

**400 Bad Request - URL 미제공**
```json
{
  "success": false,
  "message": "URL 미제공"
}
```

**400 Bad Request - 잘못된 URL**
```json
{
  "success": false,
  "message": "지정되지 않은 URL"
}
```

**400 Bad Request - 비공개 시간표**
```json
{
  "success": false,
  "message": "공개되지 않은 시간표입니다."
}
```

**500 Internal Server Error**
```json
{
  "success": false,
  "message": "서버 오류: {오류내용}"
}
```

## CORS 정책
다음 도메인에서의 요청을 허용합니다:
- `http://localhost:5173` (개발환경)
- `https://rhythmeet-be.yeonjae.kr`
- `https://*.yeonjae.kr`

## 사용 예시

### 헬스체크
```bash
curl https://rhythmeet-be.yeonjae.kr/scraper/health
```

### 시간표 데이터 가져오기
```bash
# 성공 예시
curl "https://rhythmeet-be.yeonjae.kr/scraper/timetable?url=https://everytime.kr/timetable/valid-id"

# 실패 예시 (테스트용)
curl "https://rhythmeet-be.yeonjae.kr/scraper/timetable?url=test"
```

### JavaScript에서 사용
```javascript
// 헬스체크
const healthCheck = async () => {
  const response = await fetch('https://rhythmeet-be.yeonjae.kr/scraper/health');
  const data = await response.json();
  console.log(data);
};

// 시간표 데이터 가져오기
const getTimetable = async (url) => {
  try {
    const response = await fetch(`https://rhythmeet-be.yeonjae.kr/scraper/timetable?url=${encodeURIComponent(url)}`);
    const data = await response.json();
    
    if (data.success) {
      console.log('시간표 데이터:', data.data.timetableData);
    } else {
      console.error('에러:', data.message);
    }
  } catch (error) {
    console.error('네트워크 에러:', error);
  }
};
```

## 배포 및 운영

서버 설정, 빌드, 배포에 관한 상세한 내용은 [DEPLOYMENT.md](DEPLOYMENT.md)를 참조하세요.

## 라이센스

MIT License

## 문의

- 개발자: [JandiGoorm](https://github.com/JandiGoorm)
- 이슈 리포트: [GitHub Issues](https://github.com/JandiGoorm/jandi_band_py/issues)