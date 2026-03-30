from datetime import date

from release_note.config import ConfluenceConfig, JiraConfig, RunnerConfig
from release_note.errors import ApiError
from release_note.models import (
    ConfluencePage,
    CreateOrSkipResult,
    ExecutionMode,
    JiraIssue,
    JiraVersion,
    ReleaseNoteBundle,
)
from release_note.runner import ReleaseRunner


class FakeJiraClient:
    def __init__(self, *, next_exists: bool = False) -> None:
        self.next_exists = next_exists
        self.calls: list[str] = []

    def find_version_by_name(self, version_name: str) -> JiraVersion:
        self.calls.append(f"find:{version_name}")
        return JiraVersion(
            version_id="10",
            name=version_name,
            project_id="10001",
            released=False,
            release_date=None,
        )

    def fetch_release_notes(self, version: JiraVersion) -> ReleaseNoteBundle:
        self.calls.append(f"fetch:{version.version_id}")
        return ReleaseNoteBundle(text="text note", html="<p>html note</p>")

    def list_version_issues(self, version_name: str) -> list[JiraIssue]:
        self.calls.append(f"issues:{version_name}")
        return [
            JiraIssue(key="IPR-1", summary="IE package fix"),
            JiraIssue(key="IPR-2", summary="IR package fix"),
        ]

    def release_version(self, version: JiraVersion, release_date: str) -> bool:
        self.calls.append(f"release:{version.version_id}:{release_date}")
        return True

    def has_version(self, version_name: str) -> bool:
        self.calls.append(f"has:{version_name}")
        return self.next_exists

    def preview_version_creation(
        self, *, version_name: str, before_version_name: str | None = None
    ) -> dict[str, object]:
        self.calls.append(f"preview:{version_name}:{before_version_name}")
        return {
            "already_exists": self.next_exists,
            "version_name": version_name,
            "move_action": "after" if not self.next_exists else None,
            "move_reference": "6.3.0-b1h1" if not self.next_exists else None,
        }

    def ensure_version_exists(
        self,
        *,
        project_id: str,
        version_name: str,
        before_version_name: str | None = None,
    ) -> CreateOrSkipResult:
        self.calls.append(f"ensure:{project_id}:{version_name}:{before_version_name}")
        return CreateOrSkipResult(
            created=not self.next_exists,
            version_name=version_name,
            version_id="11" if not self.next_exists else "12",
            move_action="after" if not self.next_exists else None,
            move_reference="6.3.0-b1h1" if not self.next_exists else None,
        )


class FakeConfluenceClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.pages = {
            "IPRON v6.2.0-b4h18": ConfluencePage(
                page_id="1999",
                title="IPRON v6.2.0-b4h18",
                space_key="PAC",
                content=(
                    "<h2>Version Up Packages</h2>"
                    "<table>"
                    "<tr><th>Package</th><th>Old Version</th><th>New Version</th></tr>"
                    "<tr><td>ipron-ie</td><td>v6.2.0-b4h17</td><td>v6.2.0-b4h18</td></tr>"
                    "<tr><td>ipron-ir</td><td>v6.2.0-b4h14</td><td></td></tr>"
                    "</table>"
                    '<h1>Release Notes</h1><ac:macro ac:name="panel"><ac:rich-text-body>'
                    "<p>old note</p>"
                    "</ac:rich-text-body></ac:macro>"
                    '<h1>Server Packages</h1><p><a href="http://old.example.com/path">'
                    "IPRONv6.2.0-b4h18&nbsp; package link"
                    "</a></p>"
                ),
                version=1,
                parent_id="100",
            )
        }

    def get_page(self, title: str) -> ConfluencePage | None:
        self.calls.append(f"get:{title}")
        return self.pages.get(title)

    def list_pages(self) -> list[ConfluencePage]:
        self.calls.append("list")
        return list(self.pages.values())

    def store_page(self, page: ConfluencePage) -> ConfluencePage:
        self.calls.append(f"store:{page.title}")
        stored = ConfluencePage(
            page_id=page.page_id or "3000",
            title=page.title,
            space_key=page.space_key,
            content=page.content,
            version=page.version,
            parent_id=page.parent_id,
        )
        self.pages[page.title] = stored
        return stored

    def move_page(self, source_page_id: str, target_page_id: str, position: str) -> None:
        self.calls.append(f"move:{source_page_id}:{target_page_id}:{position}")


def _config() -> RunnerConfig:
    return RunnerConfig(
        jira=JiraConfig(
            base_url="http://jira.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        confluence=ConfluenceConfig(
            base_url="http://wiki.example.com",
            username="wiki-user",
            password="wiki-pass",
        ),
        fileserver_url_template="http://100.100.103.9:8088/IPRON/{major}.{minor}/{tag_version}",
        wiki_page_title_template="IPRON v{raw}",
        attachment_strategy="reuse",
    )


