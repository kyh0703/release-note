# Single-Version Release Runner

## Goal
- `tagging-version` 하나로 Jira release note 추출, Jira release 처리, Confluence page 재생성/갱신, 다음 patch version create-or-skip까지 수행하는 Python CLI vertical slice를 구현하고 검증 가능한 상태로 만든다.

## References
- `AGENTS.md`
- `docs/STATE.md`
- `docs/v1/research/2026-03-30-v1-single-version-release-runner-api-research.md`
- `docs/v1/designs/2026-03-30-v1-single-version-release-runner.md`

## Workspace
- Branch: `feat/v1-single-version-release-runner`
- Base: `master`
- Isolation: required
- Created by: planning handoff only

## Baseline
- Command: none yet; repository is currently docs-only and has no executable source tree.
- Expected: isolated worktree에서 Python CLI 초기 구성을 추가해도 기존 baseline과 충돌하지 않는다.

## Tasks
### Task 1: Python CLI skeleton과 공통 모델
- Goal: Linux 환경에서 실행 가능한 Python package/CLI, 설정 로딩, dry-run/apply 모드, version parser를 만든다.
- Files: `pyproject.toml`, `src/release_note/...`, `tests/...`, `.gitignore`
- Verification: version parser 테스트, CLI argument smoke test
- [ ] Python project skeleton과 실행 entrypoint를 추가한다.
- [ ] 환경변수 기반 credential/config loading을 정리한다.
- [ ] `tagging-version` parser와 next patch calculator를 구현한다.
- [ ] `dry-run` / `apply` 공통 실행 contract를 만든다.

### Task 2: Jira adapter
- Goal: Jira version 조회, release note 추출, release 처리, next version create-or-skip를 API로 수행한다.
- Files: `src/release_note/jira_client.py`, `src/release_note/versioning.py`, `tests/jira/...`
- Verification: mocked HTTP tests, read-only live smoke
- [ ] project/version lookup과 version name -> id 해석을 구현한다.
- [ ] `ReleaseNote.jspa`에서 text/html release note 추출을 구현한다.
- [ ] version release update와 실행일 releaseDate 반영을 구현한다.
- [ ] 다음 patch version create-or-skip 로직을 구현한다.

### Task 3: Confluence JSON-RPC adapter
- Goal: page 검색/조회/삭제/생성/수정과 attachment/reference 보존 전략을 JSON-RPC로 구현한다.
- Files: `src/release_note/confluence_client.py`, `src/release_note/wiki_content.py`, `tests/confluence/...`
- Verification: mocked JSON-RPC tests, non-destructive live reads
- [ ] page existence 확인과 직전 page 탐색 규칙을 구현한다.
- [ ] `getPage`/`storePage`/`removePage` 기반 page lifecycle을 구현한다.
- [ ] release note와 fileserver 링크를 storage content에 반영하는 변환기를 구현한다.
- [ ] attachment/reference가 새 page에서 깨지지 않도록 필요한 copy 또는 reference 유지 전략을 검증한다.

### Task 4: End-to-end workflow runner
- Goal: 하나의 명령으로 전체 순서를 로깅과 함께 조합하고, 실패 시 어느 단계에서 멈췄는지 알 수 있게 한다.
- Files: `src/release_note/runner.py`, `src/release_note/cli.py`, `tests/e2e/...`
- Verification: dry-run 시나리오 테스트, 승인된 version에 대한 apply 리허설
- [ ] Jira -> Confluence -> Jira 순서를 orchestration으로 묶는다.
- [ ] 단계별 preview/logging과 create-or-skip 결과를 출력한다.
- [ ] dry-run에서는 변경 예정 payload만 출력하고 쓰기 호출을 막는다.
- [ ] apply mode에서 실제 반영 후 결과 요약을 출력한다.

## Verification
- Required checks:
  - `pytest`
  - `python -m release_note --help`
  - `python -m release_note run --tagging-version <sample> --dry-run`
- Optional checks:
  - 승인된 테스트 version에 대한 `--apply` smoke test
  - live endpoint fixture 기록 기반 integration test
- Last verification summary:
  - none yet
- Evidence:
  - none yet
- Open issues:
  - fileserver URL의 정확한 규칙식이 아직 문서화되지 않았다.
  - Confluence attachment/reference 보존 전략은 실제 테스트 page로 검증이 필요하다.
- Ready for finish: no

## Notes
- 자격증명은 코드에 하드코딩하지 않고 환경변수 또는 로컬 설정 파일로 주입한다.
- 브라우저 자동화 fallback은 이 plan의 범위에 넣지 않는다.
- 위키 page copy는 UI 액션을 재현하는 대신 JSON-RPC와 storage content 기반으로 정리한다.
