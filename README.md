# Flask 에브리타임 시간표 스크래핑 서버

에브리타임 시간표 URL을 받아서 시간표 데이터를 스크래핑하는 REST API 서버입니다.  
Playwright를 사용하여 동적 웹페이지를 안정적으로 스크래핑하며, Docker 컨테이너와 Jenkins CI/CD를 통해 자동 배포됩니다.

## 주요 기능

- ✅ 에브리타임 시간표 URL 스크래핑
- ✅ CORS 지원으로 웹 애플리케이션에서 직접 호출 가능
- ✅ Docker 컨테이너 기반 배포
- ✅ Jenkins CI/CD 자동 배포
- ✅ Nginx 리버스 프록시 지원
- ✅ Playwright 헤드리스 브라우저 사용
- ✅ 에러 처리 및 상태 코드 관리

## 📋 API 명세서

### Base URL
```
Production: https://your-domain.com/scraper
Development: http://localhost:5001
```

### 🔍 GET /timetable
에브리타임 시간표 데이터를 스크래핑합니다.

#### Request
**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | ✅ | 에브리타임 시간표 공유 URL |

**Example Request:**
```bash
curl "http://localhost:5001/timetable?url=https://everytime.kr/timetable/12345"
```

#### Response

**✅ Success Response (200)**
```json
{
  "success": true,
  "data": {
    "timetable": [
      {
        "subject": "컴퓨터프로그래밍",
        "professor": "김교수",
        "time": "월 09:00-10:30",
        "location": "공학관 101호",
        "credit": 3
      }
    ],
    "semester": "2024-1학기",
    "totalCredits": 18
  },
  "message": "시간표를 성공적으로 불러왔습니다."
}
```

**❌ Error Responses**

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
  "message": "서버 오류가 발생했습니다."
}
```

#### CORS 정책
다음 도메인에서의 요청을 허용합니다:
- `http://localhost:5173` (개발환경)
- `https://rhythmeet-be.yeonjae.kr`
- `https://*.yeonjae.kr`

## 🛠️ 기술 스택

- **Backend**: Python 3.12, Flask, Flask-CORS
- **Scraping**: Playwright (Chromium)
- **Containerization**: Docker
- **CI/CD**: Jenkins
- **Reverse Proxy**: Nginx
- **Process Management**: Docker Container Restart Policies

## 🏗️ 아키텍처 구조

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Request  │───▶│  Nginx Proxy    │───▶│  Flask App      │
│                 │    │  (Port 80/443)  │    │  (Port 5001)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                ▲                       ▲
                                │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub Repo   │───▶│  Jenkins CI/CD  │───▶│  Docker Host    │
│                 │    │  (Container)    │    │  (Host System)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🐳 Docker 설정

### Dockerfile 구조 및 이유

```dockerfile
FROM python:3.12-slim
# → 경량화된 Python 베이스 이미지 사용 (보안 및 성능)

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1    # 실시간 로그 출력
ENV PYTHONDONTWRITEBYTECODE=1  # .pyc 파일 생성 방지
ENV FLASK_ENV=production  # 프로덕션 모드 설정

# 시스템 의존성 설치
RUN playwright install-deps chromium  # Playwright 시스템 라이브러리 (root 권한 필요)

# 보안: 비특권 사용자 생성 및 전환
USER scraper
RUN playwright install chromium  # 브라우저 바이너리 (사용자 권한으로 설치)
```

**주요 설계 원칙:**
1. **보안**: 비특권 사용자로 애플리케이션 실행
2. **최적화**: 레이어 캐싱을 고려한 COPY 순서
3. **안정성**: Playwright 의존성을 단계별로 설치
4. **모니터링**: 헬스체크 및 로깅 설정

### 컨테이너 실행 명령어
```bash
# 개발환경
docker build -t flask-scraper:latest .
docker run -d --name flask-scraper-app -p 5001:5001 flask-scraper:latest

# 프로덕션 환경 (Jenkins에서 자동 실행)
docker run -d \
  --name flask-scraper-app \
  --restart unless-stopped \
  -p 5001:5001 \
  -e FLASK_ENV=production \
  -e PYTHONUNBUFFERED=1 \
  flask-scraper:latest
```

## 🔄 Jenkins CI/CD 설정

### Pipeline 구조 및 이유

Jenkins는 다음과 같은 이유로 Docker 컨테이너 방식을 사용합니다:

