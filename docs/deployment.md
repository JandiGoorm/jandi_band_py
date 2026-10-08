# 배포

CI/CD와 Compose는 이 저장소에서 관리한다. 서버의 Nginx와 외부 Docker 네트워크 `backend-net`을 함께 사용한다. `home-server` 체크아웃이나 스크립트는 앱 배포에 필요하지 않다.

| 브랜치 | GitHub Environment | 컨테이너 | 주소 |
|---|---|---|---|
| main | production | jandi-band-py | https://rhythmeet-py.yeonjae.kr |
| dev | development | jandi-band-py-dev | https://rhythmeet-dev-py.yeonjae.kr |

PR에서는 Docker 테스트와 실행 이미지 빌드만 수행한다. main/dev push 또는 해당 브랜치의 수동 실행은 검증 후 ARM64 이미지를 GHCR에 올리고 digest로 배포한다. 테스트 실패 시 이미지 배포를 진행하지 않는다.

## GitHub 설정

각 Environment에 다음 항목을 등록한다. 배포 브랜치는 production에 main, development에 dev만 허용한다.

| 종류 | 이름 | 내용 |
|---|---|---|
| Secret | OCI_SSH_KEY | 해당 환경 배포용 SSH 개인키 |
| Variable | OCI_HOST | OCI SSH 호스트 |
| Variable | OCI_USER | SSH 사용자 |
| Variable | OCI_KNOWN_HOSTS | 별도 경로로 검증한 SSH 호스트 공개키 항목 |

GHCR은 작업마다 발급되는 `GITHUB_TOKEN`을 사용한다. 이미지는 `ghcr.io/jandigoorm/jandi-band-py`에 저장하며, 배포 작업은 `packages: read` 권한을 사용한다. 서버로 전달한 임시 레지스트리 인증 파일은 작업 종료 시 삭제한다. 기존 패키지를 재사용할 때는 해당 저장소에 패키지 접근 권한을 부여해야 한다.

## 서버 파일

```text
/opt/jandi-band-py/
  production/
    .env                  # 필요할 때 서버에서 수동 관리
    current -> releases/release.…
    releases/release.…/
      compose.yaml
      deployment.env      # 이미지 digest 등 배포 메타데이터
      scripts/deploy.sh
  development/
    ...
```

현재 Python 앱은 별도 런타임 자격 증명을 사용하지 않는다. `.env`가 없어도 실행하며, 파일이 있으면 Compose가 읽는다. 파일 권한은 600, 환경 디렉터리는 700으로 유지한다. Compose 2.30 이상이 필요하다. `.env`는 `format: raw`로 읽으므로 값에 따옴표를 추가하지 않는다.

배포는 `.env`를 만들거나 덮어쓰지 않는다. 운영과 개발의 Compose 프로젝트 및 컨테이너 이름은 다르다. 서비스 포트는 공용 네트워크에만 열고, 외부 요청은 Nginx로 받는다.

## 상태 확인과 복구

배포 스크립트는 이미지의 ARM64 아키텍처와 소스 리비전, 컨테이너 상태, 잘못된 시간표 도메인의 400 응답을 확인한다. 이후 Nginx 설정 검사와 reload를 수행한다. 실패하면 이전 릴리스를 다시 실행하고 작업 자체는 실패로 남긴다.

첫 전환에서는 기존 컨테이너를 정지하고 `*-pre-actions-*` 이름으로 보존한다. 이전 컨테이너의 자동 재시작은 해제한다. 이후 배포에서는 `current`가 가리키는 릴리스가 복구 기준이다. 예전 릴리스를 수동 실행할 때도 그 디렉터리의 `deployment.env`를 함께 사용한다.

```bash
cd /opt/jandi-band-py/production/current
docker compose --env-file deployment.env -f compose.yaml ps
```

Nginx는 `rhythmeet-py.yeonjae.kr → jandi-band-py:8000`, `rhythmeet-dev-py.yeonjae.kr → jandi-band-py-dev:8000`으로 연결해야 한다. 서버 네트워크와 Nginx를 교체할 경우 이 연결을 유지한다.
