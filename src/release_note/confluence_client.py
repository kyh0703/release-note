from __future__ import annotations

from typing import Any
from xml.etree import ElementTree

import requests

from .config import ConfluenceConfig
from .errors import ApiError, NotFoundError
from .models import ConfluencePage


class ConfluenceClient:
    def __init__(
        self,
        config: ConfluenceConfig,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        self.session.auth = (config.username, config.password)
        self._request_id = 0

    def get_page(self, title: str) -> ConfluencePage | None:
        try:
            payload = self._call("getPage", self.config.space_key, title)
        except NotFoundError:
            return None
        if payload is None:
            return None
        page_id = payload.get("id")
        if page_id is not None:
            try:
                payload = {
                    **payload,
                    "content": self._fetch_storage_content(str(page_id)),
                }
            except ApiError:
                pass
        return ConfluencePage.from_rpc(payload)

    def store_page(self, page: ConfluencePage) -> ConfluencePage:
        try:
            payload = self._call("storePage", page.to_rpc_payload())
            return ConfluencePage.from_rpc(payload)
        except ApiError as exc:
            if "VersionMismatchException" not in str(exc):
                raise
            current_page = self.get_page(page.title)
            if current_page is None:
                raise
            retry_page = current_page.clone_for_update(content=page.content)
            payload = self._call("storePage", retry_page.to_rpc_payload())
            return ConfluencePage.from_rpc(payload)

    def list_pages(self) -> list[ConfluencePage]:
        payload = self._call("getPages", self.config.space_key)
        return [ConfluencePage.from_rpc(item) for item in payload]

    def move_page(self, source_page_id: str, target_page_id: str, position: str) -> None:
        self._call("movePage", source_page_id, target_page_id, position)

    def remove_page(self, page_id: str) -> None:
        self._call("removePage", page_id)

    def _fetch_storage_content(self, page_id: str) -> str:
        try:
            response = self.session.get(
                self._url(f"/wiki/rest/prototype/1/content/{page_id}"),
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ApiError(
                f"Confluence prototype content request failed for page '{page_id}': {exc}"
            ) from exc
        try:
            payload = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as exc:
            raise ApiError("Confluence prototype content returned invalid XML.") from exc
        return payload.findtext("body") or ""

    def _call(self, method: str, *params: Any) -> Any:
        self._request_id += 1
        try:
            response = self.session.post(
                self._url("/wiki/rpc/json-rpc/confluenceservice-v2"),
                json={
                    "jsonrpc": "2.0",
                    "id": self._request_id,
                    "method": method,
                    "params": list(params),
                },
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ApiError(f"Confluence RPC '{method}' request failed: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiError("Confluence returned invalid JSON-RPC data.") from exc
        if payload.get("error"):
            error = payload["error"]
            message = str(error.get("message", error))
            if (
                "NoSuchPage" in message
                or "Could not find page" in message
                or "You're not allowed to view that page, or it does not exist" in message
            ):
                raise NotFoundError(message)
            raise ApiError(f"Confluence RPC '{method}' failed: {message}")
        return payload.get("result")

    def _url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}{path}"
