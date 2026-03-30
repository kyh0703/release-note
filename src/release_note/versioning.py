from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import ConfigError

_VERSION_PATTERN = re.compile(
    r"^(?:v)?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<suffix>[A-Za-z0-9][A-Za-z0-9._-]*))?$"
)


@dataclass(frozen=True)
class TaggingVersion:
    raw: str
    major: int
    minor: int
    patch: int
    suffix: str | None = None
    has_v_prefix: bool = False

    @classmethod
    def parse(cls, value: str) -> "TaggingVersion":
        normalized = value.strip()
        match = _VERSION_PATTERN.fullmatch(normalized)
        if match is None:
            raise ConfigError(
                "tagging-version must look like 6.2.0, v6.2.0, or 6.2.0-b4h19."
            )
        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))
        suffix = match.group("suffix")
        raw = f"{major}.{minor}.{patch}"
        if suffix:
            raw = f"{raw}-{suffix}"
        return cls(
            raw=raw,
            major=major,
            minor=minor,
            patch=patch,
            suffix=suffix,
            has_v_prefix=normalized.startswith("v"),
        )

    @property
    def semantic(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def previous_patch(self) -> str | None:
        if self.patch == 0:
            return None
        prefix = "v" if self.has_v_prefix else ""
        return f"{prefix}{self.major}.{self.minor}.{self.patch - 1}"

    def next_patch_name(self) -> str:
        prefix = "v" if self.has_v_prefix else ""
        return f"{prefix}{self.major}.{self.minor}.{self.patch + 1}"

    @property
    def tag_version(self) -> str:
        if self.suffix:
            return f"{self.semantic}{self.suffix}"
        return self.semantic

    @property
    def version_name(self) -> str:
        if self.has_v_prefix:
            return f"v{self.raw}"
        return self.raw

    def ordering_key(self) -> tuple[object, ...]:
        suffix_rank = 0 if self.suffix is not None else 1
        return (
            self.major,
            self.minor,
            self.patch,
            suffix_rank,
            _suffix_ordering_key(self.suffix),
            self.raw,
        )

    def template_values(self) -> dict[str, str | int | None]:
        return {
            "raw": self.raw,
            "version_name": self.version_name,
            "semantic": self.semantic,
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "suffix": self.suffix or "",
            "tag_version": self.tag_version,
            "previous_patch": self.previous_patch or "",
            "next_patch": self.next_patch_name(),
        }

    def render(self, template: str) -> str:
        try:
            return template.format(**self.template_values())
        except KeyError as exc:
            raise ConfigError(
                f"Unsupported template variable '{exc.args[0]}' in '{template}'."
            ) from exc


def _suffix_ordering_key(value: str | None) -> tuple[tuple[int, object], ...]:
    if value is None:
        return ()
    parts = re.findall(r"\d+|[A-Za-z]+|[^A-Za-z\d]+", value.lower())
    ordering: list[tuple[int, object]] = []
    for part in parts:
        if part.isdigit():
            ordering.append((1, int(part)))
            continue
        ordering.append((0, part))
    return tuple(ordering)
