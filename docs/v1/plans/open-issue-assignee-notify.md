# Open Issue Assignee Notify

## Goal
- version release 실행 중 닫히지 않은 Jira 이슈를 assignee별로 묶어 `@bridgetec.co.kr` 주소로 메일 발송하는 vertical slice를 구현하고 검증 가능한 상태로 만든다.

## References
- `AGENTS.md`
- `docs/STATE.md`
- `docs/v1/designs/2026-03-30-v1-open-issue-assignee-notify.md`
- `docs/v1/plans/single-version-release-runner.md`

## Workspace
- Branch: `feat/v1-open-issue-assignee-notify`
- Base: `master`
- Isolation: required
- Created by: planning handoff only

## Baseline
- Command: `python -m pytest`
- Expected: isolated worktree에서 기존 release runner 테스트가 clean baseline으로 통과한다.

## Tasks
### Task 1: Jira issue metadata와 메일 대상 계산
- Goal: version issue 목록에서 assignee와 닫힘 여부를 판별할 수 있도록 모델과 Jira adapter를 보강한다.
- Files: `src/release_note/models.py`, `src/release_note/jira_client.py`, `tests/jira/...`
- Verification: Jira client parsing test
- [x] Jira search fields에 assignee/status 정보를 포함한다.
- [x] assignee username 기반 recipient 계산 규칙을 mail preparation에 반영한다.
- [x] 닫히지 않은 issue만 분리할 수 있는 최소 판별 로직을 추가한다.

### Task 2: CLI/config와 runner 연결
- Goal: open issue notify를 `run` 명령 옵션으로 제어하고 dry-run/apply 모두에서 실행 흐름에 연결한다.
- Files: `src/release_note/cli.py`, `src/release_note/config.py`, `src/release_note/runner.py`, `tests/...`
- Verification: CLI/config/runner tests
- [x] `--notify-open-issues`와 SMTP 관련 CLI 옵션을 추가한다.
- [x] dry-run에서는 메일 발송 계획만 step payload로 남긴다.
- [x] apply에서는 SMTP 발송 결과를 step으로 기록하고 실패는 notification error로 surface한다.
- [x] open issue가 없으면 메일 단계를 skip 처리한다.

### Task 3: 메일 템플릿과 회귀 테스트
- Goal: assignee별 grouped notification 내용과 전체 release 회귀를 테스트로 고정한다.
- Files: `src/release_note/mail.py`, `tests/test_mail.py`, `tests/e2e/...`, `tests/test_cli.py`, `tests/test_config.py`
- Verification: unit/e2e tests
- [x] subject/body와 recipient 계산을 테스트로 고정한다.
- [x] runner end-to-end 테스트에 notify step을 추가한다.
- [x] 기존 dry-run/apply 흐름이 깨지지 않음을 회귀 테스트로 확인한다.

## Verification
- Required checks:
  - `python -m pytest`
- Optional checks:
  - `$env:PYTHONPATH='src'; python -m release_note run --tagging-version 6.2.0-b4h19 --dry-run --notify-open-issues`
- Last verification summary:
  - `python -m pytest`로 42개 테스트가 통과했다.
  - `$env:PYTHONPATH='src'; python -m release_note run --help`에서 notify/SMTP 옵션이 노출되는 것을 확인했다.
  - `$env:PYTHONPATH='src'; python -m release_note run --tagging-version 6.2.0-b4h19 --dry-run --notify-open-issues`에서 Jira 설정이 없을 때 mail notify 단계가 `requires_config`로 출력되는 것을 확인했다.
- Evidence:
  - `python -m pytest`
  - `$env:PYTHONPATH='src'; python -m release_note run --help`
  - `$env:PYTHONPATH='src'; python -m release_note run --tagging-version 6.2.0-b4h19 --dry-run --notify-open-issues`
- Open issues:
  - 실제 SMTP 서버 대상 `--apply` 실서버 검증은 아직 수행하지 않았다.
- Ready for finish: yes

## Notes
- 메일 수신 주소는 assignee username + `@bridgetec.co.kr` 규칙을 우선한다.
- 기본 동작 변경을 피하기 위해 메일 발송은 명시적인 CLI 옵션으로만 활성화한다.