1. **Jenkins 컨테이너** → **호스트 Docker 소켓** → **Flask 컨테이너**
2. Docker-in-Docker가 아닌 **호스트 Docker 공유** 방식 사용
3. 이유: 성능상 이점, 복잡도 감소, 리소스 효율성

### Jenkinsfile 주요 단계

```groovy
pipeline {
    agent any
    
    environment {
        IMAGE_NAME = 'flask-scraper'
        CONTAINER_NAME = 'flask-scraper-app'
        HOST_PORT = '5001'
    }
    
    stages {
        stage('Checkout') {
            // GitHub에서 최신 코드 가져오기
        }
        
        stage('Build and Deploy') {
            // 1. 기존 컨테이너 정리
            // 2. 새 Docker 이미지 빌드
            // 3. 새 컨테이너 실행
            // 4. 헬스체크 수행
        }
    }
}
```

### Jenkins 서버 설정

#### 1. Jenkins Docker 컨테이너 실행
```bash
# Jenkins 컨테이너에서 호스트 Docker 사용하도록 설정
docker run -d \
  --name jenkins \
  -p 8080:8080 \
  -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(which docker):/usr/bin/docker \
  jenkins/jenkins:lts

# Jenkins 사용자에게 Docker 권한 부여
docker exec -u root jenkins usermod -aG docker jenkins
docker restart jenkins
```

**왜 이렇게 설정하는가?**
- `-v /var/run/docker.sock:/var/run/docker.sock`: 호스트 Docker 소켓 공유
- `-v $(which docker):/usr/bin/docker`: Docker CLI 바이너리 공유
- Jenkins 컨테이너에서 호스트의 Docker를 직접 사용 가능

#### 2. 필요한 Jenkins 플러그인
```bash
# Jenkins 관리 → 플러그인 관리에서 설치
- Docker Pipeline Plugin
- Git Plugin
- Pipeline Plugin
- Credentials Plugin
- Blue Ocean (선택사항)
```

#### 3. GitHub Credentials 설정
```bash
# Jenkins 관리 → Credentials → System → Global credentials
# Kind: Username with password
# ID: github-credentials
# Username: your-github-username
# Password: your-github-token
```

### Pipeline Job 생성
1. **New Item** → **Pipeline** 선택
2. **Pipeline** 섹션에서:
   - Definition: **Pipeline script from SCM**
   - SCM: **Git**
   - Repository URL: `https://github.com/JandiGoorm/jandi_band_py.git`
   - Credentials: **github-credentials**
   - Branch: ***/master**
   - Script Path: **Jenkinsfile**

## 🌐 Nginx 리버스 프록시 설정

### 설정 목적 및 이유

1. **포트 통합**: 모든 서비스를 80/443 포트로 통합
2. **SSL 종료**: HTTPS 인증서 중앙 관리
3. **로드 밸런싱**: 필요시 여러 인스턴스로 확장 가능
4. **보안**: 내부 서비스 포트 숨김
5. **정적 파일 서빙**: Nginx의 고성능 정적 파일 처리

