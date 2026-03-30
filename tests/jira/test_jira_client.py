from release_note.config import JiraConfig
from release_note.jira_client import JiraClient
from release_note.models import JiraVersion

from tests.support import FakeResponse, ScriptedSession


def test_find_version_by_name_reads_versions_endpoint() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data=[
                {
                    "id": "10",
                    "name": "6.2.0-b4h19",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/10",
                    "released": False,
                }
            ]
        )
    )
    client = JiraClient(
        JiraConfig(
            base_url="https://qa.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        session=session,
    )

    version = client.find_version_by_name("6.2.0-b4h19")

    assert version.version_id == "10"
    assert version.project_id == "10001"
    assert session.calls[0].url.endswith("/jira/rest/api/2/project/IPR/versions")


def test_find_version_by_name_accepts_jira_versions_with_leading_v() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data=[
                {
                    "id": "10",
                    "name": "v5.1.1-b3h75",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/10",
                    "released": False,
                }
            ]
        )
    )
    client = JiraClient(
        JiraConfig(
            base_url="https://qa.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        session=session,
    )

    version = client.find_version_by_name("5.1.1-b3h75")

    assert version.name == "v5.1.1-b3h75"


def test_fetch_release_notes_parses_textarea_for_text_and_html() -> None:
    session = ScriptedSession(
        FakeResponse(text="<html><textarea>Text summary</textarea></html>"),
        FakeResponse(text="<html><textarea><ul><li>HTML summary</li></ul></textarea></html>"),
    )
    client = JiraClient(
        JiraConfig(
            base_url="https://qa.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        session=session,
    )

    bundle = client.fetch_release_notes(
        JiraVersion(
            version_id="10",
            name="6.2.0-b4h19",
            project_id="10001",
        )
    )

    assert bundle.text == "Text summary"
    assert bundle.html == "<ul><li>HTML summary</li></ul>"


def test_list_version_issues_reads_search_results() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data={
                "startAt": 0,
                "maxResults": 100,
                "total": 1,
                "issues": [
                    {
                        "key": "IPR-1",
                        "fields": {
                            "summary": "IC package fix",
                            "description": "Affects IC module",
                            "components": [{"name": "IC"}],
                            "assignee": {
                                "name": "honggildong",
                                "displayName": "홍길동",
                                "emailAddress": "honggildong@example.com",
                            },
                            "status": {
                                "name": "In Progress",
                                "statusCategory": {"key": "indeterminate"},
                            },
                        },
                    }
                ],
            }
        )
    )
    client = JiraClient(
        JiraConfig(
            base_url="https://qa.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        session=session,
    )

    issues = client.list_version_issues("v5.1.1-b3h75")

    assert issues[0].key == "IPR-1"
    assert issues[0].summary == "IC package fix"
    assert "IC module" in issues[0].description
    assert issues[0].components == ("IC",)
    assert issues[0].assignee_name == "honggildong"
    assert issues[0].assignee_display_name == "홍길동"
    assert issues[0].assignee_email == "honggildong@example.com"
    assert issues[0].status_name == "In Progress"
    assert issues[0].status_category_key == "indeterminate"
    assert issues[0].is_closed is False
    assert session.calls[0].kwargs["params"]["jql"] == (
        'project = IPR AND fixVersion = "v5.1.1-b3h75"'
    )


def test_release_version_sends_release_date_payload() -> None:
    session = ScriptedSession(FakeResponse(json_data={"id": "10"}))
    client = JiraClient(
        JiraConfig(
            base_url="https://qa.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        session=session,
    )

    changed = client.release_version(
        JiraVersion(version_id="10", name="6.2.0-b4h19", project_id="10001"),
        "2026-03-30",
    )

    assert changed is True
    assert session.calls[0].method == "PUT"
    assert session.calls[0].kwargs["json"] == {
        "released": True,
        "releaseDate": "2026-03-30",
    }


def test_ensure_version_exists_skips_existing_version() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data=[
                {
                    "id": "11",
                    "name": "6.2.1",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/11",
                    "released": False,
                }
            ]
        )
    )
    client = JiraClient(
        JiraConfig(
            base_url="https://qa.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        session=session,
    )

    result = client.ensure_version_exists(project_id="10001", version_name="6.2.1")

    assert result.created is False
    assert result.version_id == "11"
    assert result.moved is False


def test_ensure_version_exists_moves_new_version_before_current_version() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data=[
                {
                    "id": "20",
                    "name": "v6.3.0-b1h1",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/20",
                    "released": False,
                },
                {
                    "id": "10",
                    "name": "v6.2.0-b4h19",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/10",
                    "released": True,
                },
            ]
        ),
        FakeResponse(
            json_data={
                "id": "21",
                "name": "v6.2.0-b4h20",
                "projectId": "10001",
                "self": "https://qa.example.com/jira/rest/api/2/version/21",
            }
        ),
        FakeResponse(json_data={"id": "21"}),
    )
    client = JiraClient(
        JiraConfig(
            base_url="https://qa.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        session=session,
    )

    result = client.ensure_version_exists(
        project_id="10001",
        version_name="6.2.0-b4h20",
        before_version_name="v6.2.0-b4h19",
    )

    assert result.created is True
    assert result.move_action == "after"
    assert result.move_reference == "v6.2.0-b4h19"
    assert session.calls[1].kwargs["json"] == {"name": "v6.2.0-b4h20", "project": "IPR"}
    assert session.calls[2].url.endswith("/jira/rest/api/2/version/21/move")
    assert session.calls[2].kwargs["json"] == {
        "after": "https://qa.example.com/jira/rest/api/2/version/10"
    }


def test_preview_version_creation_moves_after_current_version() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data=[
                {
                    "id": "10",
                    "name": "6.2.0-b4h19",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/10",
                    "released": True,
                }
            ]
        )
    )
    client = JiraClient(
        JiraConfig(
            base_url="https://qa.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        session=session,
    )

    preview = client.preview_version_creation(
        version_name="6.2.0-b4h20",
        before_version_name="6.2.0-b4h19",
    )

    assert preview["already_exists"] is False
    assert preview["move_action"] == "after"
    assert preview["move_reference"] == "6.2.0-b4h19"


def test_preview_version_creation_uses_leading_v_when_current_version_uses_it() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data=[
                {
                    "id": "10",
                    "name": "v5.1.1-b3h75",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/10",
                    "released": True,
                }
            ]
        )
    )
    client = JiraClient(
        JiraConfig(
            base_url="https://qa.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        session=session,
    )

    preview = client.preview_version_creation(
        version_name="5.1.1-b3h76",
        before_version_name="v5.1.1-b3h75",
    )

    assert preview["already_exists"] is False
    assert preview["version_name"] == "v5.1.1-b3h76"


def test_preview_version_creation_keeps_direct_adjacency_with_current_version() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data=[
                {
                    "id": "74",
                    "name": "v5.1.1-b3h74",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/74",
                    "released": True,
                },
                {
                    "id": "75",
                    "name": "v5.1.1-b3h75",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/75",
                    "released": True,
                },
                {
                    "id": "76",
                    "name": "v5.1.1-b4",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/76",
                    "released": False,
                },
                {
                    "id": "77",
                    "name": "v5.1.2",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/77",
                    "released": False,
                },
            ]
        )
    )
    client = JiraClient(
        JiraConfig(
            base_url="https://qa.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        session=session,
    )

    preview = client.preview_version_creation(
        version_name="5.1.1-b3h76",
        before_version_name="v5.1.1-b3h75",
    )

    assert preview["already_exists"] is False
    assert preview["move_action"] == "after"
    assert preview["move_reference"] == "v5.1.1-b3h75"


def test_ensure_version_exists_moves_existing_version_after_current_version() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data=[
                {
                    "id": "74",
                    "name": "v5.1.1-b3h74",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/74",
                    "released": True,
                },
                {
                    "id": "75",
                    "name": "v5.1.1-b3h75",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/75",
                    "released": True,
                },
                {
                    "id": "76",
                    "name": "v5.1.1-b3h76",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/76",
                    "released": False,
                },
            ]
        ),
        FakeResponse(json_data={"id": "76"}),
    )
    client = JiraClient(
        JiraConfig(
            base_url="https://qa.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        session=session,
    )

    result = client.ensure_version_exists(
        project_id="10001",
        version_name="5.1.1-b3h76",
        before_version_name="v5.1.1-b3h75",
    )

    assert result.created is False
    assert result.moved is True
    assert result.move_action == "after"
    assert result.move_reference == "v5.1.1-b3h75"
    assert session.calls[1].url.endswith("/jira/rest/api/2/version/76/move")
    assert session.calls[1].kwargs["json"] == {
        "after": "https://qa.example.com/jira/rest/api/2/version/75"
    }


def test_preview_version_creation_reports_move_for_existing_version() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data=[
                {
                    "id": "75",
                    "name": "v5.1.1-b3h75",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/75",
                    "released": True,
                },
                {
                    "id": "76",
                    "name": "v5.1.1-b3h76",
                    "projectId": "10001",
                    "self": "https://qa.example.com/jira/rest/api/2/version/76",
                    "released": False,
                },
            ]
        )
    )
    client = JiraClient(
        JiraConfig(
            base_url="https://qa.example.com",
            username="jira-user",
            password="jira-pass",
        ),
        session=session,
    )

    preview = client.preview_version_creation(
        version_name="5.1.1-b3h76",
        before_version_name="v5.1.1-b3h75",
    )

    assert preview["already_exists"] is True
    assert preview["move_action"] == "after"
    assert preview["move_reference"] == "v5.1.1-b3h75"
