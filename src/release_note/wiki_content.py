from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

from .errors import ConfigError
from .models import JiraIssue
from .versioning import TaggingVersion

AUTOMATION_START = "<!-- release-note:automation:start -->"
AUTOMATION_END = "<!-- release-note:automation:end -->"
_AUTOMATION_BLOCK_PATTERN = re.compile(
    rf"{re.escape(AUTOMATION_START)}.*?{re.escape(AUTOMATION_END)}",
    re.DOTALL,
)
_VERSION_UP_PACKAGES_HEADING_PATTERN = re.compile(
    r"<h[1-6][^>]*>\s*Version Up Packages\s*</h[1-6]>",
    re.IGNORECASE,
)
_RELEASE_NOTES_HEADING_PATTERN = re.compile(
    r"<h[1-6][^>]*>\s*(?:<span[^>]*>\s*)*Release Notes\s*(?:</span>\s*)*</h[1-6]>",
    re.IGNORECASE,
)
_SERVER_PACKAGES_HEADING_PATTERN = re.compile(
    r"<h[1-6][^>]*>\s*(?:<span[^>]*>\s*)*Server Packages\s*(?:</span>\s*)*</h[1-6]>",
    re.IGNORECASE,
)
_TABLE_START_PATTERN = re.compile(r"<table\b", re.IGNORECASE)
_TABLE_END_PATTERN = re.compile(r"</table>", re.IGNORECASE)
_RICH_TEXT_BODY_START_PATTERN = re.compile(r"<ac:rich-text-body>", re.IGNORECASE)
_RICH_TEXT_BODY_END_PATTERN = re.compile(r"</ac:rich-text-body>", re.IGNORECASE)
_HEADING_PATTERN = re.compile(r"<h[1-6]\b", re.IGNORECASE)
_ANCHOR_PATTERN = re.compile(
    r'(<a\b[^>]*href=")([^"]*)(".*?>)(.*?)(</a>)',
    re.IGNORECASE | re.DOTALL,
)
_ROW_PATTERN = re.compile(r"<tr\b[^>]*>.*?</tr>", re.DOTALL | re.IGNORECASE)
_CELL_PATTERN = re.compile(r"(<t[hd]\b[^>]*>)(.*?)(</t[hd]>)", re.DOTALL | re.IGNORECASE)
_PACKAGE_CODE_PATTERN = re.compile(r"\b(IE|IC|GS|DI|MS|ID|IR|FC)\b", re.IGNORECASE)
_VERSION_TOKEN_PATTERN = re.compile(r"v\d+\.\d+\.\d+(?:-[A-Za-z0-9]+)?")


def prepare_storage_content(
    *,
    base_content: str,
    tagging_version: TaggingVersion,
    release_note_html: str,
    fileserver_url: str,
    attachment_strategy: str,
    version_issues: list[JiraIssue],
) -> str:
    if attachment_strategy != "reuse":
        raise ConfigError(
            "Only attachment/reference reuse is supported until the copy strategy is verified."
        )
    cleaned_content = _AUTOMATION_BLOCK_PATTERN.sub("", base_content).strip()
    rolled_content = update_version_up_packages_table(
        base_content=cleaned_content,
        tagging_version=tagging_version,
        version_issues=version_issues,
    )
    release_note_content = update_release_notes_section(
        base_content=rolled_content,
        release_note_html=release_note_html,
    )
    return update_server_packages_link(
        base_content=release_note_content,
        tagging_version=tagging_version,
        fileserver_url=fileserver_url,
    ).strip()


def update_release_notes_section(*, base_content: str, release_note_html: str) -> str:
    note_html = release_note_html.strip() or "<p>(empty release note)</p>"
    return _replace_first_rich_text_body_after_heading(
        base_content=base_content,
        heading_pattern=_RELEASE_NOTES_HEADING_PATTERN,
        replacement_html=note_html,
    )


