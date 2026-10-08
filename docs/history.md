# 변경 이력

## 2026-10-09

- Tailscale 연결 옵션 중복을 제거하고, 연결 후 별도 명령으로 실행기의 서브넷 경로 수신을 해제했다.
- main의 Jenkinsfile 제거를 반영하고, README는 GitHub Actions 배포 안내로 유지했다.

## 2026-10-08

- 배포 작업에 Tailscale OIDC 연결과 SSH 전용 접근 설정을 추가했다.
- main/dev 별 GitHub Actions 배포와 독립 Compose를 추가했다.
- Docker 테스트 단계와 API 회귀 테스트 3개를 추가했다.
- 서버 `.env` 유지, digest 배포, 실패 시 이전 배포 복구를 구현했다.
