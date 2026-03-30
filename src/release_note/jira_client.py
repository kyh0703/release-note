from __future__ import annotations

from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlencode

import requests

from .config import JiraConfig
from .errors import ApiError, NotFoundError
from .models import (
    CreateOrSkipResult,
    JiraIssue,
    JiraProject,
    JiraVersion,
    ReleaseNoteBundle,
)


class _TextareaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_textarea = False
        self._parts: list[str] = []
        self.textarea: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "textarea" and self.textarea is None:
            self._in_textarea = True

    def handle_data(self, data: str) -> None:
        if self._in_textarea:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "textarea" and self._in_textarea:
            self._in_textarea = False
            self.textarea = "".join(self._parts).strip()


class JiraClient:
    def __init__(
        self,
        config: JiraConfig,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        self.session.auth = (config.username, config.password)

    def get_project(self) -> JiraProject:
        response = self._send(
            "get",
            self._url(f"/jira/rest/api/2/project/{self.config.project_key}"),
            timeout=30,
        )
        payload = self._json(response)
        return JiraProject(
            project_id=str(payload["id"]),
            key=str(payload["key"]),
            name=str(payload["name"]),
        )

    def list_versions(self) -> list[JiraVersion]:
        response = self._send(
            "get",
            self._url(f"/jira/rest/api/2/project/{self.config.project_key}/versions"),
            timeout=30,
        )
        payload = self._json(response)
        return [self._parse_version(item) for item in payload]

    def has_version(self, version_name: str) -> bool:
        versions = self.list_versions()
        return self._find_matching_version(versions, version_name) is not None

    def find_version_by_name(self, version_name: str) -> JiraVersion:
        version = self._find_matching_version(self.list_versions(), version_name)
        if version is not None:
            if version.project_id:
                return version
            project = self.get_project()
            return JiraVersion(
                version_id=version.version_id,
                name=version.name,
                project_id=project.project_id,
                self_url=version.self_url,
                released=version.released,
                release_date=version.release_date,
            )
        raise NotFoundError(f"Jira version '{version_name}' was not found.")

    def fetch_release_notes(self, version: JiraVersion) -> ReleaseNoteBundle:
        text = self._fetch_release_note(version, "Text")
        html = self._fetch_release_note(version, "Html")
        return ReleaseNoteBundle(text=text, html=html)

    def list_version_issues(self, version_name: str) -> list[JiraIssue]:
        start_at = 0
        issues: list[JiraIssue] = []
        while True:
            response = self._send(
                "get",
                self._url("/jira/rest/api/2/search"),
                params={
                    "jql": f'project = {self.config.project_key} AND fixVersion = "{version_name}"',
                    "fields": "summary,description,components",
                    "startAt": start_at,
                    "maxResults": 100,
                },
                timeout=30,
            )
            payload = self._json(response)
            issue_items = payload.get("issues", [])
            for item in issue_items:
                fields = item.get("fields", {})
                issue_key = str(item["key"])
                issues.append(
                    JiraIssue(
                        key=issue_key,
                        summary=str(fields.get("summary", "")),
                        description=_stringify_description(fields.get("description")),
                        browse_url=self._url(f"/jira/browse/{issue_key}"),
                        components=tuple(
                            str(component.get("name", ""))
                            for component in fields.get("components", [])
                            if component.get("name")
                        ),
                    )
                )
            start_at += len(issue_items)
            total = int(payload.get("total", len(issue_items)))
            if start_at >= total or not issue_items:
                return issues

    def release_version(self, version: JiraVersion, release_date: str) -> bool:
        if version.released and version.release_date == release_date:
            return False
        response = self._send(
            "put",
            self._url(f"/jira/rest/api/2/version/{version.version_id}"),
            json={"released": True, "releaseDate": release_date},
            timeout=30,
        )
        self._json(response)
        return True

    def ensure_version_exists(
        self,
        *,
        project_id: str,
        version_name: str,
        before_version_name: str | None = None,
    ) -> CreateOrSkipResult:
        versions = self.list_versions()
        desired_name = self._canonical_version_name(
            version_name,
            before_version_name=before_version_name,
        )
        existing = self._find_matching_version(versions, desired_name)
        if existing is not None:
            return CreateOrSkipResult(
                created=False,
                version_name=existing.name,
                version_id=existing.version_id,
            )
        response = self._send(
            "post",
            self._url("/jira/rest/api/2/version"),
            json={"name": desired_name, "project": self.config.project_key},
            timeout=30,
        )
        payload = self._json(response)
        created_version = self._parse_version(payload)
        move_action = None
        move_reference = None
        if before_version_name is not None:
            move_payload, move_action, move_reference = self._build_move_before_payload(
                versions=versions,
                before_version_name=before_version_name,
            )
            self._send(
                "post",
                self._url(f"/jira/rest/api/2/version/{created_version.version_id}/move"),
                json=move_payload,
                timeout=30,
            ).raise_for_status()
        return CreateOrSkipResult(
            created=True,
            version_name=created_version.name,
            version_id=created_version.version_id,
            move_action=move_action,
            move_reference=move_reference,
        )

    def preview_version_creation(
        self, *, version_name: str, before_version_name: str | None = None
    ) -> dict[str, Any]:
        versions = self.list_versions()
        desired_name = self._canonical_version_name(
            version_name,
            before_version_name=before_version_name,
        )
        existing = self._find_matching_version(versions, desired_name)
        if existing is not None:
            return {
                "already_exists": True,
                "version_name": existing.name,
                "move_action": None,
                "move_reference": None,
            }
        move_action = None
        move_reference = None
        if before_version_name is not None:
            _, move_action, move_reference = self._build_move_before_payload(
                versions=versions,
                before_version_name=before_version_name,
            )
        return {
            "already_exists": False,
            "version_name": desired_name,
            "move_action": move_action,
            "move_reference": move_reference,
        }

    def _fetch_release_note(self, version: JiraVersion, style_name: str) -> str:
        params = urlencode(
            {
                "projectId": version.project_id,
                "version": version.version_id,
                "styleName": style_name,
                "Create": "Create",
            }
        )
        response = self._send(
            "get",
            self._url(f"/jira/secure/ReleaseNote.jspa?{params}"),
            timeout=30,
        )
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ApiError(f"Jira release note request failed: {exc}") from exc
        parser = _TextareaParser()
        parser.feed(response.text)
        if parser.textarea is None:
            raise ApiError(
                f"Jira release note response did not contain a textarea for {style_name}."
            )
        return parser.textarea

    def _url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}{path}"

    def _json(self, response: requests.Response) -> Any:
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = response.text.strip()
            if detail:
                raise ApiError(f"Jira request failed: {exc} | body: {detail}") from exc
            raise ApiError(f"Jira request failed: {exc}") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError("Jira returned invalid JSON.") from exc

    def _send(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        try:
            request = getattr(self.session, method)
            return request(url, **kwargs)
        except requests.RequestException as exc:
            raise ApiError(f"Jira request failed: {exc}") from exc

    def _parse_version(self, item: dict[str, Any]) -> JiraVersion:
        return JiraVersion(
            version_id=str(item["id"]),
            name=str(item["name"]),
            project_id=str(item.get("projectId", "")),
            self_url=str(item.get("self")) if item.get("self") else self._url(f"/jira/rest/api/2/version/{item['id']}"),
            released=bool(item.get("released", False)),
            release_date=item.get("releaseDate"),
        )

    def _build_move_before_payload(
        self,
        *,
        versions: list[JiraVersion],
        before_version_name: str,
    ) -> tuple[dict[str, str], str, str]:
        for index, version in enumerate(versions):
            if version.name != before_version_name:
                continue
            if index == 0:
                return {"position": "First"}, "position", "First"
            predecessor = versions[index - 1]
            if predecessor.self_url is None:
                raise ApiError(
                    f"Cannot move version before '{before_version_name}' without predecessor self link."
                )
            return {"after": predecessor.self_url}, "after", predecessor.name
        raise NotFoundError(
            f"Jira version '{before_version_name}' was not found for move planning."
        )

    def _find_matching_version(
        self, versions: list[JiraVersion], version_name: str
    ) -> JiraVersion | None:
        candidates = self._candidate_version_names(version_name)
        for version in versions:
            if version.name in candidates:
                return version
        return None

    def _canonical_version_name(
        self, version_name: str, *, before_version_name: str | None = None
    ) -> str:
        normalized = version_name.strip()
        if normalized.startswith("v"):
            return normalized
        if before_version_name is not None and before_version_name.startswith("v"):
            return f"v{normalized}"
        return normalized

    def _candidate_version_names(self, version_name: str) -> tuple[str, ...]:
        normalized = version_name.strip()
        if normalized.startswith("v"):
            return (normalized, normalized[1:])
        return (normalized, f"v{normalized}")


def _stringify_description(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_stringify_description(item) for item in value if item is not None)
    if isinstance(value, dict):
        parts: list[str] = []
        for item in value.values():
            text = _stringify_description(item)
            if text:
                parts.append(text)
        return "\n".join(parts)
    return str(value)
