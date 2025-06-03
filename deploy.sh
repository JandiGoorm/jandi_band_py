#!/bin/bash

# Flask 앱 배포 스크립트
set -e

echo "🚀 Flask 스크래핑 서버 배포 시작..."

# 변수 설정
APP_DIR="/home/ubuntu/flask-app"
REPO_URL="https://github.com/your-username/your-repo.git"  # 실제 저장소 URL로 변경
BRANCH="main"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 애플리케이션 디렉토리 설정
setup_app_directory() {
    log_info "애플리케이션 디렉토리 설정 중..."
    
    if [ ! -d "$APP_DIR" ]; then
        log_info "flask-app 디렉토리 생성 중..."
        sudo mkdir -p "$APP_DIR"
        cd "$APP_DIR"
        git clone "$REPO_URL" .
        
        # docker-compose.yml 생성
        if [ ! -f "docker-compose.yml" ]; then
            log_info "docker-compose.yml 생성 중..."
            cp docker-compose.template.yml docker-compose.yml
        fi
    else
        log_info "기존 코드 업데이트 중..."
        cd "$APP_DIR"
        git fetch origin
        git reset --hard "origin/$BRANCH"
        
        # docker-compose.yml이 없으면 템플릿에서 생성
        if [ ! -f "docker-compose.yml" ]; then
            log_info "docker-compose.yml 생성 중..."
            cp docker-compose.template.yml docker-compose.yml
        fi
    fi
}

# 기존 서비스 중지
stop_existing_service() {
    log_info "기존 서비스 중지 중..."
    cd "$APP_DIR"
    docker-compose down || log_warn "기존 서비스가 실행 중이지 않습니다."
}

# Docker 이미지 빌드
build_docker_image() {
    log_info "Docker 이미지 빌드 중..."
    cd "$APP_DIR"
    docker build -t flask-scraper:latest .
}

# 서비스 시작
start_service() {
    log_info "서비스 시작 중..."
    cd "$APP_DIR"
    docker-compose up -d
    
    # 서비스 시작 대기
    log_info "서비스 시작 대기 중..."
    sleep 30
    
    # 헬스체크
    if curl -f http://localhost:5001/timetable?url=test &> /dev/null; then
        log_info "✅ 서비스가 성공적으로 시작되었습니다!"
    else
        log_error "❌ 서비스 시작에 실패했습니다."
        docker-compose logs
        exit 1
    fi
}

# 정리 작업
cleanup() {
    log_info "정리 작업 중..."
    docker image prune -f
}

# 상태 확인
check_status() {
    log_info "서비스 상태 확인 중..."
    cd "$APP_DIR"
    docker-compose ps
    
    echo ""
    log_info "서비스 정보:"
    echo "- Flask 앱: http://localhost:5001"
    echo "- 공개 URL: https://rhythmeet-be.yeonjae.kr/scraper/"
    echo "- 헬스체크: http://localhost:5001/timetable?url=test"
    echo "- 로그 확인: cd $APP_DIR && docker-compose logs -f"
}

# 메인 실행
main() {
    log_info "Flask 스크래핑 서버 배포를 시작합니다..."
    
    setup_app_directory
    stop_existing_service
    build_docker_image
    start_service
    cleanup
    check_status
    
    log_info "🎉 배포가 완료되었습니다!"
}

# 스크립트 실행
main "$@" 