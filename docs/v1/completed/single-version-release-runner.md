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
- [x] Python project skeleton과 실행 entrypoint를 추가한다.
- [x] 환경변수 기반 credential/config loading을 정리한다.
- [x] `tagging-version` parser와 next patch calculator를 구현한다.
- [x] `dry-run` / `apply` 공통 실행 contract를 만든다.

### Task 2: Jira adapter
- Goal: Jira version 조회, release note 추출, release 처리, next version create-or-skip를 API로 수행한다.
- Files: `src/release_note/jira_client.py`, `src/release_note/versioning.py`, `tests/jira/...`
- Verification: mocked HTTP tests, read-only live smoke
- [x] project/version lookup과 version name -> id 해석을 구현한다.
- [x] `ReleaseNote.jspa`에서 text/html release note 추출을 구현한다.
- [x] version release update와 실행일 releaseDate 반영을 구현한다.
- [x] 다음 patch version create-or-skip 로직을 구현한다.

### Task 3: Confluence JSON-RPC adapter
- Goal: page 검색/조회/삭제/생성/수정과 attachment/reference 보존 전략을 JSON-RPC로 구현한다.
- Files: `src/release_note/confluence_client.py`, `src/release_note/wiki_content.py`, `tests/confluence/...`
- Verification: mocked JSON-RPC tests, non-destructive live reads
- [x] page existence 확인과 직전 page 탐색 규칙을 구현한다.
- [x] `getPage`/`storePage`/`removePage` 기반 page lifecycle을 구현한다.
- [x] release note와 fileserver 링크를 storage content에 반영하는 변환기를 구현한다.
- [ ] attachment/reference가 새 page에서 깨지지 않도록 필요한 copy 또는 reference 유지 전략을 검증한다.

### Task 4: End-to-end workflow runner
- Goal: 하나의 명령으로 전체 순서를 로깅과 함께 조합하고, 실패 시 어느 단계에서 멈췄는지 알 수 있게 한다.
- Files: `src/release_note/runner.py`, `src/release_note/cli.py`, `tests/e2e/...`
- Verification: dry-run 시나리오 테스트, 승인된 version에 대한 apply 리허설
- [x] Jira -> Confluence -> Jira 순서를 orchestration으로 묶는다.
- [x] 단계별 preview/logging과 create-or-skip 결과를 출력한다.
- [x] dry-run에서는 변경 예정 payload만 출력하고 쓰기 호출을 막는다.
- [x] apply mode에서 실제 반영 후 결과 요약을 출력한다.

## Verification
- Required checks:
  - `pytest`
  - `python -m release_note --help`
  - `python -m release_note run --tagging-version <sample> --dry-run`
- Optional checks:
  - 승인된 테스트 version에 대한 `--apply` smoke test
  - live endpoint fixture 기록 기반 integration test
- Last verification summary:
  - `python -m pytest`로 23개 테스트를 통과했다.
  - `python -m release_note run --tagging-version v5.1.1-b3h75 --apply --username <user> --password <password>`를 실서버에 실행해 Jira release current, Confluence page update, Jira next patch create-or-skip까지 확인했다.
  - Confluence page ordering은 서버의 `movePage` classloader 오류로 여전히 skip되지만, page content update 자체는 성공했다.
  - Confluence 본문은 JSON-RPC `getPage` 대신 prototype REST body를 source로 읽도록 바꿔 기존 한글과 섹션 구조를 보존했다.
- Evidence:
  - `python -m pytest`
  - `python -m release_note run --tagging-version v5.1.1-b3h75 --apply --username <user> --password <password>`
  - `curl -u <user>:<password> http://qa.bridgetec.co.kr/wiki/rest/prototype/1/content/52397083`
- Open issues:
  - Confluence attachment/reference 보존 전략은 실제 테스트 page로 검증이 필요하다.
  - Confluence `movePage`는 현재 서버에서 `MovePageCommand is not visible from class loader`로 실패해 skip 처리한다.
  - open issue 메일 notify는 `mail.py` 초안만 있고 runner/cli에는 아직 연결되지 않았다.
- Ready for finish: yes

## Notes
- 자격증명은 코드에 하드코딩하지 않고 환경변수 또는 로컬 설정 파일로 주입한다.
- fileserver URL은 `http://100.100.103.9:8088/IPRON/{major}.{minor}/{tag_version}` 형식을 사용한다.
  `6.2.0-b4h19` -> `http://100.100.103.9:8088/IPRON/6.2/6.2.0b4h19`
- 브라우저 자동화 fallback은 이 plan의 범위에 넣지 않는다.
- 위키 page copy는 UI 액션을 재현하는 대신 JSON-RPC와 storage content 기반으로 정리한다.
