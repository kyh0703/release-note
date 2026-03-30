from release_note.config import ConfluenceConfig
from release_note.confluence_client import ConfluenceClient
from release_note.models import ConfluencePage

from tests.support import FakeResponse, ScriptedSession


def test_get_page_returns_none_for_missing_page_error() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"message": "NoSuchPageException: Could not find page"},
            }
        )
    )
    client = ConfluenceClient(
        ConfluenceConfig(
            base_url="https://qa.example.com",
            username="wiki-user",
            password="wiki-pass",
        ),
        session=session,
    )

    page = client.get_page("IPRON v6.2.0-b4h19")

    assert page is None


def test_get_page_prefers_prototype_rest_body_content() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": "2001",
                    "title": "IPRON v5.1.1-b3h75",
                    "space": "PAC",
                    "content": "<p>fallback</p>",
                    "version": 1,
                    "parentId": "100",
                },
            }
        ),
        FakeResponse(
            text=(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                "<content>"
                "<body>&lt;h1&gt;Release Notes&lt;/h1&gt;&lt;p&gt;status fix&lt;/p&gt;</body>"
                "</content>"
            )
        ),
    )
    client = ConfluenceClient(
        ConfluenceConfig(
            base_url="https://qa.example.com",
            username="wiki-user",
            password="wiki-pass",
        ),
        session=session,
    )

    page = client.get_page("IPRON v5.1.1-b3h75")

    assert page is not None
    assert "<p>status fix</p>" in page.content
    assert session.calls[1].method == "GET"
    assert session.calls[1].url.endswith("/wiki/rest/prototype/1/content/2001")


def test_get_page_returns_none_for_permission_or_missing_page_error() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "message": (
                        "The application was unable to serve your request: "
                        "com.atlassian.confluence.rpc.RemoteException: "
                        "You're not allowed to view that page, or it does not exist"
                    )
                },
            }
        )
    )
    client = ConfluenceClient(
        ConfluenceConfig(
            base_url="https://qa.example.com",
            username="wiki-user",
            password="wiki-pass",
        ),
        session=session,
    )

    page = client.get_page("IPRON v5.1.1-b3h75")

    assert page is None


def test_store_page_sends_json_rpc_payload() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": "2001",
                    "title": "IPRON v6.2.0-b4h19",
                    "space": "PAC",
                    "content": "<p>body</p>",
                    "version": 2,
                },
            }
        )
    )
    client = ConfluenceClient(
        ConfluenceConfig(
            base_url="https://qa.example.com",
            username="wiki-user",
            password="wiki-pass",
        ),
        session=session,
    )

    page = client.store_page(
        ConfluencePage(
            page_id="2001",
            title="IPRON v6.2.0-b4h19",
            space_key="PAC",
            content="<p>body</p>",
            version=2,
        )
    )

    assert page.page_id == "2001"
    assert session.calls[0].kwargs["json"]["method"] == "storePage"
    assert session.calls[0].kwargs["json"]["params"][0]["version"] == 2


def test_store_page_retries_with_latest_version_after_version_mismatch() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "message": (
                        "The application was unable to serve your request: "
                        "com.atlassian.confluence.rpc.VersionMismatchException: "
                        "You're trying to edit an outdated version of that page."
                    )
                },
            }
        ),
        FakeResponse(
            json_data={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "id": "2001",
                    "title": "IPRON v6.2.0-b4h19",
                    "space": "PAC",
                    "content": "<p>fallback body</p>",
                    "version": 3,
                    "parentId": "100",
                },
            }
        ),
        FakeResponse(
            text=(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                "<content><body>&lt;p&gt;old body&lt;/p&gt;</body></content>"
            )
        ),
        FakeResponse(
            json_data={
                "jsonrpc": "2.0",
                "id": 3,
                "result": {
                    "id": "2001",
                    "title": "IPRON v6.2.0-b4h19",
                    "space": "PAC",
                    "content": "<p>new body</p>",
                    "version": 4,
                    "parentId": "100",
                },
            }
        ),
    )
    client = ConfluenceClient(
        ConfluenceConfig(
            base_url="https://qa.example.com",
            username="wiki-user",
            password="wiki-pass",
        ),
        session=session,
    )

    page = client.store_page(
        ConfluencePage(
            page_id="2001",
            title="IPRON v6.2.0-b4h19",
            space_key="PAC",
            content="<p>new body</p>",
            version=2,
            parent_id="100",
        )
    )

    assert page.version == 4
    assert session.calls[1].kwargs["json"]["method"] == "getPage"
    assert session.calls[2].method == "GET"
    assert session.calls[3].kwargs["json"]["method"] == "storePage"
    assert session.calls[3].kwargs["json"]["params"][0]["version"] == 3


def test_move_page_sends_relative_position_payload() -> None:
    session = ScriptedSession(
        FakeResponse(
            json_data={
                "jsonrpc": "2.0",
                "id": 1,
                "result": None,
            }
        )
    )
    client = ConfluenceClient(
        ConfluenceConfig(
            base_url="https://qa.example.com",
            username="wiki-user",
            password="wiki-pass",
        ),
        session=session,
    )

    client.move_page("3001", "2001", "below")

    assert session.calls[0].kwargs["json"]["method"] == "movePage"
    assert session.calls[0].kwargs["json"]["params"] == ["3001", "2001", "below"]
