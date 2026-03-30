import release_note.cli as cli_module
from release_note.models import ExecutionMode, RunSummary


def test_cli_dry_run_without_flags_reports_missing_config(capsys) -> None:
    exit_code = cli_module.main(["run", "--tagging-version", "6.2.0-b4h19", "--dry-run"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "run started" in captured.out
    assert "step [requires_config] jira:" in captured.out
    assert "tagging_version: 6.2.0-b4h19" in captured.out
    assert "fileserver_url: http://100.100.103.9:8088/IPRON/6.2/6.2.0b4h19" in captured.out
    assert "summary:" in captured.out
    assert "requires_config" in captured.out


def test_cli_common_auth_flags_build_shared_config(monkeypatch, capsys) -> None:
    captured_config: list[object] = []

    class FakeRunner:
        def __init__(
            self,
            config,
            jira_client=None,
            confluence_client=None,
            *,
            today=None,
            step_reporter=None,
            run_start_reporter=None,
        ) -> None:
            captured_config.append(config)
            self._run_start_reporter = run_start_reporter

        def run(self, tagging_version: str, execution_mode: ExecutionMode) -> RunSummary:
            summary = RunSummary(
                tagging_version=tagging_version,
                execution_mode=execution_mode,
                release_date="2026-03-30",
                target_page_title="IPRON v6.2.0-b4h19",
                next_patch_version="6.2.1",
                fileserver_url="http://100.100.103.9:8088/IPRON/6.2/6.2.0b4h19",
            )
            if self._run_start_reporter is not None:
                self._run_start_reporter(summary)
            return summary

    monkeypatch.setattr(cli_module, "ReleaseRunner", FakeRunner)

    exit_code = cli_module.main(
        [
            "run",
            "--tagging-version",
            "6.2.0-b4h19",
            "--dry-run",
            "--username",
            "release-user",
            "--password",
            "release-pass",
        ]
    )
    capsys.readouterr()

    assert exit_code == 0
    config = captured_config[0]
    assert config.jira.base_url == "http://qa.bridgetec.co.kr"
    assert config.confluence.base_url == "http://qa.bridgetec.co.kr"
    assert config.jira.project_key == "IPR"
    assert config.confluence.space_key == "PAC"
    assert config.jira.username == "release-user"
    assert config.confluence.username == "release-user"
