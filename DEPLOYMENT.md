# Flask 스크래핑 서버 배포 가이드

## 🚀 EC2 배포 설정

### 1. 서버 설정 파일 준비

#### docker-compose.yml 생성
```bash
cd /home/ubuntu/flask-app
cp docker-compose.template.yml docker-compose.yml

# 필요시 설정 수정
nano docker-compose.yml
```

#### Nginx 설정 업데이트
```bash
# 기존 설정 백업
sudo cp /etc/nginx/sites-available/default /etc/nginx/sites-available/default.backup

# 새 설정 적용 (nginx-updated.conf 내용 참고)
sudo nano /etc/nginx/sites-available/default

# 설정 확인 및 재시작
sudo nginx -t
sudo systemctl restart nginx
```

### 2. Jenkins Pipeline 설정

1. Jenkins 접속: `https://rhythmeet-be.yeonjae.kr/jenkins/`
2. "New Item" → "Pipeline" 
3. 프로젝트명: `flask-scraper-deploy`
4. Pipeline 설정:
   - Definition: `Pipeline script from SCM`
   - SCM: `Git`
   - Repository URL: `[실제 저장소 URL]`
   - Credentials: `github-credentials`
   - Branch: `*/main`
   - Script Path: `Jenkinsfile`

### 3. 수동 배포

```bash
# 첫 배포
sudo mkdir -p /home/ubuntu/flask-app
cd /home/ubuntu/flask-app
git clone [저장소 URL] .
cp docker-compose.template.yml docker-compose.yml

# Docker 이미지 빌드 및 실행
docker build -t flask-scraper:latest .
docker-compose up -d

# 상태 확인
docker-compose ps
curl http://localhost:5001/timetable?url=test
```

### 4. 서비스 URL

- **Flask API**: `https://rhythmeet-be.yeonjae.kr/scraper/`
- **헬스체크**: `https://rhythmeet-be.yeonjae.kr/scraper/timetable?url=test`

### 5. 모니터링

```bash
# 로그 확인
cd /home/ubuntu/flask-app && docker-compose logs -f

# 서비스 재시작
cd /home/ubuntu/flask-app && docker-compose restart

# 전체 재배포
cd /home/ubuntu/flask-app && docker-compose down && docker-compose up -d
```

## 🔧 환경별 설정

### 개발 환경
- 포트: `5001`
- CORS: `localhost:5173` 허용

### 운영 환경  
- 포트: `5001`
- CORS: `https://rhythmeet-be.yeonjae.kr` 허용
- SSL 적용

## 📝 주의사항

1. **docker-compose.yml은 Git으로 관리하지 않음**
   - 서버별 설정이 다를 수 있음
   - 민감한 정보 포함 가능성

2. **환경변수 관리**
   - 필요시 `.env` 파일 별도 생성
   - 민감한 정보는 서버에서만 관리

3. **백업**
   - 설정 파일들을 정기적으로 백업
   - Docker 이미지 백업 고려 