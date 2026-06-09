from __future__ import annotations

import itertools
import json
from typing import Any

import httpx


MCP_PROTOCOL_VERSION = "2025-06-18"


class WindowsMcpError(RuntimeError):
    """Base error raised when Windows-MCP cannot complete a request."""


class WindowsMcpConnectionError(WindowsMcpError):
    """Raised when the Windows-MCP HTTP endpoint cannot be reached."""


class WindowsMcpProtocolError(WindowsMcpError):
    """Raised when the MCP server returns a JSON-RPC protocol error."""


class WindowsMcpToolError(WindowsMcpError):
    """Raised when a Windows-MCP tool reports an execution error."""


class WindowsMcpClient:
    def __init__(
        self,
        url: str,
        *,
        auth_token: str = "",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.url = _normalize_mcp_url(url)
        self.auth_token = auth_token.strip()
        self.protocol_version = MCP_PROTOCOL_VERSION
        self.session_id = ""
        self._initialized = False
        self._ids = itertools.count(1)
        self._client = httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def list_tools(self) -> list[dict[str, Any]]:
        self._ensure_initialized()
        response = self._request("tools/list", {})
        result = _require_result(response)
        return list(result.get("tools", []))

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        self._ensure_initialized()
        response = self._request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )
        result = _require_result(response)
        if result.get("isError"):
            raise WindowsMcpToolError(_tool_result_text(result) or f"{name} 执行失败。")
        return result

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        response = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "local-agent-runtime",
                    "version": "0.1.0",
                },
            },
            include_session=False,
        )
        result = _require_result(response)
        protocol_version = result.get("protocolVersion")
        if isinstance(protocol_version, str) and protocol_version:
            self.protocol_version = protocol_version

        self._notification("notifications/initialized")
        self._initialized = True

    def _notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        try:
            response = self._client.post(
                self.url,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise WindowsMcpConnectionError(_connection_error_message(self.url, exc)) from exc

    def _request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        include_session: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": next(self._ids),
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        try:
            response = self._client.post(
                self.url,
                headers=self._headers(include_session=include_session),
                json=payload,
            )
            if response.status_code == 404 and self.session_id:
                self.session_id = ""
                self._initialized = False
                return self._request(method, params, include_session=False)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise WindowsMcpConnectionError(_connection_error_message(self.url, exc)) from exc

        session_id = response.headers.get("mcp-session-id")
        if session_id:
            self.session_id = session_id

        return self._decode_response(response)

    def _headers(self, *, include_session: bool = True) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": self.protocol_version,
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if include_session and self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def _decode_response(self, response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "").lower()
        if "text/event-stream" in content_type:
            return _decode_sse_json_rpc(response.text)

        payload = response.json()
        if not isinstance(payload, dict):
            raise WindowsMcpProtocolError("Windows-MCP 返回了无效的 JSON-RPC 响应。")
        return payload


def _normalize_mcp_url(url: str) -> str:
    value = (url or "http://127.0.0.1:8000/mcp").strip()
    if not value:
        value = "http://127.0.0.1:8000/mcp"
    return value.rstrip("/")


def _require_result(response: dict[str, Any]) -> dict[str, Any]:
    error = response.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "Windows-MCP 返回了协议错误。")
        raise WindowsMcpProtocolError(message)

    result = response.get("result")
    if not isinstance(result, dict):
        raise WindowsMcpProtocolError("Windows-MCP 响应中缺少 result。")
    return result


def _decode_sse_json_rpc(text: str) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    data_lines: list[str] = []

    for line in text.splitlines():
        if not line.strip():
            _append_sse_data(candidates, data_lines)
            data_lines = []
            continue
        if line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").lstrip())

    _append_sse_data(candidates, data_lines)

    for candidate in reversed(candidates):
        if "result" in candidate or "error" in candidate:
            return candidate

    raise WindowsMcpProtocolError("Windows-MCP SSE 响应中没有 JSON-RPC result。")


def _append_sse_data(candidates: list[dict[str, Any]], data_lines: list[str]) -> None:
    if not data_lines:
        return
    payload = "\n".join(data_lines).strip()
    if not payload:
        return
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return
    if isinstance(decoded, dict):
        candidates.append(decoded)


def _tool_result_text(result: dict[str, Any], *, max_length: int = 1200) -> str:
    parts: list[str] = []
    content = result.get("content", [])
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            elif item.get("type") == "image":
                parts.append("[image]")
            elif item.get("type") == "audio":
                parts.append("[audio]")

    text = "\n".join(part for part in parts if part).strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


def _connection_error_message(url: str, exc: httpx.HTTPError) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        detail = response.text.strip()
        if detail:
            return f"无法调用 Windows-MCP（{response.status_code}）：{detail}"
        return f"无法调用 Windows-MCP（{response.status_code}）。"
    return (
        f"无法连接 Windows-MCP：{exc}. 请先启动 "
        f"`uvx windows-mcp serve --transport streamable-http --host 127.0.0.1 --port 8000`，"
        f"并确认 MCP 地址为 {url}。"
    )


def windows_mcp_result_text(result: dict[str, Any], *, max_length: int = 1200) -> str:
    return _tool_result_text(result, max_length=max_length)
