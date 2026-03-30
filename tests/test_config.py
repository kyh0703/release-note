from release_note.config import (
    DEFAULT_BASE_URL,
    DEFAULT_CONFLUENCE_SPACE_KEY,
    DEFAULT_JIRA_PROJECT_KEY,
    DEFAULT_MAIL_FROM,
    DEFAULT_SMTP_HOST,
    RunnerConfig,
)
from release_note.versioning import TaggingVersion


def test_default_fileserver_url_template_matches_confirmed_pattern() -> None:
    config = RunnerConfig.from_cli_options()

    rendered = config.render_fileserver_url(TaggingVersion.parse("6.2.0-b4h19"))

    assert rendered == "http://100.100.103.9:8088/IPRON/6.2/6.2.0b4h19"


def test_common_cli_options_are_shared_between_jira_and_confluence() -> None:
    config = RunnerConfig.from_cli_options(
        username="release-user",
        password="release-pass",
    )

    assert config.jira.base_url == DEFAULT_BASE_URL
    assert config.confluence.base_url == DEFAULT_BASE_URL
    assert config.jira.project_key == DEFAULT_JIRA_PROJECT_KEY
    assert config.confluence.space_key == DEFAULT_CONFLUENCE_SPACE_KEY
    assert config.jira.username == "release-user"
    assert config.confluence.username == "release-user"

def test_smtp_defaults_are_hard_coded() -> None:
    config = RunnerConfig.from_cli_options()

    assert config.smtp.host == DEFAULT_SMTP_HOST
    assert config.smtp.from_address == DEFAULT_MAIL_FROM
    assert config.smtp.default_suffix == "@bridgetec.co.kr"


def test_parse_page_title_version_extracts_raw_version_from_default_template() -> None:
    config = RunnerConfig.from_cli_options()

    version = config.parse_page_title_version("IPRON v6.2.0-b4h19")

    assert version is not None
    assert version.raw == "6.2.0-b4h19"
