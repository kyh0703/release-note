from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
from typing import Any

import requests


@dataclass
class RecordedCall:
    method: str
    url: str
    kwargs: dict[str, Any]


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        text: str = "",
        json_data: Any = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self._json_data = json_data

    def json(self) -> Any:
        if self._json_data is None:
            raise ValueError("No JSON payload configured.")
        return self._json_data

    @property
    def content(self) -> bytes:
        if self.text:
            return self.text.encode("utf-8")
        if self._json_data is not None:
            return json.dumps(self._json_data, ensure_ascii=False).encode("utf-8")
        return b""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class ScriptedSession:
    def __init__(self, *responses: FakeResponse) -> None:
        self._responses = deque(responses)
        self.calls: list[RecordedCall] = []
        self.auth: tuple[str, str] | None = None

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        return self._record("GET", url, kwargs)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        return self._record("POST", url, kwargs)

    def put(self, url: str, **kwargs: Any) -> FakeResponse:
        return self._record("PUT", url, kwargs)

    def _record(self, method: str, url: str, kwargs: dict[str, Any]) -> FakeResponse:
        self.calls.append(RecordedCall(method=method, url=url, kwargs=kwargs))
        if not self._responses:
            raise AssertionError("No scripted response left for request.")
        return self._responses.popleft()
