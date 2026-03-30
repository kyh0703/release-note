from email.message import EmailMessage

from release_note.config import SmtpConfig
from release_note.mail import SmtpClient, prepare_open_issue_notifications
from release_note.models import JiraIssue


def test_prepare_open_issue_notifications_groups_by_assignee_username() -> None:
    notifications = prepare_open_issue_notifications(
        project_key="IPR",
        version_name="v6.2.0-b4h19",
        issues=[
            JiraIssue(
                key="IPR-1",
                summary="First issue",
                assignee_name="honggildong",
                assignee_display_name="홍길동",
                assignee_email="other@example.com",
                browse_url="http://jira.example.com/jira/browse/IPR-1",
            ),
            JiraIssue(
                key="IPR-2",
                summary="Second issue",
                assignee_name="honggildong",
                assignee_display_name="홍길동",
                browse_url="http://jira.example.com/jira/browse/IPR-2",
            ),
        ],
        default_suffix="@bridgetec.co.kr",
    )

    assert len(notifications) == 1
    assert notifications[0].recipient == "honggildong@bridgetec.co.kr"
    assert notifications[0].recipient_name == "홍길동"
    assert notifications[0].issue_keys == ["IPR-1", "IPR-2"]
    assert "v6.2.0-b4h19" in notifications[0].subject


class _FakeSmtpTransport:
    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in_with: tuple[str, str] | None = None
        self.messages: list[EmailMessage] = []

    def __enter__(self) -> "_FakeSmtpTransport":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logged_in_with = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.messages.append(message)


def test_smtp_client_sends_grouped_notifications() -> None:
    transport = _FakeSmtpTransport("smtp.example.com", 2525, 30)

    def smtp_factory(host: str, port: int, timeout: int) -> _FakeSmtpTransport:
        assert host == "smtp.example.com"
        assert port == 2525
        assert timeout == 90
        return transport

    client = SmtpClient(
        SmtpConfig(
            host="smtp.example.com",
            port=2525,
            use_tls=True,
            username="smtp-user",
            password="smtp-pass",
            from_address="release@example.com",
            reply_to="team@example.com",
        ),
        smtp_factory=smtp_factory,
    )
    notifications = prepare_open_issue_notifications(
        project_key="IPR",
        version_name="v6.2.0-b4h19",
        issues=[
            JiraIssue(
                key="IPR-1",
                summary="First issue",
                assignee_name="honggildong",
                assignee_display_name="홍길동",
                browse_url="http://jira.example.com/jira/browse/IPR-1",
            )
        ],
        default_suffix="@bridgetec.co.kr",
    )

    client.send_notifications(notifications, fallback_sender="jira-user")

    assert transport.started_tls is True
    assert transport.logged_in_with == ("smtp-user", "smtp-pass")
    assert len(transport.messages) == 1
    assert transport.messages[0]["From"] == "release@example.com"
    assert transport.messages[0]["To"] == "honggildong@bridgetec.co.kr"
    assert transport.messages[0]["Reply-To"] == "team@example.com"
