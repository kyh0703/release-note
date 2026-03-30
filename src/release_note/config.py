from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ConfigError
from .versioning import TaggingVersion

DEFAULT_FILESERVER_URL_TEMPLATE = (
    "http://100.100.103.9:8088/IPRON/{major}.{minor}/{tag_version}"
)
DEFAULT_BASE_URL = "http://qa.bridgetec.co.kr"
DEFAULT_WIKI_PAGE_TITLE_TEMPLATE = "IPRON v{raw}"
DEFAULT_JIRA_PROJECT_KEY = "IPR"
DEFAULT_CONFLUENCE_SPACE_KEY = "PAC"
DEFAULT_SMTP_HOST = "mail.bridgetec.co.kr"
DEFAULT_MAIL_FROM = "jira@bridgetec.co.kr"
DEFAULT_MAIL_SUFFIX = "@bridgetec.co.kr"


@dataclass(frozen=True)
class JiraConfig:
    base_url: str = DEFAULT_BASE_URL
    username: str = ""
    password: str = ""
    project_key: str = DEFAULT_JIRA_PROJECT_KEY

    @property
    def is_configured(self) -> bool:
        return bool(self.username and self.password)

    def missing_fields(self) -> list[str]:
        return _missing_auth_flags(username=self.username, password=self.password)


@dataclass(frozen=True)
class ConfluenceConfig:
    base_url: str = DEFAULT_BASE_URL
    username: str = ""
    password: str = ""
    space_key: str = DEFAULT_CONFLUENCE_SPACE_KEY

    @property
    def is_configured(self) -> bool:
        return bool(self.username and self.password)

    def missing_fields(self) -> list[str]:
        return _missing_auth_flags(username=self.username, password=self.password)


@dataclass(frozen=True)
class SmtpConfig:
    host: str = DEFAULT_SMTP_HOST
    port: int | None = None
    use_tls: bool = False
    use_ssl: bool = False
    username: str = ""
    password: str = ""
    from_address: str = DEFAULT_MAIL_FROM
    reply_to: str = ""
    default_suffix: str = DEFAULT_MAIL_SUFFIX

    @property
    def is_configured(self) -> bool:
        return bool(self.host)

    def resolve_port(self) -> int:
        if self.port is not None:
            return self.port
        if self.use_ssl:
            return 465
        if self.use_tls:
            return 587
        return 25


@dataclass(frozen=True)
class RunnerConfig:
    jira: JiraConfig
    confluence: ConfluenceConfig
    smtp: SmtpConfig = field(default_factory=SmtpConfig)
    fileserver_url_template: str = DEFAULT_FILESERVER_URL_TEMPLATE
    wiki_page_title_template: str = DEFAULT_WIKI_PAGE_TITLE_TEMPLATE
    attachment_strategy: str = "reuse"
    notify_open_issues: bool = False

    @classmethod
    def from_cli_options(
        cls,
        *,
        username: str = "",
        password: str = "",
        fileserver_url_template: str = DEFAULT_FILESERVER_URL_TEMPLATE,
        wiki_page_title_template: str = DEFAULT_WIKI_PAGE_TITLE_TEMPLATE,
        attachment_strategy: str = "reuse",
        notify_open_issues: bool = False,
        smtp_host: str = DEFAULT_SMTP_HOST,
        smtp_port: int | None = None,
        smtp_use_tls: bool = False,
        smtp_use_ssl: bool = False,
        smtp_username: str = "",
        smtp_password: str = "",
        mail_from: str = DEFAULT_MAIL_FROM,
        mail_reply_to: str = "",
    ) -> "RunnerConfig":
        normalized_username = username.strip()
        normalized_password = password.strip()
        return cls(
            jira=JiraConfig(
                base_url=DEFAULT_BASE_URL,
                username=normalized_username,
                password=normalized_password,
                project_key=DEFAULT_JIRA_PROJECT_KEY,
            ),
            confluence=ConfluenceConfig(
                base_url=DEFAULT_BASE_URL,
                username=normalized_username,
                password=normalized_password,
                space_key=DEFAULT_CONFLUENCE_SPACE_KEY,
            ),
            smtp=SmtpConfig(
                host=smtp_host.strip() or DEFAULT_SMTP_HOST,
                port=smtp_port,
                use_tls=smtp_use_tls,
                use_ssl=smtp_use_ssl,
                username=smtp_username.strip(),
                password=smtp_password.strip(),
                from_address=mail_from.strip() or DEFAULT_MAIL_FROM,
                reply_to=mail_reply_to.strip(),
                default_suffix=DEFAULT_MAIL_SUFFIX,
            ),
            fileserver_url_template=fileserver_url_template.strip()
            or DEFAULT_FILESERVER_URL_TEMPLATE,
            wiki_page_title_template=wiki_page_title_template.strip()
            or DEFAULT_WIKI_PAGE_TITLE_TEMPLATE,
            attachment_strategy=attachment_strategy.strip() or "reuse",
            notify_open_issues=notify_open_issues,
        )

    def render_page_title(self, tagging_version: TaggingVersion) -> str:
        return tagging_version.render(self.wiki_page_title_template)

    def parse_page_title_version(self, title: str) -> TaggingVersion | None:
        placeholder = "{raw}"
        if self.wiki_page_title_template.count(placeholder) != 1:
            return None
        prefix, suffix = self.wiki_page_title_template.split(placeholder)
        if not title.startswith(prefix):
            return None
        if suffix and not title.endswith(suffix):
            return None
        raw = title[len(prefix) :]
        if suffix:
            raw = raw[: -len(suffix)]
        if not raw:
            return None
        try:
            return TaggingVersion.parse(raw)
        except ConfigError:
            return None

    def render_fileserver_url(self, tagging_version: TaggingVersion) -> str:
        if not self.fileserver_url_template:
            raise ConfigError(
                "RELEASE_NOTE_FILESERVER_URL_TEMPLATE is required for Confluence output."
            )
        return tagging_version.render(self.fileserver_url_template)

    def validate_for_apply(self) -> None:
        missing: list[str] = []
        missing.extend(self.jira.missing_fields())
        missing.extend(self.confluence.missing_fields())
        if not self.fileserver_url_template:
            missing.append("--fileserver-url-template")
        missing = list(dict.fromkeys(missing))
        if missing:
            joined = ", ".join(missing)
            raise ConfigError(f"apply mode requires configuration: {joined}")
        if self.attachment_strategy != "reuse":
            raise ConfigError(
                "Only RELEASE_NOTE_ATTACHMENT_STRATEGY=reuse is currently supported."
            )
        if self.smtp.use_tls and self.smtp.use_ssl:
            raise ConfigError("Only one of --smtp-use-tls or --smtp-use-ssl can be enabled.")
        if bool(self.smtp.username) != bool(self.smtp.password):
            raise ConfigError(
                "SMTP authentication requires both --smtp-username and --smtp-password."
            )


def _missing_auth_flags(*, username: str, password: str) -> list[str]:
    missing: list[str] = []
    if not username:
        missing.append("--username")
    if not password:
        missing.append("--password")
    return missing