def update_server_packages_link(
    *,
    base_content: str,
    tagging_version: TaggingVersion,
    fileserver_url: str,
) -> str:
    heading_match = _SERVER_PACKAGES_HEADING_PATTERN.search(base_content)
    if heading_match is None:
        return base_content

    section_start = heading_match.end()
    next_heading_match = _HEADING_PATTERN.search(base_content, section_start)
    section_end = next_heading_match.start() if next_heading_match is not None else len(
        base_content
    )
    section = base_content[section_start:section_end]
    link_match = _ANCHOR_PATTERN.search(section)
    if link_match is None:
        return base_content

    inner_html = _VERSION_TOKEN_PATTERN.sub(
        f"v{tagging_version.raw}", link_match.group(4), count=1
    )
    updated_link = (
        f"{link_match.group(1)}{escape(fileserver_url, quote=True)}"
        f"{link_match.group(3)}{inner_html}{link_match.group(5)}"
    )
    updated_section = (
        f"{section[:link_match.start()]}"
        f"{updated_link}"
        f"{section[link_match.end():]}"
    )
    return f"{base_content[:section_start]}{updated_section}{base_content[section_end:]}"


def update_version_up_packages_table(
    *,
    base_content: str,
    tagging_version: TaggingVersion,
    version_issues: list[JiraIssue],
) -> str:
    heading_match = _VERSION_UP_PACKAGES_HEADING_PATTERN.search(base_content)
    if heading_match is None:
        return base_content

    table_start_match = _TABLE_START_PATTERN.search(base_content, heading_match.end())
    if table_start_match is None:
        return base_content

    table_end_match = _TABLE_END_PATTERN.search(base_content, table_start_match.start())
    if table_end_match is None:
        return base_content

    affected_codes = detect_affected_package_codes(version_issues)
    updated_table = _rewrite_version_up_packages_table(
        base_content[table_start_match.start() : table_end_match.end()],
        tagging_version.version_name,
        affected_codes,
    )
    return (
        f"{base_content[:table_start_match.start()]}"
        f"{updated_table}"
        f"{base_content[table_end_match.end():]}"
    )


def _rewrite_version_up_packages_table(
    table_html: str, version_name: str, affected_codes: set[str]
) -> str:
    chunks: list[str] = []
    cursor = 0
    for match in _ROW_PATTERN.finditer(table_html):
        chunks.append(table_html[cursor : match.start()])
        chunks.append(
            _rewrite_version_up_packages_row(match.group(0), version_name, affected_codes)
        )
        cursor = match.end()
    chunks.append(table_html[cursor:])
    return "".join(chunks)


def _rewrite_version_up_packages_row(
    row_html: str, version_name: str, affected_codes: set[str]
) -> str:
    cells = list(_CELL_PATTERN.finditer(row_html))
    if len(cells) < 3:
        return row_html

    package_name = _normalize_html_text(cells[0].group(2)).lower()
    if package_name == "package":
        return row_html

    package_code = package_name.rsplit("-", 1)[-1].upper()
    current_old = _normalize_html_text(cells[1].group(2))
    current_new = _normalize_html_text(cells[2].group(2))
    rolled_old = current_new or current_old
    next_new = version_name if package_code in affected_codes else ""

    replacements = {
        1: escape(rolled_old),
        2: escape(next_new),
    }
    chunks: list[str] = []
    cursor = 0
    for index, cell in enumerate(cells):
        chunks.append(row_html[cursor : cell.start(2)])
        chunks.append(replacements.get(index, cell.group(2)))
        cursor = cell.end(2)
    chunks.append(row_html[cursor:])
    return "".join(chunks)


def _replace_first_rich_text_body_after_heading(
    *,
    base_content: str,
    heading_pattern: re.Pattern[str],
    replacement_html: str,
) -> str:
    heading_match = heading_pattern.search(base_content)
    if heading_match is None:
        return base_content

    body_start_match = _RICH_TEXT_BODY_START_PATTERN.search(base_content, heading_match.end())
    if body_start_match is None:
        return base_content

    body_end_match = _RICH_TEXT_BODY_END_PATTERN.search(base_content, body_start_match.end())
    if body_end_match is None:
        return base_content

    return (
        f"{base_content[:body_start_match.end()]}"
        f"{replacement_html.strip()}"
        f"{base_content[body_end_match.start():]}"
    )


def detect_affected_package_codes(version_issues: list[JiraIssue]) -> set[str]:
    affected: set[str] = set()
    for issue in version_issues:
        text = " ".join(
            part
            for part in [
                issue.key,
                issue.summary,
                issue.description,
                " ".join(issue.components),
            ]
            if part
        )
        for match in _PACKAGE_CODE_PATTERN.finditer(text.upper()):
            affected.add(match.group(1).upper())
    return affected


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _normalize_html_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return " ".join("".join(parser.parts).split())
