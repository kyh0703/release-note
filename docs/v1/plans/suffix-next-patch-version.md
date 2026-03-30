# Suffix Next Patch Version

## Goal
- Make the release runner create the next Jira version by incrementing the build
  suffix number when the tagging version uses the IPRON suffix form.

## References
- `docs/STATE.md`
- `docs/v1/designs/2026-03-30-v1-single-version-release-runner.md`
- `docs/v1/designs/2026-03-30-v1-suffix-next-patch-version.md`

## Workspace
- Branch: `feat/v1-suffix-next-patch-version`
- Base: `master`
- Isolation: required
- Created by: `exec-plan` via `git-worktree`

## Baseline
- Command: `python -m pytest`
- Expected: tests pass before and after the targeted change

## Tasks
### Task 1: Add suffix-aware next-version calculation
- Goal: increment `b3h75` style suffixes to the next numeric suffix.
- Files: `src/release_note/versioning.py`, `tests/test_versioning.py`
- Verification: versioning tests cover both suffix and non-suffix cases
- [ ] Update `next_patch_name()` for suffix-with-trailing-number versions
- [ ] Preserve current fallback behavior for versions without that pattern

### Task 2: Align Jira and runner expectations
- Goal: ensure dry-run/apply paths pass the suffix-based next version through to Jira.
- Files: `tests/jira/test_jira_client.py`, `tests/e2e/test_runner.py`
- Verification: Jira client and runner tests assert the new next version value
- [ ] Update preview/create expectations
- [ ] Update runner step payload expectations

## Verification
- Required checks:
  - `python -m pytest`
- Optional checks:
  - read-only dry-run against the internal Jira server
- Last verification summary:
  - none yet
- Evidence:
  - none yet
- Open issues:
  - none
- Ready for finish: no

## Notes
- Keep the change scoped to next-version naming only. Do not expand into other
  workflow behavior in this slice.
