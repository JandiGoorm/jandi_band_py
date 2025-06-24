#!/bin/bash

# AWS Lambda 배포 스크립트
# 사용법: ./deploy.sh [stage]

set -e

STAGE=${1:-dev}
echo "🚀 Stage: $STAGE 환경으로 배포를 시작합니다."

# 필요한 도구 확인
if ! command -v serverless &> /dev/null; then
    echo "❌ Serverless Framework가 설치되지 않았습니다."
    echo "npm install -g serverless 명령으로 설치해주세요."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Docker가 설치되지 않았습니다."
    echo "lxml 패키지 빌드를 위해 Docker가 필요합니다."
    exit 1
fi

# AWS CLI 인증 확인
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI 인증이 설정되지 않았습니다."
    echo "aws configure 명령으로 인증을 설정해주세요."
    exit 1
fi

echo "✅ 필요한 도구들이 모두 설치되어 있습니다."

# Python 가상환경 확인
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  가상환경이 활성화되지 않았습니다."
    echo "venv를 활성화하는 것을 권장합니다."
fi

# serverless-python-requirements 플러그인 설치
echo "📦 Serverless 플러그인을 설치합니다."
serverless plugin install -n serverless-python-requirements

# 배포 실행
echo "🔧 Lambda 함수를 배포합니다."
serverless deploy --stage $STAGE --verbose

# 배포 정보 출력
echo "✅ 배포가 완료되었습니다!"
echo "📋 배포 정보를 확인합니다."
serverless info --stage $STAGE

# Health check 테스트
echo "🏥 Health check를 수행합니다."
ENDPOINT=$(serverless info --stage $STAGE --verbose | grep -oE 'https://[^/]+\.execute-api\.[^/]+\.amazonaws\.com/[^/]+' | head -1)

if [ ! -z "$ENDPOINT" ]; then
    echo "🌐 엔드포인트: $ENDPOINT"
    curl -f "$ENDPOINT/health" && echo "" || echo "❌ Health check 실패"
else
    echo "⚠️  엔드포인트를 찾을 수 없습니다."
fi

echo "🎉 배포 완료!"
