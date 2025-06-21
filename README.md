# FastAPI 에브리타임 시간표 불러오기 서버

에브리타임 시간표 URL을 받아서 시간표 데이터를 불러오는 REST API 서버입니다.
에브리타임 API를 직접 호출하여 XML 응답을 파싱하며, Docker 컨테이너와 Jenkins CI/CD를 통해 자동 배포됩니다.

## 주요 기능

- 에브리타임 시간표 URL 스크래핑 (API 직접 호출)
- CORS 지원으로 웹 애플리케이션에서 직접 호출 가능
- Docker 컨테이너 기반 배포
- Jenkins CI/CD 자동 배포
- 고성능 HTTP 클라이언트 사용 (httpx)
- XML 응답 파싱 (xmltodict)
- 에러 처리 및 상태 코드 관리

## 기술 스택

- **Backend**: Python 3.12, FastAPI, Uvicorn
- **HTTP Client**: httpx (비동기 HTTP 클라이언트)
- **XML Parsing**: xmltodict
- **Containerization**: Docker
- **CI/CD**: Jenkins
- **Reverse Proxy**: Nginx

## 프로젝트 구조

```
jandi_band_py/
├── app.py                      # FastAPI 애플리케이션 메인 파일
├── requirements.txt            # Python 의존성
├── Dockerfile                  # Docker 이미지 빌드 설정
├── Jenkinsfile                 # CI/CD 파이프라인 설정
├── service/                    # 비즈니스 로직
│   ├── __init__.py
│   └── scraper.py              # 시간표 스크래핑 로직 (API 직접 호출)
├── ARCHITECTURE.md             # 아키텍처 문서
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
  "service": "fastapi-scraper"
}
```

### GET /timetable
에브리타임 시간표 데이터를 스크래핑합니다.

#### Request
**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | 에브리타임 시간표 공유 URL |

**URL 검증 규칙:**
- URL은 반드시 `https://everytime.kr/`로 시작해야 함
- 다른 도메인의 URL은 "지정되지 않은 URL" 에러 반환

**Example Request:**
```bash
curl "https://rhythmeet-be.yeonjae.kr/scraper/timetable?url=https://everytime.kr/@user123"
```

#### Response

**Success Response (200)**
```json
{
  "success": true,
  "message": "유저 시간표 불러오기 성공",
  "data": {
    "timetableData": {
      "Mon": ["07:00", "07:30", "08:00", "08:30", "09:00", "09:30", "10:00", "10:30"],
      "Tue": ["10:00", "10:30", "11:00", "11:30", "12:00", "12:30"],
      "Wed": ["14:00", "14:30", "15:00", "15:30", "16:00", "16:30"],
      "Thu": [],
      "Fri": ["13:00", "13:30", "14:00", "14:30", "15:00", "15:30"],
      "Sat": [],
      "Sun": []
    }
  }
}
```

**응답 데이터 설명:**
- `timetableData`: 각 요일별 사용 불가능한 시간 목록 (30분 단위)
- 시간 범위: 07:00 ~ 23:30 (30분 간격)
- 빈 배열 `[]`: 해당 요일에 사용 가능한 시간이 없음 (모든 시간이 사용 가능)
- 시간 형식: "HH:MM" (24시간 형식)

**Error Responses**

**400 Bad Request - 잘못된 URL**
```json
{
  "success": false,
  "message": "지정되지 않은 URL입니다."
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
- `https://rhythmeet.netlify.app`

## 사용 예시

### 헬스체크
```bash
curl https://rhythmeet-be.yeonjae.kr/scraper/health
```

### 시간표 데이터 가져오기
```bash
# 성공 예시
curl "https://rhythmeet-be.yeonjae.kr/scraper/timetable?url=https://everytime.kr/@user123"

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

## 아키텍처 개선점

### API 직접 호출 방식 (Playwright → httpx + xmltodict)

**이전 방식 (Playwright):**
- 브라우저 자동화를 통한 DOM 조작
- 높은 메모리 사용량 (~800MB)
- 긴 응답 시간 (3-5초)
- 복잡한 브라우저 관리 시스템

**현재 방식 (API 직접 호출):**
- 에브리타임 API 직접 호출 (`https://api.everytime.kr`)
- 낮은 메모리 사용량 (~100MB)
- 빠른 응답 시간 (~0.1-0.5초)
- 단순한 HTTP 클라이언트 시스템

### 성능 개선 결과
- **응답 시간**: 90% 단축 (3-5초 → 0.1-0.5초)
- **메모리 사용량**: 87% 감소 (800MB → 100MB)
- **Docker 이미지 크기**: 86% 감소 (1.5GB → 200MB)

## 배포 및 운영

서버 설정, 빌드, 배포에 관한 상세한 내용은 [DEPLOYMENT.md](DEPLOYMENT.md)를 참조하세요.

## 라이센스

MIT License

## 문의

- 개발자: [JandiGoorm](https://github.com/JandiGoorm)
- 이슈 리포트: [GitHub Issues](https://github.com/JandiGoorm/jandi_band_py/issues)
