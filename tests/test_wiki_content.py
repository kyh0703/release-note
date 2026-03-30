from release_note.models import JiraIssue
from release_note.versioning import TaggingVersion
from release_note.wiki_content import AUTOMATION_END, AUTOMATION_START, prepare_storage_content


def test_prepare_storage_content_updates_release_notes_and_server_packages() -> None:
    base = """
<h1>Release Notes</h1>
<ac:macro ac:name="panel"><ac:rich-text-body><p>old</p></ac:rich-text-body></ac:macro>
<h1>Server Packages</h1>
<p><a href="http://old.example.com/path">IPRONv6.2.0-b4h18&nbsp; package link</a></p>
"""

    content = prepare_storage_content(
        base_content=base,
        tagging_version=TaggingVersion.parse("6.2.0-b4h19"),
        release_note_html="<ul><li>장애지원</li></ul>",
        fileserver_url="http://100.100.103.9:8088/IPRON/6.2/6.2.0b4h19",
        attachment_strategy="reuse",
        version_issues=[],
    )

    assert "<ac:rich-text-body><ul><li>장애지원</li></ul></ac:rich-text-body>" in content
    assert 'href="http://100.100.103.9:8088/IPRON/6.2/6.2.0b4h19"' in content
    assert "IPRONv6.2.0-b4h19&nbsp; package link" in content
    assert "http://100.100.103.9:8088/IPRON/6.2/6.2.0b4h19" in content


def test_prepare_storage_content_removes_existing_automation_block() -> None:
    base = "<p>Existing body</p>\n" f"{AUTOMATION_START}\nold\n{AUTOMATION_END}\n"

    content = prepare_storage_content(
        base_content=base,
        tagging_version=TaggingVersion.parse("6.2.0-b4h19"),
        release_note_html="<p>new</p>",
        fileserver_url="http://100.100.103.9:8088/IPRON/6.2/6.2.0b4h19",
        attachment_strategy="reuse",
        version_issues=[],
    )

    assert AUTOMATION_START not in content
    assert AUTOMATION_END not in content
    assert "old" not in content
    assert content == "<p>Existing body</p>"


def test_prepare_storage_content_rolls_new_version_into_old_version_and_sets_current() -> None:
    base = """
<h2>Version Up Packages</h2>
<table>
  <tr><th>Package</th><th>Old Version</th><th>New Version</th></tr>
  <tr><td>ipron-ie</td><td>v6.2.0-b4h18</td><td></td></tr>
  <tr><td>ipron-ic</td><td>v6.2.0-b4h17</td><td>v6.2.0-b4h19</td></tr>
  <tr><td>ipron-gs</td><td>v6.2.0-b4h17</td><td>v6.2.0-b4h19</td></tr>
</table>
"""

    content = prepare_storage_content(
        base_content=base,
        tagging_version=TaggingVersion.parse("v6.2.0-b4h20"),
        release_note_html="<p>new</p>",
        fileserver_url="http://100.100.103.9:8088/IPRON/6.2/6.2.0b4h20",
        attachment_strategy="reuse",
        version_issues=[
            JiraIssue(key="IPR-1", summary="IC package fix"),
            JiraIssue(key="IPR-2", summary="GS package fix"),
        ],
    )

    assert "<td>ipron-ie</td><td>v6.2.0-b4h18</td><td></td>" in content
    assert "<td>ipron-ic</td><td>v6.2.0-b4h19</td><td>v6.2.0-b4h20</td>" in content
    assert "<td>ipron-gs</td><td>v6.2.0-b4h19</td><td>v6.2.0-b4h20</td>" in content


def test_prepare_storage_content_updates_table_inside_confluence_panel_macro() -> None:
    base = """
<h1>Version Up Packages</h1>
<ac:macro ac:name="panel">
  <ac:rich-text-body>
    <table>
      <tbody>
        <tr><th>Package</th><th>Old Version</th><th>New Version</th></tr>
        <tr><td>ipron-ie</td><td><p>v5.1.1-b3h71</p></td><td><p>&nbsp;</p></td></tr>
        <tr><td>ipron-ic</td><td><p>v5.1.1-b3h73</p></td><td><span>v5.1.1-b3h74</span></td></tr>
      </tbody>
    </table>
  </ac:rich-text-body>
</ac:macro>
"""

    content = prepare_storage_content(
        base_content=base,
        tagging_version=TaggingVersion.parse("v5.1.1-b3h75"),
        release_note_html="<p>new</p>",
        fileserver_url="http://100.100.103.9:8088/IPRON/5.1/5.1.1b3h75",
        attachment_strategy="reuse",
        version_issues=[JiraIssue(key="IPR-1", summary="IE package fix")],
    )

    assert "<td>ipron-ie</td><td>v5.1.1-b3h71</td><td>v5.1.1-b3h75</td>" in content
    assert "<td>ipron-ic</td><td>v5.1.1-b3h74</td><td></td>" in content
