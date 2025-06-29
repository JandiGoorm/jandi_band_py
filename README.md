# FastAPI 에브리타임 시간표 불러오기 서버

에브리타임 시간표 URL을 받아서 시간표 데이터를 불러오는 REST API 서버입니다.
Docker 컨테이너와 Jenkins CI/CD를 통해 자동 배포됩니다.

## 주요 기능 및 특징

- 에브리타임 시간표 공유 URL을 통한 시간표 데이터 불러오기
- 비동기 처리를 통한 빠른 응답 속도 (~0.1초)

## 기술 스택

- Python 3.12
- FastAPI
- Docker
- Jenkins

## API 명세서

### Base URL
```
Production: https://rhythmeet-be.yeonjae.kr/scraper
Development: http://localhost:5001
```

### Endpoints

#### GET /health
서비스 상태를 확인하는 헬스체크 엔드포인트입니다.

**Response:**
```json
{
  "status": "healthy",
  "service": "fastapi-scraper"
}
```

#### GET /timetable
에브리타임 시간표 데이터를 조회합니다.

**Request:**
- **Query Parameters:**
  - `url` (string, required): 에브리타임 시간표 공유 URL
  - 예시: `https://everytime.kr/@username`

**URL 검증:**
- URL은 반드시 `everytime.kr` 도메인이어야 함
- 다른 도메인의 URL은 400 에러 반환

**Success Response (200):**
```json
{
  "success": true,
  "message": "유저 시간표 불러오기 성공",
  "data": {
    "timetableData": {
      "Mon": ["07:00", "07:30", "08:00", "08:30", "09:00", "09:30", "10:00", "10:30"...],
      "Tue": ["10:00", "10:30", "11:00", "11:30", "12:00", "12:30"...],
      "Wed": ["14:00", "14:30", "15:00", "15:30", "16:00", "16:30"...],
      "Thu": ["07:00", "07:30", "08:00", "08:30", "09:00", "09:30", "10:00", "10:30"...],
      "Fri": ["13:00", "13:30", "14:00", "14:30", "15:00", "15:30"...],
      "Sat": ["07:00", "07:30", "08:00", "08:30", "09:00", "09:30", "10:00", "10:30"...],
      "Sun": ["07:00", "07:30", "08:00", "08:30", "09:00", "09:30", "10:00", "10:30"...],
    }
  }
}
```

**응답 데이터 설명:**
- `timetableData`: 각 요일별 **사용 가능한** 시간 목록 (강의 시간의 여집합)
- 시간 범위: 07:00 ~ 23:30 (30분 단위)
- 시간 형식: "HH:MM" (24시간 형식)

**Error Responses:**

| Status Code | Description | Response |
|-------------|-------------|----------|
| 400 | 잘못된 URL | `{"success": false, "message": "지정되지 않은 URL입니다."}` |
| 400 | 유효하지 않은 URL | `{"success": false, "message": "유효하지 않은 URL입니다. identifier를 찾을 수 없습니다."}` |
| 400 | 비공개 시간표 | `{"success": false, "message": "공개되지 않은 시간표입니다."}` |
| 500 | 서버 오류 | `{"success": false, "message": "서버 오류: {오류내용}"}` |

### CORS 정책
다음 도메인에서의 요청을 허용합니다:
- `http://localhost:5173` (개발환경)
- `https://rhythmeet-be.yeonjae.kr`
- `https://*.yeonjae.kr`
- `https://rhythmeet.netlify.app`

## 로컬 개발 환경 설정

### 요구사항
- Python 3.12 이상
- Docker

### 설치 및 실행

1. **저장소 클론**
   ```bash
   git clone https://github.com/JandiGoorm/jandi_band_py.git
   cd jandi_band_py
   ```

2. **가상환경 설정 (권장)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **의존성 설치**
   ```bash
   pip install -r requirements.txt
   ```

4. **서버 실행**
   ```bash
   python app.py
   ```

### Docker로 실행

```bash
# 이미지 빌드
docker build -t fastapi-scraper:latest .

# 컨테이너 실행
docker run -d \
  --name fastapi-scraper-app \
  -p 5001:5001 \
  -e PYTHONUNBUFFERED=1 \
  fastapi-scraper:latest
```

## 사용 예시

### cURL 예시
```bash
# 헬스체크
curl https://rhythmeet-be.yeonjae.kr/scraper/health

# 시간표 불러오기
curl "https://rhythmeet-be.yeonjae.kr/scraper/timetable?url=https://everytime.kr/@username"
```

### JavaScript 예시
```javascript
// 시간표 데이터 가져오기
async function getTimetable(everyTimeUrl) {
  try {
    const response = await fetch(
      `https://rhythmeet-be.yeonjae.kr/scraper/timetable?url=${encodeURIComponent(everyTimeUrl)}`
    );
    const data = await response.json();

    if (data.success) {
      console.log('사용 불가능한 시간:', data.data.timetableData);
      return data.data.timetableData;
    } else {
      console.error('에러:', data.message);
      throw new Error(data.message);
    }
  } catch (error) {
    console.error('네트워크 에러:', error);
    throw error;
  }
}

// 사용 예시
getTimetable('https://everytime.kr/@username')
  .then(timetable => {
    console.log('월요일 사용 불가능한 시간:', timetable.Mon);
  });
```

## 성능 및 최적화

### 현재 성능 지표
- **응답 시간**: ~100ms (네트워크 지연 포함)
- **메모리 사용량**: ~50MB

### 최적화 기법
1. **비동기 처리**: httpx AsyncClient 사용
2. **연결 재사용**: HTTP 연결 풀링
3. **효율적인 XML 파싱**: lxml 라이브러리
4. **리소스 관리**: lifespan을 통한 적절한 정리

## 주의사항: 개인정보 보호

### ⚠️ 중요! 본인의 시간표만 사용하세요

본 서비스는 **반드시 본인의 에브리타임 시간표 URL만 사용**해야 합니다.

**법적 고지:**
- 본 서비스는 개인정보 자기결정권을 존중하며, 사용자 본인의 정보 활용을 전제로 합니다.
- 다른 사람의 시간표 정보를 무단으로 활용하는 것은 법적인 문제가 될 수 있습니다.
