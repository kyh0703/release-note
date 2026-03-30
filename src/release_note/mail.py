from __future__ import annotations

import html
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from .config import SmtpConfig
from .errors import ConfigError, NotificationError
from .models import JiraIssue


@dataclass(frozen=True)
class OpenIssueNotification:
    recipient: str
    recipient_name: str
    subject: str
    text_body: str
    html_body: str
    issue_keys: list[str]


def prepare_open_issue_notifications(
    *,
    project_key: str,
    version_name: str,
    issues: list[JiraIssue],
    default_suffix: str,
) -> list[OpenIssueNotification]:
    grouped: dict[str, list[JiraIssue]] = {}
    recipient_names: dict[str, str] = {}

    for issue in issues:
        username = _resolve_assignee_username(issue)
        if not username:
            raise ConfigError(
                f"Jira issue '{issue.key}' does not contain assignee username or email."
            )
        recipient = normalize_email_address(username, default_suffix)
        grouped.setdefault(recipient, []).append(issue)
        recipient_names.setdefault(
            recipient,
            issue.assignee_display_name or issue.assignee_name or recipient,
        )

    notifications: list[OpenIssueNotification] = []
    for recipient, recipient_issues in grouped.items():
        subject = f"[{project_key}] {version_name} 배포 후 미종결 이슈 확인 요청"
        text_body = build_open_issue_text_body(
            version_name=version_name,
            recipient_name=recipient_names[recipient],
            issues=recipient_issues,
        )
        html_body = build_open_issue_html_body(
            version_name=version_name,
            recipient_name=recipient_names[recipient],
            issues=recipient_issues,
        )
        notifications.append(
            OpenIssueNotification(
                recipient=recipient,
                recipient_name=recipient_names[recipient],
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                issue_keys=[issue.key for issue in recipient_issues],
            )
        )
    return notifications


def build_open_issue_text_body(
    *,
    version_name: str,
    recipient_name: str,
    issues: list[JiraIssue],
) -> str:
    issue_lines: list[str] = []
    for issue in issues:
        issue_lines.append(f"- {issue.key}: {issue.summary}")
        issue_lines.append(f"  {issue.browse_url}")

    return "\n".join(
        [
            f"{recipient_name}님, 안녕하세요.",
            "",
            f"{version_name} 버전이 배포되었습니다.",
            "배포 이후에도 아직 닫히지 않은 담당 이슈가 있어 확인을 요청드립니다.",
            "아래 이슈를 확인하신 뒤 필요한 조치를 진행해 주세요.",
            "",
            *issue_lines,
            "",
            "감사합니다.",
        ]
    )


def build_open_issue_html_body(
    *,
    version_name: str,
    recipient_name: str,
    issues: list[JiraIssue],
) -> str:
    items = []
    for issue in issues:
        items.append(
            "<li>"
            f"<a href=\"{html.escape(issue.browse_url, quote=True)}\">"
            f"{html.escape(issue.key)}</a>: {html.escape(issue.summary)}"
            "</li>"
        )
    return (
        f"<p>{html.escape(recipient_name)}님, 안녕하세요.</p>"
        f"<p>{html.escape(version_name)} 버전이 배포되었습니다.<br/>"
        "배포 이후에도 아직 닫히지 않은 담당 이슈가 있어 확인을 요청드립니다.<br/>"
        "아래 이슈를 확인하신 뒤 필요한 조치를 진행해 주세요.</p>"
        f"<ul>{''.join(items)}</ul>"
        "<p>감사합니다.</p>"
    )


def normalize_email_address(value: str, default_suffix: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ConfigError("A mail address or username is required.")
    if "@" in normalized:
        return normalized
    suffix = default_suffix if default_suffix.startswith("@") else f"@{default_suffix}"
    return f"{normalized}{suffix}"


def _resolve_assignee_username(issue: JiraIssue) -> str:
    username = issue.assignee_name.strip()
    if username:
        return username
    if issue.assignee_email:
        email_username = issue.assignee_email.strip().split("@", 1)[0]
        if email_username:
            return email_username
    return ""


class SmtpClient:
    def __init__(
        self,
        config: SmtpConfig,
        *,
        smtp_factory: type[smtplib.SMTP] = smtplib.SMTP,
        smtp_ssl_factory: type[smtplib.SMTP_SSL] = smtplib.SMTP_SSL,
    ) -> None:
        self.config = config
        self.smtp_factory = smtp_factory
        self.smtp_ssl_factory = smtp_ssl_factory

    def send_notifications(
        self,
        notifications: list[OpenIssueNotification],
        *,
        fallback_sender: str,
    ) -> None:
        if not notifications:
            return

        sender = normalize_email_address(
            self.config.from_address or self.config.username or fallback_sender,
            self.config.default_suffix,
        )
        reply_to = (
            normalize_email_address(self.config.reply_to, self.config.default_suffix)
            if self.config.reply_to
            else None
        )

        try:
            with self._connect() as smtp:
                if self.config.use_tls:
                    smtp.starttls()
                if self.config.username and self.config.password:
                    smtp.login(self.config.username, self.config.password)
                for notification in notifications:
                    message = EmailMessage()
                    message["Subject"] = notification.subject
                    message["From"] = sender
                    message["To"] = notification.recipient
                    if reply_to is not None:
                        message["Reply-To"] = reply_to
                    message.set_content(
                        notification.text_body,
                        subtype="plain",
                        charset="utf-8",
                    )
                    message.add_alternative(
                        notification.html_body,
                        subtype="html",
                        charset="utf-8",
                    )
                    smtp.send_message(message)
        except (OSError, smtplib.SMTPException, ValueError) as exc:
            raise NotificationError(f"SMTP notification failed: {exc}") from exc

    def _connect(self) -> smtplib.SMTP:
        port = self.config.resolve_port()
        if self.config.use_ssl:
            return self.smtp_ssl_factory(self.config.host, port, timeout=30)
        return self.smtp_factory(self.config.host, port, timeout=30)
