---
feature: single-version-release-runner
status: plan_ready
created_at: 2026-03-30T10:14:54+09:00
---

# Single-Version Release Runner

## Goal

`tagging-version` 하나를 입력받아 Jira release note 추출, Jira version release 처리, PAC 위키 페이지 재생성/갱신, 다음 patch version 생성까지 API-only로 실행하는 Linux CLI의 첫 vertical slice를 정의한다.

## Context / Inputs

- Source docs:
  - `AGENTS.md`
  - `docs/STATE.md`
  - `docs/v1/research/2026-03-30-v1-single-version-release-runner-api-research.md`
- Existing system facts:
  - Jira 프로젝트 키는 `IPR`이다.
  - Confluence 공간 키는 `PAC`이다.
  - Jira는 REST API와 `ReleaseNote.jspa`가 사용 가능하다.
  - Confluence는 `4.2.4`이며 JSON-RPC가 사용 가능하다.
  - Jira에서는 다음 patch version이 이미 존재할 수 있으므로 create-only가 아니라 create-or-skip이 필요하다.
  - PAC의 실제 release page는 `IPRON v6.2.0-b4h19` 같은 title 규칙을 사용한다.
- External constraints:
  - Linux 환경에서 동작해야 한다.
  - Playwright 같은 브라우저 자동화는 사용하지 않는다.
  - 사용자 설명 기준으로 Jira releaseDate는 실행일을 사용한다.
  - fileserver 주소는 `tagging-version`에서 결정되는 규칙식으로 계산해야 한다.

## Problem Statement

현재 릴리즈 후처리는 Jira와 Confluence를 오가며 수동으로 수행된다. 이 과정에는 release note 복사, version release, 위키 페이지 삭제/복사/수정, 다음 patch version 생성이 섞여 있어 반복 작업이 많고 누락이나 중복 생성 같은 실수가 생기기 쉽다. 이번 v1은 이 흐름을 단일 CLI 명령으로 재현하되, Linux에서 안전하게 실행되고 dry-run으로 사전 검토가 가능한 API-only 자동화를 목표로 한다.

## Decision Drivers

- Linux 환경에서 실행 가능한 순수 HTTP/RPC 기반 구현이어야 한다.
- Jira와 Confluence의 현재 서버 버전에 맞는 방식이어야 한다.
- 재실행 시 중복 생성이나 중복 release를 피하는 idempotent 동작이 필요하다.
- 수동 복사와 최대한 같은 결과를 만들되 HTML UI 구조 의존성은 최소화해야 한다.
- 적용 전 결과를 검토할 수 있도록 dry-run이 필요하다.

## Options Considered

### Option A
- Summary:
  - Jira는 REST API + `ReleaseNote.jspa`, Confluence는 JSON-RPC로 처리한다.
- Pros:
  - Linux 친화적이다.
  - UI 셀렉터나 브라우저 상태에 의존하지 않는다.
  - dry-run, 재시도, idempotency 제어가 단순하다.
- Cons:
  - Confluence page copy를 UI와 동일하게 재현하려면 storage content와 attachment 참조를 이해해야 한다.
- Risks:
  - attachment/reference 보존 전략이 틀리면 새 페이지 일부 링크가 깨질 수 있다.

### Option B
- Summary:
  - Jira는 API를 쓰고, Confluence는 legacy HTML form POST를 사용한다.
- Pros:
  - Confluence UI copy/edit/remove 흐름과 가깝다.
- Cons:
  - HTML form 필드와 토큰 구조에 더 강하게 의존한다.
  - Linux 환경에서 장기 유지보수성이 떨어진다.
- Risks:
  - 페이지 편집 UI 변경 시 쉽게 깨질 수 있다.

### Option C
- Summary:
  - 브라우저 자동화로 사람이 하던 절차를 그대로 재현한다.
- Pros:
  - 초기 구현 시 흐름 이해가 단순하다.
- Cons:
  - 사용자 제약과 충돌한다.
  - 느리고 불안정하며 운영 자동화에 부적합하다.
