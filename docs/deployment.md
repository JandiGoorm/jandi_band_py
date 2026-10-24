# 배포

`main`만 운영 OCI AMD E2.1.Micro 한 곳에 배포한다. `dev`와 PR은 Docker 검증만 수행한다.
Python 3.15 기반 AMD64 이미지를 GHCR에 발행하고 digest로 배포한다.
컨테이너 메모리는 256MiB다. 공개 URL과 `/health`, `/timetable` API 규격은 유지한다.

저장소의 `compose.yaml`, `scripts/deploy.py`, `scripts/deploy.sh`로 배포한다.
런타임 `.env`는 서버 `/opt/jandi-band-py/production/.env`에서 수동 관리하며 선택 사항이다.
GHCR 인증에는 작업별 `GITHUB_TOKEN`을 사용한다.
GitHub production 환경의 `OCI_HOST`, `OCI_USER`, `OCI_KNOWN_HOSTS` 변수와 `OCI_SSH_KEY` 시크릿을 사용한다.
Tailscale OIDC는 `TS_CLIENT_ID`, `TS_AUDIENCE` 변수로 연결한다.

Docker 테스트 후 호스트에서 `/health`와 허용되지 않은 시간표 URL의 400 응답을 확인한다.
배포 실패 시 이전 release로 복구한다. DB와 이미지 저장소에는 직접 접속하지 않는다.
