# Flask 스크래핑 서버 배포 가이드

> **주의**: 현재 프로젝트는 Jenkins CI/CD를 통한 **자동 배포**가 구축되어 있습니다.  
> 일반적으로는 코드를 푸시하면 자동으로 배포되므로 수동 배포는 필요하지 않습니다.

## 🚀 자동 배포 (권장)

### 배포 프로세스
```mermaid
graph LR
    A[코드 Push] --> B[GitHub Webhook]
    B --> C[Jenkins 빌드 트리거]
    C --> D[Docker 이미지 빌드]
    D --> E[컨테이너 배포]
    E --> F[헬스체크]
    F --> G[배포 완료]
```

### 자동 배포 실행
1. **코드 수정 후 푸시**:
   ```bash
   git add .
   git commit -m "Update feature"
   git push origin master
   ```

2. **Jenkins에서 확인**:
   - 접속: https://rhythmeet-be.yeonjae.kr/jenkins/
   - `flask-scraper` 프로젝트에서 빌드 진행 상황 확인

3. **배포 결과 확인**:
   ```bash
   # 서비스 상태 확인
   curl https://rhythmeet-be.yeonjae.kr/scraper/health
   
   # API 테스트
   curl "https://rhythmeet-be.yeonjae.kr/scraper/timetable?url=test"
   ```

## 🔧 Jenkins CI/CD 설정

### Pipeline 상태 확인
- **Jenkins 대시보드**: https://rhythmeet-be.yeonjae.kr/jenkins/
- **빌드 히스토리**: 성공/실패 확인
- **콘솔 출력**: 상세 로그 확인

### GitHub Webhook 확인
- **GitHub 설정**: Repository Settings → Webhooks
- **Webhook URL**: `https://rhythmeet-be.yeonjae.kr/jenkins/github-webhook/`
- **Content type**: `application/json`
- **이벤트**: `Just the push event`

## 🆘 긴급 수동 배포

> Jenkins가 실패했거나 긴급 상황에서만 사용하세요.

### 1. 서버 접속
```bash
ssh ubuntu@your-server-ip
```

### 2. 기존 컨테이너 정리
```bash
# 기존 컨테이너 중지 및 제거
docker stop flask-scraper-app || true
docker rm flask-scraper-app || true

# 기존 이미지 제거 (선택사항)
docker rmi flask-scraper:latest || true
```

### 3. 최신 코드 가져오기
```bash
# 임시 디렉토리에서 작업
cd /tmp
rm -rf jandi_band_py
git clone https://github.com/JandiGoorm/jandi_band_py.git
cd jandi_band_py
```

### 4. 수동 빌드 및 배포
```bash
# Docker 이미지 빌드
docker build -t flask-scraper:latest .

# 컨테이너 실행 (Jenkins와 동일한 방식)
docker run -d \
  --name flask-scraper-app \
  --restart unless-stopped \
  -p 5001:5001 \
  -e FLASK_ENV=production \
  -e PYTHONUNBUFFERED=1 \
  flask-scraper:latest

# 서비스 확인
sleep 30
docker exec flask-scraper-app curl -f http://localhost:5001/health
```

### 5. 상태 확인
```bash
# 컨테이너 상태
docker ps | grep flask-scraper-app

# 로그 확인
docker logs flask-scraper-app --tail 20

# 외부 접근 테스트
curl https://rhythmeet-be.yeonjae.kr/scraper/health
```

## 📊 모니터링

### 서비스 상태 확인
```bash
# 컨테이너 상태
docker ps -a | grep flask-scraper

# 리소스 사용량
docker stats flask-scraper-app

# 로그 실시간 모니터링
docker logs -f flask-scraper-app
```

### Jenkins 빌드 로그
```bash
# Jenkins 컨테이너 로그
docker logs jenkins | tail -50

# 특정 빌드 로그는 Jenkins 웹 인터페이스에서 확인
```

## 🔍 트러블슈팅

### 자동 배포가 실행되지 않는 경우

1. **GitHub Webhook 확인**:
   - Repository → Settings → Webhooks
   - Recent Deliveries에서 응답 확인

2. **Jenkins 설정 확인**:
   - Job 설정에서 "GitHub hook trigger" 체크박스 확인
   - Credentials 설정 확인

### 배포는 성공했지만 서비스가 안 되는 경우

1. **컨테이너 상태 확인**:
   ```bash
   docker ps -a | grep flask-scraper
   docker logs flask-scraper-app
   ```

2. **포트 확인**:
   ```bash
   netstat -tlnp | grep 5001
   ```

3. **Nginx 설정 확인**:
   ```bash
   sudo nginx -t
   sudo systemctl status nginx
   ```

### 긴급 복구

```bash
# 마지막 성공한 이미지로 롤백 (있는 경우)
docker images | grep flask-scraper
docker run -d --name flask-scraper-app --restart unless-stopped -p 5001:5001 flask-scraper:previous-tag

# 또는 Jenkins에서 마지막 성공한 빌드 재실행
```

## 📝 환경 정보

### 현재 배포 환경
- **서버**: EC2 (Ubuntu)
- **도메인**: rhythmeet-be.yeonjae.kr
- **포트 매핑**: 
  - Jenkins: 8080 → /jenkins/
  - Flask API: 5001 → /scraper/
  - Nginx: 80, 443
- **SSL**: Let's Encrypt 자동 갱신

### 주요 URL
- **API 베이스**: https://rhythmeet-be.yeonjae.kr/scraper/
- **헬스체크**: https://rhythmeet-be.yeonjae.kr/scraper/health
- **Jenkins**: https://rhythmeet-be.yeonjae.kr/jenkins/
- **시스템 헬스**: https://rhythmeet-be.yeonjae.kr/health

## ⚠️ 주의사항

1. **수동 배포는 최후의 수단**: Jenkins CI/CD가 실패했을 때만 사용
2. **환경 일관성**: 수동 배포 시에도 Jenkins와 동일한 명령어 사용
3. **백업**: 중요한 변경 전에는 현재 상태 백업
4. **로그 보관**: 문제 발생 시 디버깅을 위해 로그 보관

---

> 💡 **팁**: 대부분의 경우 코드를 푸시하기만 하면 자동으로 배포됩니다!  
> 문제가 있을 때만 이 가이드를 참고하세요. 