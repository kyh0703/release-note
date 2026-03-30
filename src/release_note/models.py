from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionMode(str, Enum):
    DRY_RUN = "dry-run"
    APPLY = "apply"

    @property
    def is_apply(self) -> bool:
        return self is ExecutionMode.APPLY


@dataclass(frozen=True)
class JiraProject:
    project_id: str
    key: str
    name: str


@dataclass(frozen=True)
class JiraVersion:
    version_id: str
    name: str
    project_id: str
    self_url: str | None = None
    released: bool = False
    release_date: str | None = None


@dataclass(frozen=True)
class ReleaseNoteBundle:
    text: str
    html: str


@dataclass(frozen=True)
class JiraIssue:
    key: str
    summary: str
    description: str = ""
    assignee_name: str = ""
    assignee_display_name: str | None = None
    assignee_email: str | None = None
    browse_url: str = ""
    components: tuple[str, ...] = ()
    status_name: str = ""
    status_category_key: str = ""

    @property
    def is_closed(self) -> bool:
        return self.status_category_key.strip().lower() == "done"


@dataclass(frozen=True)
class ConfluencePage:
    page_id: str | None
    title: str
    space_key: str
    content: str
    version: int | None = None
    parent_id: str | None = None

    @classmethod
    def from_rpc(cls, payload: dict[str, Any]) -> "ConfluencePage":
        version_value = payload.get("version")
        if isinstance(version_value, dict):
            version = version_value.get("version")
        else:
            version = version_value
        return cls(
            page_id=str(payload["id"]) if payload.get("id") is not None else None,
            title=str(payload["title"]),
            space_key=str(payload["space"]),
            content=str(payload.get("content", "")),
            version=int(version) if version is not None else None,
            parent_id=(
                str(payload["parentId"]) if payload.get("parentId") is not None else None
            ),
        )

    def to_rpc_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "title": self.title,
            "space": self.space_key,
            "content": self.content,
        }
        if self.page_id is not None:
            payload["id"] = self.page_id
        if self.version is not None:
            payload["version"] = self.version
        if self.parent_id is not None:
            payload["parentId"] = self.parent_id
        return payload

    def clone_for_create(self, *, title: str, content: str) -> "ConfluencePage":
        return ConfluencePage(
            page_id=None,
            title=title,
            space_key=self.space_key,
            content=content,
            version=1,
            parent_id=self.parent_id,
        )

    def clone_for_update(self, *, content: str) -> "ConfluencePage":
        return ConfluencePage(
            page_id=self.page_id,
            title=self.title,
            space_key=self.space_key,
            content=content,
            version=self.version,
            parent_id=self.parent_id,
        )


@dataclass(frozen=True)
class CreateOrSkipResult:
    created: bool
    version_name: str
    version_id: str | None = None
    move_action: str | None = None
    move_reference: str | None = None


@dataclass
class RunStep:
    name: str
    status: str
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunSummary:
    tagging_version: str
    execution_mode: ExecutionMode
    release_date: str
    target_page_title: str
    next_patch_version: str
    fileserver_url: str | None = None
    steps: list[RunStep] = field(default_factory=list)

    def add_step(
        self,
        name: str,
        status: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.steps.append(
            RunStep(
                name=name,
                status=status,
                message=message,
                payload=payload or {},
            )
        )

    def to_text(self) -> str:
        lines = [
            f"mode: {self.execution_mode.value}",
            f"tagging_version: {self.tagging_version}",
            f"target_page_title: {self.target_page_title}",
            f"next_patch_version: {self.next_patch_version}",
            f"release_date: {self.release_date}",
        ]
        if self.fileserver_url is not None:
            lines.append(f"fileserver_url: {self.fileserver_url}")
        lines.append("steps:")
        for step in self.steps:
            lines.append(f"- [{step.status}] {step.name}: {step.message}")
            if step.payload:
                lines.append(
                    f"  payload: {json.dumps(step.payload, ensure_ascii=False, sort_keys=True)}"
                )
        return "\n".join(lines)
