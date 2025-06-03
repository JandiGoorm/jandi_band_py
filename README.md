# Flask 스크래핑 서버

에브리타임 시간표 스크래핑 API 서버입니다.

## 기능

- 에브리타임 시간표 URL을 받아서 시간표 데이터를 스크래핑
- CORS 지원으로 웹 애플리케이션에서 직접 호출 가능
- Docker 컨테이너로 배포 가능

## API 엔드포인트

### GET /timetable
시간표 데이터를 스크래핑합니다.

**Query Parameters:**
- `url` (required): 에브리타임 시간표 URL

**Response:**
```json
{
  "success": true,
  "data": {
    "timetable": [...],
    "semester": "2024-1"
  }
}
```

## 로컬 개발

### 요구사항
- Python 3.12+
- pip

### 설치 및 실행
```bash
# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium

# 서버 실행
python app.py
```

서버는 `http://localhost:5001`에서 실행됩니다.

## Docker 배포

### 로컬 Docker 실행
```bash
# 이미지 빌드
docker build -t flask-scraper .

# 컨테이너 실행
docker run -p 5001:5001 flask-scraper
```

### Docker Compose 실행
```bash
# 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 서비스 중지
docker-compose down
```

## EC2 배포

### 1. EC2 서버 구조
```
~/home/
├── jenkins/
│   ├── Dockerfile
│   └── docker-compose.yml
├── spring-app/
│   ├── docker-compose.yml
│   └── application.properties
└── flask-app/
    ├── docker-compose.yml
    └── (Git 저장소 파일들)
```

### 2. 배포 준비

#### EC2 서버에 필요한 도구 설치
```bash
# Docker 설치
sudo apt update
sudo apt install -y docker.io docker-compose

# Docker 서비스 시작
sudo systemctl start docker
sudo systemctl enable docker

# 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER
```

#### 애플리케이션 디렉토리 생성
```bash
mkdir -p ~/flask-app
cd ~/flask-app
```

### 3. 자동 배포 스크립트 사용
```bash
# 배포 스크립트 실행 권한 부여
chmod +x deploy.sh

# 배포 실행
./deploy.sh
```

### 4. 수동 배포
```bash
# 저장소 클론 (첫 배포시)
git clone <your-repo-url> ~/flask-app

# 또는 기존 코드 업데이트
cd ~/flask-app
git pull origin main

# Docker 이미지 빌드 및 실행
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 상태 확인
docker-compose ps
curl http://localhost:5001/timetable?url=test
```

## Jenkins CI/CD 설정

### 1. Jenkinsfile 기반 파이프라인 (권장)
- 저장소에 `Jenkinsfile`이 포함되어 있음
- Jenkins에서 "Pipeline" 프로젝트 생성
- SCM을 Git으로 설정하고 저장소 URL 입력
- Script Path를 `Jenkinsfile`로 설정

### 2. Pipeline 스크립트 Job
- Jenkins에서 "Pipeline" 프로젝트 생성
- "Pipeline script" 선택
- `Jenkinsfile` 내용을 복사해서 붙여넣기

### Jenkins 설정 확인사항
```bash
# Jenkins 서버에서 Docker 명령 실행 권한 확인
sudo usermod -aG docker jenkins
sudo systemctl restart jenkins

# 필요한 플러그인
- Docker Pipeline
- Git plugin
- Pipeline plugin
```

## Nginx 리버스 프록시 설정

### 1. Nginx 설치
```bash
sudo apt install -y nginx
```

### 2. 설정 파일 적용
```bash
# 설정 파일 복사
sudo cp nginx.conf /etc/nginx/sites-available/default

# 설정 문법 확인
sudo nginx -t

# Nginx 재시작
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 3. 서비스 접근 URL
- Jenkins: `http://your-domain.com/jenkins/`
- Spring Boot API: `http://your-domain.com/api/`
- Flask 스크래핑 API: `http://your-domain.com/scraper/`

## 모니터링 및 관리

### 로그 확인
```bash
# Flask 앱 로그
cd ~/flask-app && docker-compose logs -f

# 전체 컨테이너 상태
docker ps -a

# 리소스 사용량 확인
docker stats
```

### 트러블슈팅
```bash
# 컨테이너 재시작
cd ~/flask-app && docker-compose restart

# 이미지 재빌드
cd ~/flask-app && docker-compose build --no-cache

# 전체 재배포
cd ~/flask-app && docker-compose down && docker-compose up -d
```

### 백업 및 복구
```bash
# 설정 파일 백업
tar -czf flask-app-backup.tar.gz ~/flask-app/docker-compose.yml ~/flask-app/.env

# Docker 이미지 백업
docker save flask-app_flask-scraper:latest | gzip > flask-app-image.tar.gz
```

## 보안 고려사항

1. **방화벽 설정**: 필요한 포트만 열기
2. **SSL 인증서**: Let's Encrypt 등으로 HTTPS 적용
3. **환경 변수**: 민감한 정보는 `.env` 파일로 관리
4. **컨테이너 보안**: 비특권 사용자로 실행
5. **정기 업데이트**: 베이스 이미지 및 의존성 업데이트

## 라이센스

MIT License
