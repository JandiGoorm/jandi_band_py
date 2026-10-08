# 물리 FK 사용 현황 조사 (2026-08-08)

> 배경: 실무 경험 이후 "물리 FK를 사용하면 안 된다"는 통념을 접하고,
> 대학생 때 만든 이 프로젝트에 해당 이슈가 있는지 점검한 기록.
>
> 두 AI 에이전트(Claude / Codex)가 각각 조사한 결과를 교차 검증해 통합한 문서.

## 요약

| 리포지토리 | 물리 FK 이슈 | 비고 |
|:--|:--|:--|
| `jandi_band_py` (본 리포) | **해당 없음** | DB 계층이 현재는 물론 전체 히스토리에도 없음 |
| `jandi_band_backend` | **존재하나, 현 구조에선 유지가 합리적** | 아래 근거 및 검증 항목 참고 |

---

## 1. jandi_band_py — 해당 없음

전체가 파일 3개(`app.py`, `service/scraper.py`, `service/__init__.py`)인 stateless 서비스.
에브리타임 API 호출 → XML 파싱 → 메모리상 `dict`/`set` 가공 → JSON 응답 (`service/scraper.py:65`).
영속 계층이 없으므로 FK 문제가 성립하지 않는다.

### 확인 근거

- **현재 트리**: 소스 파일 3개(`app.py`, `service/scraper.py`, `service/__init__.py`)와
  설정 파일 전수 확인. `requirements.txt`에는
  `fastapi, uvicorn[standard], pydantic, httpx, lxml`만 선언 — ORM / DB 드라이버 없음
- **전체 히스토리**: 로컬·리모트 모든 브랜치(`master`, `lambda-api-version`, `playwright-version`)의
  **커밋 88개 전수 검색**. 아래 키워드 중 어느 것도 발견되지 않음
  - `FOREIGN KEY`, `REFERENCES`, `ForeignKey`, `relationship`
  - `CREATE TABLE` 등 DDL
  - SQLAlchemy, Django ORM, Alembic 등 ORM·마이그레이션 도구
  - PostgreSQL, MySQL, SQLite 드라이버 및 커넥션 설정
  - → 과거에 DB를 쓰다 걷어낸 흔적도 **없음**

> 주의: 단순 키워드 grep은 `orm`이 "f**orm**atting", "x-www-**form**-urlencoded"에 매칭되는 등
> 오탐이 발생한다. 위 결과는 오탐을 걸러낸 것.

README에 따르면 이 서비스는 `jandi_band_backend`의 서브 서버이므로, 실제 조사 대상은 그쪽이다.

---

## 2. jandi_band_backend — 현황

Spring Boot + JPA + MySQL, `@Entity` 26개.

| 항목 | 값 |
|:--|:--|
| `@ManyToOne` / `@JoinColumn` | 45개 / 45개 (1:1 대응 — FK 컬럼 보유 측 45개) |
| `@OneToOne` / `@ManyToMany` / `@JoinTable` | 0개 |
| `@ForeignKey(ConstraintMode.NO_CONSTRAINT)` | **0개** |
| `ddl-auto` | `validate` (`src/main/resources/application.properties.example:8`) |
| `cascade` 속성 사용 | 0개 |
| soft delete(`deletedAt`) 보유 엔티티 | 26개 중 **18개** |

리포지토리에 유일하게 남아있는 DDL(`docs/notice-notice.md:487`)이 실제 컨벤션을 보여준다:

```sql
FOREIGN KEY (creator_user_id) REFERENCES users(user_id)
```

### 중요: 코드만으로는 확정 불가

`ddl-auto=validate`라 Hibernate가 스키마를 생성하지 않으며, **실제 DDL은 리포지토리 밖에 손으로 작성**되어 있다.
또한 `validate`는 테이블·컬럼·타입만 검사하고 **FK 제약은 검사하지 않으므로**,
물리 FK가 있든 없든 애플리케이션은 동일하게 기동한다. → 실제 DB 확인이 필요하다.

```sql
SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE REFERENCED_TABLE_NAME IS NOT NULL AND TABLE_SCHEMA = '<스키마명>';
```

