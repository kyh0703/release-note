---
feature: open-issue-assignee-notify
status: plan_ready
created_at: 2026-03-30T13:37:51+09:00
---

# Open Issue Assignee Notify

## Goal

`run` 실행 중 version release 시점에 아직 닫히지 않은 Jira 이슈를 assignee 기준으로 묶어 메일로 알리는 기능을 추가한다.

## Context / Inputs

- Source docs:
  - `AGENTS.md`
  - `docs/STATE.md`
  - `docs/v1/completed/single-version-release-runner.md`
- Existing system facts:
  - `src/release_note/mail.py`에 assignee별 메일 생성과 SMTP 발송 초안이 이미 있다.
  - 현재 `runner.py`와 `cli.py`에는 open issue 메일 발송이 연결되어 있지 않다.
  - `RunnerConfig`에는 SMTP 설정 모델이 있지만 CLI 인자가 아직 없다.
  - version issue 조회는 이미 Jira search API로 수행하고 있다.
- User brief:
  - version release 시 닫히지 않은 이슈의 assignee에게 메일을 보낸다.
  - 수신 주소는 항상 `assigner@bridgetec.co.kr` 형태를 사용한다.
  - CLI 옵션이 있을 법한 구조이므로 기존 옵션/설정 흐름에 맞춰 붙인다.

## Plan Handoff

### Scope for Planning
- Jira issue 조회 결과에 assignee와 닫힘 여부 판단에 필요한 필드를 포함한다.
- `run` 명령에 open issue 메일 발송 opt-in과 SMTP 관련 CLI 옵션을 추가한다.
- apply에서는 실제 메일을 보내고 dry-run에서는 발송 대상과 이슈 목록만 미리 보여준다.
- 수신자는 Jira assignee username에 `@bridgetec.co.kr`를 붙여 계산한다.

### Success Criteria
- `python -m release_note run ... --notify-open-issues --dry-run`에서 발송 예정 recipient와 issue key를 확인할 수 있다.
- `python -m release_note run ... --notify-open-issues --apply`에서 닫히지 않은 이슈가 assignee별로 묶여 SMTP로 발송된다.
- 닫히지 않은 이슈가 없으면 메일 단계는 skip되고 전체 release 흐름은 계속 진행된다.
- assignee username이 `honggildong`이면 수신 주소는 `honggildong@bridgetec.co.kr`로 계산된다.

### Non-Goals
- 메일 템플릿의 고급 커스터마이징
- assignee 외 다른 수신자(CC/BCC) 추가
- Jira에서 이미 저장된 emailAddress를 우선 사용하도록 바꾸는 작업

### Open Questions
- 닫히지 않은 이슈 기준은 Jira `statusCategory != done`으로 두고, 필드가 비어 있으면 open으로 간주해도 되는지 구현 시 확인이 필요하다.

### Suggested Validation
- Jira client issue parsing 테스트
- mail notification grouping/unit 테스트
- CLI 옵션 전달 테스트
- runner dry-run/apply 시나리오 테스트
