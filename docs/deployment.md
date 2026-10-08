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
| Variable | OCI_HOST | OCI의 Tailscale IPv4 주소 |
| Variable | OCI_USER | SSH 사용자 |
| Variable | OCI_KNOWN_HOSTS | 별도 경로로 검증한 SSH 호스트 공개키 항목 |
| Variable | TS_CLIENT_ID | 해당 저장소·환경의 Tailscale OIDC Client ID |
| Variable | TS_AUDIENCE | Tailscale OIDC의 Audience |

GHCR은 작업마다 발급되는 `GITHUB_TOKEN`을 사용한다. 이미지는 `ghcr.io/jandigoorm/jandi-band-py`에 저장하며, 배포 작업은 `packages: read` 권한을 사용한다. 서버로 전달한 임시 레지스트리 인증 파일은 작업 종료 시 삭제한다. 기존 패키지를 재사용할 때는 해당 저장소에 패키지 접근 권한을 부여해야 한다.

## Tailscale 연결

배포 작업만 GitHub OIDC로 Tailscale에 임시 장치를 등록한다. `TS_CLIENT_ID`와 `TS_AUDIENCE`는 비밀값이 아닌 식별자다. Tailscale OAuth Secret이나 재사용 Auth Key는 저장하지 않는다. PR 검증과 이미지 게시 작업에는 `id-token: write` 권한이 없다.

서버에는 `tag:github-oci`, 임시 실행기에는 `tag:jandi-ci`를 지정한다. 접근 정책은 `tag:jandi-ci`에서 `tag:github-oci`의 `tcp:22`만 허용한다. 기본 전체 허용 규칙과 함께 사용하면 이 제한이 적용되지 않으므로 전체 허용 규칙을 제거한다. 기존 OpenSSH와 환경별 `OCI_SSH_KEY`를 사용하며, Tailscale SSH는 켜지 않는다.

운영·개발 OIDC 신뢰 설정은 각각 만든다. Issuer는 `https://token.actions.githubusercontent.com`, Scope는 `auth_keys`, Tag는 `tag:jandi-ci`다. Subject와 Custom claims는 다음 값에 정확히 일치해야 한다.

| 항목 | production | development |
|---|---|---|
| Subject | `repo:JandiGoorm/jandi_band_py:environment:production` | `repo:JandiGoorm/jandi_band_py:environment:development` |
| ref | `refs/heads/main` | `refs/heads/dev` |
| workflow_ref | `JandiGoorm/jandi_band_py/.github/workflows/cicd.yml@refs/heads/main` | `JandiGoorm/jandi_band_py/.github/workflows/cicd.yml@refs/heads/dev` |
| repository_id | `991963880` | `991963880` |
| repository_owner_id | `191837133` | `191837133` |

`OCI_KNOWN_HOSTS`의 주소도 Tailscale 주소와 일치시킨다. 호스트 공개키는 기존 관리용 SSH 경로에서 확인한 것을 사용한다. OCI 공인 IP의 화이트리스트는 유지한다. 서버와 실행기는 DNS 설정 및 다른 장치의 서브넷 경로를 받지 않는다. 실행기는 서버 연결을 확인한 뒤 배포하며, 종료 시 Tailscale 임시 장치를 제거한다.

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
