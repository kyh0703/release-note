from __future__ import annotations

from collections.abc import Callable
from datetime import date

from .config import RunnerConfig
from .confluence_client import ConfluenceClient
from .errors import ApiError, ConfigError, NotFoundError
from .jira_client import JiraClient
from .models import (
    ConfluencePage,
    ExecutionMode,
    JiraIssue,
    ReleaseNoteBundle,
    RunStep,
    RunSummary,
)
from .versioning import TaggingVersion
from .wiki_content import detect_affected_package_codes, prepare_storage_content


class ReleaseRunner:
    def __init__(
        self,
        config: RunnerConfig,
        jira_client: JiraClient | None = None,
        confluence_client: ConfluenceClient | None = None,
        *,
        today: date | None = None,
        step_reporter: Callable[[RunStep], None] | None = None,
        run_start_reporter: Callable[[RunSummary], None] | None = None,
    ) -> None:
        self.config = config
        self.jira_client = (
            jira_client
            if jira_client is not None
            else (JiraClient(config.jira) if config.jira.is_configured else None)
        )
        self.confluence_client = (
            confluence_client
            if confluence_client is not None
            else (
                ConfluenceClient(config.confluence)
                if config.confluence.is_configured
                else None
            )
        )
        self.today = today or date.today()
        self.step_reporter = step_reporter
        self.run_start_reporter = run_start_reporter

    def run(self, tagging_version: str, execution_mode: ExecutionMode) -> RunSummary:
        if execution_mode.is_apply:
            self.config.validate_for_apply()

        version = TaggingVersion.parse(tagging_version)
        summary = RunSummary(
            tagging_version=version.raw,
            execution_mode=execution_mode,
            release_date=self.today.isoformat(),
            target_page_title=self.config.render_page_title(version),
            next_patch_version=version.next_patch_name(),
            fileserver_url=self.config.render_fileserver_url(version),
        )
        if self.run_start_reporter is not None:
            self.run_start_reporter(summary)

        jira_version = None
        release_note = None
        version_issues: list[JiraIssue] = []
        if self.jira_client is None:
            self._record_step(
                summary,
                "jira",
                "requires_config",
                "Jira access is disabled until CLI auth flags are provided.",
                {"missing": self.config.jira.missing_fields(), "version_name": version.raw},
            )
        else:
            jira_version = self.jira_client.find_version_by_name(version.raw)
            release_note = self.jira_client.fetch_release_notes(jira_version)
            version_issues = self.jira_client.list_version_issues(jira_version.name)
            self._record_step(
                summary,
                "jira.fetch_release_note",
                "preview",
                "Loaded Jira release note payload.",
                {
                    "version_id": jira_version.version_id,
                    "project_id": jira_version.project_id,
                    "issue_count": len(version_issues),
                },
            )
            if execution_mode.is_apply:
                released = self.jira_client.release_version(
                    jira_version, summary.release_date
                )
                self._record_step(
                    summary,
                    "jira.release_current",
                    "updated" if released else "skipped",
                    "Updated Jira version release state."
                    if released
                    else "Jira version was already released with the same date.",
                    {
                        "version_id": jira_version.version_id,
                        "release_date": summary.release_date,
                    },
                )
            else:
                self._record_step(
                    summary,
                    "jira.release_current",
                    "planned",
                    "Prepared Jira release update for dry-run.",
                    {
                        "version_id": jira_version.version_id,
                        "release_date": summary.release_date,
                        "already_released": jira_version.released,
                    },
                )

        self._run_confluence_phase(
            summary=summary,
            version=version,
            execution_mode=execution_mode,
            release_note=release_note,
            version_issues=version_issues,
        )

        if self.jira_client is None:
            self._record_step(
                summary,
                "jira.ensure_next_patch",
                "requires_config",
                "Jira access is required to prepare the next patch version.",
                {"next_patch_version": summary.next_patch_version},
            )
        elif jira_version is None:
            raise NotFoundError("Current Jira version could not be loaded.")
        elif execution_mode.is_apply:
            result = self.jira_client.ensure_version_exists(
                project_id=jira_version.project_id,
                version_name=summary.next_patch_version,
                before_version_name=jira_version.name,
            )
            self._record_step(
                summary,
                "jira.ensure_next_patch",
                "created" if result.created else "skipped",
                "Created the next patch version."
                if result.created
                else "Skipped next patch version because it already exists.",
                {
                    "version_name": result.version_name,
                    "version_id": result.version_id,
                    "move_action": result.move_action,
                    "move_reference": result.move_reference,
                },
            )
        else:
            preview = self.jira_client.preview_version_creation(
                version_name=summary.next_patch_version,
                before_version_name=jira_version.name,
            )
            self._record_step(
                summary,
                "jira.ensure_next_patch",
                "already_exists" if preview["already_exists"] else "planned",
                "Prepared next patch version preview for dry-run.",
                {
                    "version_name": summary.next_patch_version,
                    "already_exists": preview["already_exists"],
                    "move_action": preview["move_action"],
                    "move_reference": preview["move_reference"],
                },
            )

        return summary

    def _run_confluence_phase(
        self,
        *,
        summary: RunSummary,
        version: TaggingVersion,
        execution_mode: ExecutionMode,
        release_note: ReleaseNoteBundle | None,
        version_issues: list[JiraIssue],
    ) -> None:
        if self.confluence_client is None:
            self._record_step(
                summary,
                "confluence",
                "requires_config",
                "Confluence access is disabled until CLI auth flags are provided.",
                {
                    "missing": self.config.confluence.missing_fields(),
                    "target_page_title": summary.target_page_title,
                },
            )
            return

        if release_note is None:
            if execution_mode.is_apply:
                raise ConfigError("Confluence apply mode requires Jira release note data.")
            self._record_step(
                summary,
                "confluence.page",
                "requires_config",
                "Jira release note data is required to build the Confluence page.",
                {"target_page_title": summary.target_page_title},
            )
            return

        fileserver_url = summary.fileserver_url
        if fileserver_url is None:
            raise ConfigError("fileserver URL could not be rendered.")

        target_page = self.confluence_client.get_page(summary.target_page_title)
        move_target = self._find_previous_confluence_page(version)
        previous_source_page = self._load_confluence_page(move_target)
        action = "update"
        source_page = target_page

        if target_page is None:
            if previous_source_page is None:
                raise NotFoundError(
                    f"Previous Confluence version page was not found for '{summary.target_page_title}'."
                )
            source_page = previous_source_page
            action = "create"
        elif previous_source_page is not None:
            source_page = previous_source_page

        if source_page is None:
            raise NotFoundError("A Confluence source page could not be resolved.")

        page = self._build_page(
            source_page=source_page,
            target_page=target_page,
            target_title=summary.target_page_title,
            version=version,
            release_note=release_note,
            fileserver_url=fileserver_url,
            version_issues=version_issues,
        )
        affected_packages = sorted(detect_affected_package_codes(version_issues))
        payload = {
            "action": action,
            "target_page_title": summary.target_page_title,
            "source_page_title": source_page.title,
            "attachment_strategy": self.config.attachment_strategy,
            "fileserver_url": fileserver_url,
            "affected_packages": affected_packages,
        }
        if execution_mode.is_apply:
            stored = self.confluence_client.store_page(page)
            self._record_step(
                summary,
                "confluence.page",
                action,
                "Stored the Confluence page.",
                {**payload, "page_id": stored.page_id},
            )
            self._record_confluence_move_step(
                summary=summary,
                execution_mode=execution_mode,
                stored_page=stored,
                move_target=move_target,
            )
            return

        self._record_step(
            summary,
            "confluence.page",
            "planned",
            "Prepared Confluence page payload for dry-run.",
            payload,
        )
        self._record_confluence_move_step(
            summary=summary,
            execution_mode=execution_mode,
            stored_page=None,
            move_target=move_target,
        )

    def _build_page(
        self,
        *,
        source_page: ConfluencePage,
        target_page: ConfluencePage | None,
        target_title: str,
        version: TaggingVersion,
        release_note: ReleaseNoteBundle,
        fileserver_url: str,
        version_issues: list[JiraIssue],
    ) -> ConfluencePage:
        content = prepare_storage_content(
            base_content=source_page.content,
            tagging_version=version,
            release_note_html=release_note.html,
            fileserver_url=fileserver_url,
            attachment_strategy=self.config.attachment_strategy,
            version_issues=version_issues,
        )
        if target_page is not None:
            return target_page.clone_for_update(content=content)
        return source_page.clone_for_create(title=target_title, content=content)

    def _find_previous_confluence_page(
        self, version: TaggingVersion
    ) -> ConfluencePage | None:
        if self.confluence_client is None:
            return None
        current_title = self.config.render_page_title(version)
        candidates: list[tuple[tuple[object, ...], ConfluencePage]] = []
        for page in self.confluence_client.list_pages():
            if page.title == current_title:
                continue
            page_version = self.config.parse_page_title_version(page.title)
            if page_version is None:
                continue
            if page_version.ordering_key() >= version.ordering_key():
                continue
            candidates.append((page_version.ordering_key(), page))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[0])[1]

    def _load_confluence_page(
        self, page: ConfluencePage | None
    ) -> ConfluencePage | None:
        if self.confluence_client is None or page is None:
            return None
        return self.confluence_client.get_page(page.title)

    def _record_confluence_move_step(
        self,
        *,
        summary: RunSummary,
        execution_mode: ExecutionMode,
        stored_page: ConfluencePage | None,
        move_target: ConfluencePage | None,
    ) -> None:
        if move_target is None:
            self._record_step(
                summary,
                "confluence.order_page",
                "skipped",
                "Skipped page ordering because no previous version page was found.",
                {"position": "below"},
            )
            return

        payload = {
            "position": "below",
            "target_page_id": move_target.page_id,
            "target_page_title": move_target.title,
        }
        if not execution_mode.is_apply:
            self._record_step(
                summary,
                "confluence.order_page",
                "planned",
                "Prepared Confluence page ordering for dry-run.",
                payload,
            )
            return

        if stored_page is None or stored_page.page_id is None:
            raise ConfigError("Stored Confluence page id is required for page ordering.")
        if move_target.page_id is None:
            raise ConfigError("Move target Confluence page id is required for page ordering.")
        try:
            self.confluence_client.move_page(
                stored_page.page_id, move_target.page_id, "below"
            )
        except ApiError as exc:
            if "MovePageCommand" not in str(exc):
                raise
            self._record_step(
                summary,
                "confluence.order_page",
                "skipped",
                "Skipped page ordering because the current Confluence JSON-RPC server cannot execute movePage.",
                {**payload, "reason": str(exc), "source_page_id": stored_page.page_id},
            )
            return
        self._record_step(
            summary,
            "confluence.order_page",
            "updated",
            "Moved the Confluence page below the previous version page.",
            {**payload, "source_page_id": stored_page.page_id},
        )

    def _record_step(
        self,
        summary: RunSummary,
        name: str,
        status: str,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        summary.add_step(name, status, message, payload)
        if self.step_reporter is not None:
            self.step_reporter(summary.steps[-1])