def test_dry_run_keeps_write_calls_disabled() -> None:
    jira = FakeJiraClient()
    confluence = FakeConfluenceClient()
    runner = ReleaseRunner(
        _config(),
        jira_client=jira,
        confluence_client=confluence,
        today=date(2026, 3, 30),
    )

    summary = runner.run("6.2.0-b4h19", ExecutionMode.DRY_RUN)

    assert "release:10:2026-03-30" not in jira.calls
    assert "ensure:10001:6.2.1:6.2.0-b4h19" not in jira.calls
    assert all(not call.startswith("store:") for call in confluence.calls)
    assert "issues:6.2.0-b4h19" in jira.calls
    assert summary.next_patch_version == "6.2.1"
    assert summary.fileserver_url == "http://100.100.103.9:8088/IPRON/6.2/6.2.0b4h19"
    assert summary.steps[2].payload["action"] == "create"
    assert summary.steps[2].payload["source_page_title"] == "IPRON v6.2.0-b4h18"
    assert (
        summary.steps[2].payload["fileserver_url"]
        == "http://100.100.103.9:8088/IPRON/6.2/6.2.0b4h19"
    )
    assert summary.steps[3].payload["position"] == "below"
    assert summary.steps[3].payload["target_page_title"] == "IPRON v6.2.0-b4h18"
    assert summary.steps[4].payload["move_action"] == "after"
    assert summary.steps[4].payload["move_reference"] == "6.3.0-b1h1"
    assert [step.name for step in summary.steps] == [
        "jira.fetch_release_note",
        "jira.release_current",
        "confluence.page",
        "confluence.order_page",
        "jira.ensure_next_patch",
    ]


def test_apply_runs_jira_confluence_jira_sequence() -> None:
    jira = FakeJiraClient()
    confluence = FakeConfluenceClient()
    runner = ReleaseRunner(
        _config(),
        jira_client=jira,
        confluence_client=confluence,
        today=date(2026, 3, 30),
    )

    summary = runner.run("6.2.0-b4h19", ExecutionMode.APPLY)

    assert jira.calls == [
        "find:6.2.0-b4h19",
        "fetch:10",
        "issues:6.2.0-b4h19",
        "release:10:2026-03-30",
        "ensure:10001:6.2.1:6.2.0-b4h19",
    ]
    assert confluence.calls == [
        "get:IPRON v6.2.0-b4h19",
        "list",
        "get:IPRON v6.2.0-b4h18",
        "store:IPRON v6.2.0-b4h19",
        "move:3000:1999:below",
    ]
    assert summary.steps[-2].status == "updated"
    assert summary.steps[-2].payload["target_page_title"] == "IPRON v6.2.0-b4h18"
    assert summary.steps[-1].status == "created"
    assert summary.steps[-1].payload["move_action"] == "after"
    assert summary.steps[-1].payload["move_reference"] == "6.3.0-b1h1"
    assert (
        "http://100.100.103.9:8088/IPRON/6.2/6.2.0b4h19"
        in confluence.pages["IPRON v6.2.0-b4h19"].content
    )
    assert (
        "<ac:rich-text-body><p>html note</p></ac:rich-text-body>"
        in confluence.pages["IPRON v6.2.0-b4h19"].content
    )
    assert (
        "IPRONv6.2.0-b4h19&nbsp; package link"
        in confluence.pages["IPRON v6.2.0-b4h19"].content
    )
    assert (
        "<td>ipron-ie</td><td>v6.2.0-b4h18</td><td>6.2.0-b4h19</td>"
        in confluence.pages["IPRON v6.2.0-b4h19"].content
    )
    assert (
        "<td>ipron-ir</td><td>v6.2.0-b4h14</td><td>6.2.0-b4h19</td>"
        in confluence.pages["IPRON v6.2.0-b4h19"].content
    )


def test_runner_reports_progress_in_execution_order() -> None:
    jira = FakeJiraClient()
    confluence = FakeConfluenceClient()
    events: list[str] = []

    def on_start(summary) -> None:
        events.append(f"start:{summary.tagging_version}")

    def on_step(step) -> None:
        events.append(f"step:{step.name}:{step.status}")

    runner = ReleaseRunner(
        _config(),
        jira_client=jira,
        confluence_client=confluence,
        today=date(2026, 3, 30),
        step_reporter=on_step,
        run_start_reporter=on_start,
    )

    runner.run("6.2.0-b4h19", ExecutionMode.DRY_RUN)

    assert events == [
        "start:6.2.0-b4h19",
        "step:jira.fetch_release_note:preview",
        "step:jira.release_current:planned",
        "step:confluence.page:planned",
        "step:confluence.order_page:planned",
        "step:jira.ensure_next_patch:planned",
    ]


def test_apply_skips_confluence_order_when_move_page_is_unsupported() -> None:
    jira = FakeJiraClient()
    confluence = FakeConfluenceClient()

    def failing_move_page(source_page_id: str, target_page_id: str, position: str) -> None:
        raise ApiError(
            "Confluence RPC 'movePage' failed: The application was unable to serve your "
            "request: java.lang.IllegalArgumentException: interface "
            "com.atlassian.confluence.content.service.page.MovePageCommand is not visible "
            "from class loader"
        )

    confluence.move_page = failing_move_page
    runner = ReleaseRunner(
        _config(),
        jira_client=jira,
        confluence_client=confluence,
        today=date(2026, 3, 30),
    )

    summary = runner.run("6.2.0-b4h19", ExecutionMode.APPLY)

    assert summary.steps[-2].status == "skipped"
    assert summary.steps[-2].name == "confluence.order_page"
    assert "MovePageCommand" in summary.steps[-2].payload["reason"]
    assert summary.steps[-1].name == "jira.ensure_next_patch"
