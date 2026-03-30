---
feature: suffix-next-patch-version
status: plan_ready
created_at: 2026-03-30T16:20:00+09:00
---

# Suffix Next Patch Version

## Goal

When `tagging-version` uses the Jira build suffix form such as `v5.1.1-b3h75`, the
runner should prepare the next Jira version as `v5.1.1-b3h76` instead of
switching to `v5.1.2`.

## Context / Inputs
- Source docs:
  - `docs/STATE.md`
  - `docs/v1/designs/2026-03-30-v1-single-version-release-runner.md`
- Existing system facts:
  - Current release flow already releases the current Jira version and then
    creates or skips the next Jira version.
  - The current implementation always increments the semantic patch number for
    `next_patch_version`.
  - Actual Jira version names for this workflow use a leading `v` and a suffix
    such as `b3h75`.
- User brief:
  - Releasing `v5.1.1-b3h75` should create `v5.1.1-b3h76`.

## Plan Handoff
### Scope for Planning
- Update version parsing and next-version calculation so suffixes with a trailing
  number increment that number in place.
- Keep existing behavior for versions without a numeric suffix tail.
- Update Jira preview/create expectations and runner tests to use the new value.

### Success Criteria
- `TaggingVersion.parse("v5.1.1-b3h75").next_patch_name()` returns
  `v5.1.1-b3h76`.
- Dry-run and apply paths pass the suffix-based next version to Jira.
- Existing non-suffix numeric patch behavior continues to work.

### Non-Goals
- Changing release ordering logic
- Changing Confluence page update behavior
- Changing mail notification behavior

### Open Questions
- None for this slice. The suffix increment rule is fixed by the user brief.

### Suggested Validation
- `pytest` unit tests for `versioning.py`
- Jira client tests for preview/create expectations
- Runner tests for dry-run/apply next version payloads