- Risks:
  - 헤드리스 환경 구성과 셀렉터 유지 비용이 크다.

## Recommended Option

- Choice:
  - Option A
- Why now:
  - 실서버에서 Jira REST와 Confluence JSON-RPC가 모두 검증됐고, Linux + API-only라는 고정 제약과 가장 잘 맞는다.
- Rejected alternatives:
  - Option B는 fallback으로는 가능하지만 HTML 구조 의존성이 커서 v1 기본안으로 적합하지 않다.
  - Option C는 사용자 제약과 직접 충돌하므로 제외한다.

## Scope Decision

- In:
  - `tagging-version` 단일 입력
  - Jira version 조회와 release note 추출
  - Jira version release 처리와 `releaseDate=실행일`
  - Confluence page 검색, 존재 시 삭제, 직전 버전 기반 신규 page 생성/갱신
  - release note와 fileserver 링크 반영
  - 다음 patch version create-or-skip
  - `dry-run` / `apply` 실행 모드
- Out:
  - fileserver 업로드 자체
  - 다중 Jira 프로젝트 지원
  - 다중 Confluence 공간 지원
  - 브라우저 자동화 fallback
- Deferred:
  - 스케줄러/알림
  - UI 대시보드
  - 운영용 다중 릴리즈 배치 처리

## Open Questions

- fileserver URL의 정확한 규칙식을 어떤 예시로 고정할지 아직 문서화되지 않았다.
- Confluence 신규 page 생성 시 attachment를 새 page로 복사해야 하는지, 기존 page reference를 유지해야 하는지 구현 전 검증이 필요하다.
- 직전 위키 page를 title 규칙만으로 찾을지, page tree와 Jira version 규칙을 함께 쓸지 최종 판단이 필요하다.

## Plan Handoff

### Source of Truth Docs
- `AGENTS.md`
- `docs/STATE.md`
- `docs/v1/research/2026-03-30-v1-single-version-release-runner-api-research.md`
- `docs/v1/designs/2026-03-30-v1-single-version-release-runner.md`

### Scope for Planning
- Python CLI 한 개가 `tagging-version` 입력으로 Jira와 Confluence를 API-only 방식으로 연결해 전체 후처리 순서를 실행한다.
- 첫 plan은 하나의 version에 대해 dry-run과 apply를 모두 지원하는 단일 vertical slice를 목표로 한다.

### Fixed Constraints
- Linux 환경에서 동작해야 한다.
- 브라우저 자동화는 사용하지 않는다.
- Jira는 REST API와 `ReleaseNote.jspa`를 사용한다.
- Confluence는 JSON-RPC를 사용한다.
- Jira releaseDate는 실행일을 사용한다.
- 다음 patch version은 이미 존재할 수 있으므로 create-or-skip이어야 한다.

### Success Criteria
- 지정한 `tagging-version`에 대해 Jira release note를 추출할 수 있다.
- 지정한 version을 Jira에서 release 처리할 수 있다.
- PAC 위키 page를 찾아 삭제/생성/수정할 수 있다.
- release note와 fileserver 링크를 새 위키 page에 반영할 수 있다.
- 다음 patch version을 안전하게 생성하거나 이미 존재하면 skip할 수 있다.
- dry-run에서 실제 변경 예정 내용을 출력할 수 있다.

### Non-Goals
- fileserver 업로드
- GUI 제공
- 브라우저 기반 자동화
- 다중 프로젝트 일반화

### Open Questions
- fileserver URL 규칙식
- attachment/reference 보존 전략
- 직전 위키 page 탐색 규칙

### Suggested Validation
- version parser와 next patch calculator 단위 테스트
- fileserver URL formatter 단위 테스트
- Jira adapter mock/integration 테스트
- Confluence JSON-RPC adapter mock/integration 테스트
- 실제 버전을 대상으로 한 read-only dry-run 검증
- 승인된 테스트 version을 대상으로 한 apply 검증