### nginx.conf 설정

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # Flask 스크래핑 API
    location /scraper/ {
        proxy_pass http://localhost:5001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS 헤더 (필요시)
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
        add_header Access-Control-Allow-Headers "Content-Type, Authorization";
    }
    
    # Jenkins CI/CD
    location /jenkins/ {
        proxy_pass http://localhost:8080/jenkins/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # 헬스체크
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

### SSL 설정 (Let's Encrypt)
```bash
# Certbot 설치
sudo apt install -y certbot python3-certbot-nginx

# SSL 인증서 발급
sudo certbot --nginx -d your-domain.com

# 자동 갱신 설정
sudo crontab -e
# 추가: 0 12 * * * /usr/bin/certbot renew --quiet
```

## 🚀 배포 가이드

### 1. 서버 초기 설정

#### EC2 인스턴스 설정
```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# Docker 설치
sudo apt install -y docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# Nginx 설치
sudo apt install -y nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# 방화벽 설정
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

#### 디렉토리 구조 생성
```bash
mkdir -p ~/services/{jenkins,flask-app,nginx}
```

### 2. Jenkins 설정 및 실행

```bash
# Jenkins 컨테이너 실행
cd ~/services/jenkins
docker run -d \
  --name jenkins \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(which docker):/usr/bin/docker \
  jenkins/jenkins:lts

# 초기 관리자 비밀번호 확인
docker logs jenkins
```

### 3. Nginx 설정 적용

```bash
# 설정 파일 복사
sudo cp nginx.conf /etc/nginx/sites-available/default

# 설정 테스트
sudo nginx -t

# Nginx 재시작
sudo systemctl restart nginx
```

### 4. 애플리케이션 배포

#### 자동 배포 (Jenkins Pipeline)
1. Jenkins 웹 인터페이스 접속: `http://your-domain.com:8080`
2. Pipeline Job 생성 (위의 Jenkins 설정 참조)
3. **Build Now** 클릭하여 배포 실행

#### 수동 배포 (개발/테스트용)
```bash
# 저장소 클론
git clone https://github.com/JandiGoorm/jandi_band_py.git ~/flask-app
cd ~/flask-app

# Docker 빌드 및 실행
docker build -t flask-scraper:latest .
docker run -d \
  --name flask-scraper-app \
  --restart unless-stopped \
  -p 5001:5001 \
  -e FLASK_ENV=production \
  flask-scraper:latest
```

## 🔍 모니터링 및 관리

### 로그 확인
```bash
# Flask 애플리케이션 로그
docker logs -f flask-scraper-app

# Jenkins 로그
docker logs -f jenkins

# Nginx 로그
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# 시스템 리소스 모니터링
docker stats
htop
```

### 헬스체크
```bash
# 애플리케이션 상태 확인
curl http://localhost:5001/timetable?url=test

# Nginx 프록시를 통한 확인
curl http://your-domain.com/scraper/timetable?url=test

# 컨테이너 상태 확인
docker ps -a
docker inspect flask-scraper-app
```

### 트러블슈팅

#### 컨테이너 재시작
```bash
docker restart flask-scraper-app
docker restart jenkins
```

#### 이미지 재빌드
```bash
docker stop flask-scraper-app
docker rm flask-scraper-app
docker rmi flask-scraper:latest
# Jenkins Pipeline 재실행 또는 수동 빌드
```

#### 로그 분석
```bash
# 에러 로그 확인
docker logs flask-scraper-app | grep -i error

# 마지막 100줄 로그
docker logs --tail 100 flask-scraper-app

# 실시간 로그 모니터링
docker logs -f flask-scraper-app
```

## 🔒 보안 고려사항

### 1. 컨테이너 보안
- ✅ 비특권 사용자로 애플리케이션 실행
- ✅ 최소한의 시스템 패키지만 설치
- ✅ 정기적인 베이스 이미지 업데이트

### 2. 네트워크 보안
- ✅ 방화벽으로 필요한 포트만 개방
- ✅ Nginx 리버스 프록시로 내부 포트 숨김
- ✅ SSL/TLS 암호화 적용

### 3. 접근 제어
- ✅ Jenkins 관리자 계정 보안
- ✅ GitHub 토큰 기반 인증
- ✅ 환경 변수로 민감 정보 관리

### 4. 모니터링
- ✅ 접근 로그 모니터링
- ✅ 실패한 요청 추적
- ✅ 리소스 사용량 모니터링

## 📊 성능 최적화

### 1. Docker 최적화
```dockerfile
# 멀티스테이지 빌드 (필요시)
# 이미지 레이어 캐싱 최적화
# 불필요한 파일 제거
```

### 2. 애플리케이션 최적화
- Playwright 브라우저 인스턴스 재사용
- 적절한 타임아웃 설정
- 에러 처리 및 재시도 로직

### 3. 인프라 최적화
- Nginx 캐싱 설정
- 적절한 리소스 제한 설정
- 로그 로테이션 설정

## 📋 체크리스트

### 배포 전 확인사항
- [ ] GitHub 저장소 접근 권한 확인
- [ ] Jenkins Credentials 설정 완료
- [ ] Docker 및 Nginx 설치 완료
- [ ] 방화벽 설정 확인
- [ ] 도메인 및 DNS 설정 (필요시)

### 배포 후 확인사항
- [ ] 애플리케이션 정상 실행 확인
- [ ] API 엔드포인트 응답 확인
- [ ] Jenkins Pipeline 정상 동작 확인
- [ ] Nginx 프록시 정상 동작 확인
- [ ] SSL 인증서 적용 확인 (필요시)

## 🤝 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 라이센스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 📞 문의

- 개발자: [JandiGoorm](https://github.com/JandiGoorm)
- 이슈 리포트: [GitHub Issues](https://github.com/JandiGoorm/jandi_band_py/issues)