---

## 3. 판단 — 이 프로젝트에서는 "문제"가 아니다

물리 FK는 항상 피해야 하는 기능이 아니다. "물리 FK 금지"는 절대 규칙이 아니라
**대규모 트래픽 / MSA 맥락에서 나온 트레이드오프**다.

**물리 FK가 유리한 조건** — 단일 데이터베이스에서 강한 참조 무결성이 필요한 경우.

**논리 FK가 유리한 조건** — 다음과 같이 물리 FK의 비용이 실제로 발생하는 환경:

- 서비스 간 DB 분리 (FK가 서비스 경계를 넘는 경우), 샤딩
- 높은 쓰기 처리량 — 대량 delete/insert 시 InnoDB가 부모 행에 공유 락을 잡아 발생하는 락 경합
- `pt-osc` / `gh-ost` 등 온라인 스키마 변경
- 테스트 픽스처 구성 난이도

이 프로젝트는 **단일 서비스 모놀리식 + 단일 MySQL + 동아리 앱 수준 트래픽**으로 어디에도 해당하지 않는다.
게다가 `cascade`가 한 곳도 없고 26개 중 18개 엔티티가 soft delete이므로,
"FK cascade로 데이터가 연쇄 삭제됐다"는 대표적 사고 시나리오는 **발생 경로 자체가 없다**.

→ 지금 구조에서 물리 FK를 제거하면, 필요 없는 확장성을 위해 실재하는 정합성 보장을 버리는 거래가 된다.

### 다만 알고 있어야 할 것: soft delete + FK의 착시

FK는 "참조 대상 행이 **존재한다**"만 보장하며, "그 행이 **논리적으로 살아있다**"는 보장하지 않는다.
부모가 `deleted_at` 처리되어도 행은 남으므로 FK는 통과하고,
결국 조인할 때마다 애플리케이션이 `deleted_at IS NULL`을 직접 챙겨야 한다.

FK를 제거할 근거는 아니지만, **FK가 기대보다 적게 지켜준다**는 점은 인지하고 사용해야 한다.

---

## TODO

### 확인
- [ ] 운영 DB에서 실제 FK 제약 목록 조회 (위 `information_schema` 쿼리) — 45개 연관관계 중 몇 개가 물리 FK인지 확정
- [ ] 조회 결과를 본 문서에 반영

### 개선 (우선순위 순)
- [ ] **DDL을 리포지토리로 편입** — 현재 스키마가 코드 밖에만 존재해 재현·리뷰·이력 추적이 불가능.
      물리 FK 여부보다 이게 더 큰 실무 리스크. Flyway 또는 Liquibase 도입 검토
- [ ] `@ManyToOne`에 `fetch = LAZY` 누락 6곳 수정 (기본값 EAGER → N+1 위험).
      이 코드베이스에서 체감 성능에 미치는 영향은 FK보다 이쪽이 크다
  - `club/entity/Club.java:40`
  - `club/entity/ClubMember.java:25`, `:29`
  - `clubpending/entity/ClubPending.java:27`, `:31`, `:39`
- [ ] soft delete 대상 조인 쿼리에서 `deleted_at IS NULL` 필터 누락 여부 점검

### 하지 않기로 한 것
- [x] ~~물리 FK 일괄 제거~~ — 위 3번 근거에 따라 현 구조에서는 이득 없음

### 재검토 트리거

아래 중 하나라도 해당하게 되면 관계별로 물리 FK 유지 / 논리 FK 전환을 다시 판단한다.

- 서비스 분리 또는 DB 분리
- 샤딩 도입, 쓰기 처리량 급증
- 무중단 온라인 스키마 변경이 상시 필요해짐

전환하게 될 경우 반드시 함께 설계해야 할 항목:

- 애플리케이션 레벨 참조 무결성 검증 지점
- 트랜잭션 경계와 쓰기 순서 보장
- FK가 암묵적으로 만들어주던 **인덱스를 명시적으로 생성** (누락 시 조인 성능 급락)
- 삭제 정책 및 고아(orphan) 데이터 주기적 점검 방법
