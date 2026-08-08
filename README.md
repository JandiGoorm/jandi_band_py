# Jandi Band Py - 에브리타임 시간표 스크래퍼

jandi_band_backend를 위한 서브 서버로, 에브리타임 시간표 URL을 파싱하여 시간표 정보를 제공합니다.

## 주요 기능

- **시간표 스크래핑**: 에브리타임 공유 URL에서 시간표 데이터 추출
- **API 제공**: FastAPI 기반 REST API
- **헬스체크**: 서비스 상태 확인 엔드포인트

---

## 기술 스택

| 구분 | 기술 |
|:-----|:-----|
| **Language** | Python 3.12 |
| **Framework** | FastAPI, Uvicorn |
| **Libraries** | httpx, lxml, pydantic |
| **Infra** | Docker, Jenkins (`home-server`에서 중앙 관리) |

---

## 프로젝트 구조

```
jandi_band_py/
├── app.py                  # FastAPI 애플리케이션
├── service/
│   ├── __init__.py
│   └── scraper.py          # 시간표 스크래핑 로직
├── requirements.txt        # Python 의존성
├── Dockerfile              # Docker 이미지 빌드
└── README.md
```

---

## 네이티브 환경에서 실행

### 사전 요구사항

- Python 3.12

### 실행 방법

```bash
# 1. 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 서버 실행
python app.py
# 또는
uvicorn app:app --reload --host 0.0.0.0 --port 5001
```

**접속 URL**
- API 서버: http://localhost:5001
- 헬스체크: http://localhost:5001/health

---

## 네이티브 환경에서 테스트

```bash
# 헬스체크 테스트
curl http://localhost:5001/health

# 시간표 조회 테스트 (에브리타임 공유 URL 필요)
curl "http://localhost:5001/timetable?url=https://everytime.kr/timetable/share/xxxxxx"
```

---

## Docker 환경에서 실행

```bash
# 1. 이미지 빌드
docker build -t jandi-band-py:local .

# 2. 컨테이너 실행
docker run -d \
  --name jandi-band-py \
  -p 5001:5001 \
  jandi-band-py:local

# 3. 로그 확인
docker logs -f jandi-band-py

# 4. 컨테이너 중지 및 삭제
docker stop jandi-band-py && docker rm jandi-band-py
```

---

## Docker 환경에서 테스트

```bash
# 헬스체크 테스트
docker exec jandi-band-py curl http://localhost:5001/health

# 또는 호스트에서
curl http://localhost:5001/health
```

---

## GHCR에 이미지 Push

### 수동 Push

```bash
# 1. GHCR 로그인
echo $GITHUB_TOKEN | docker login ghcr.io -u kyj0503 --password-stdin

# 2. 이미지 빌드
docker build --platform linux/amd64 -t ghcr.io/kyj0503/jandi-band-py:latest .

# 3. Push
docker push ghcr.io/kyj0503/jandi-band-py:latest
```

### 중앙 CI/CD (Jenkins)

파이프라인 정의는 `home-server/cicd/jenkins/pipeline/jandi-band-py/`에서 관리합니다.
Jenkins의 `jandi-band-py` Job을 수동 실행하고 `APP_ENV`를 선택합니다.

- `dev`: `dev` 브랜치를 빌드해 `:dev` 이미지로 Push
- `prod`: `main` 브랜치를 빌드해 `:latest` 이미지로 Push한 뒤 배포 및 헬스 체크

---

## API 엔드포인트

### GET /health

서비스 상태 확인

**Response**
```json
{
  "status": "healthy",
  "service": "fastapi-scraper"
}
```

### GET /timetable

에브리타임 시간표 조회

**Parameters**
- `url` (required): 에브리타임 시간표 공유 URL

**Example**
```bash
curl "http://localhost:5001/timetable?url=https://everytime.kr/timetable/share/xxxxxx"
```

---

## 커밋 컨벤션

### 기본 포맷

```
태그(스코프): 제목 (50자 내외)

- 본문 (선택 사항)
```

### 스코프 (Scope)

| 스코프 | 설명 |
|:-------|:-----|
| `be` | Backend 관련 코드 |
| `infra` | 배포, Docker, CI/CD 등 |

### 태그 (Type)

| 태그 | 설명 | 예시 |
|:-----|:-----|:-----|
| `feat` | 새로운 기능 추가 | API 개발 |
| `fix` | 버그 수정 | 로직 오류 수정 |
| `docs` | 문서 수정 | README |
| `style` | 코드 포맷팅 | 들여쓰기 정렬 |
| `refactor` | 코드 리팩토링 | 구조 개선 |
| `test` | 테스트 코드 | 테스트 추가/수정 |
| `chore` | 기타 잡무 | 빌드 설정 |

### 예시

```
feat(be): 시간표 파싱 로직 개선
fix(be): 에브리타임 URL 검증 오류 수정
chore(infra): Dockerfile 최적화
```

---

## 운영 환경

- Jenkins 파이프라인 정의와 운영 환경 배포는 **home-server** 리포지토리에서 중앙 관리
- jandi-band-backend와 함께 실행되어야 함
