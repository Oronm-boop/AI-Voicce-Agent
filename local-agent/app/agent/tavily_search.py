"""Tavily web search client.

Calls the Tavily Search API (https://api.tavily.com/search) via httpx
and returns structured search results that can be fed to the LLM as
context for answering user queries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


@dataclass(frozen=True)
class TavilyResult:
    """A single search result returned by Tavily."""

    title: str
    url: str
    content: str
    score: float = 0.0


@dataclass(frozen=True)
class TavilySearchResponse:
    """Structured response from a Tavily search request."""

    query: str
    results: list[TavilyResult] = field(default_factory=list)
    answer: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and len(self.results) > 0


class TavilySearchError(Exception):
    """Raised when the Tavily API returns an error."""


async def tavily_search(
    query: str,
    *,
    api_key: str,
    search_depth: str = "basic",
    max_results: int = 5,
    include_answer: bool = True,
    timeout_seconds: float = 15.0,
) -> TavilySearchResponse:
    """Execute a search query against the Tavily API.

    Parameters
    ----------
    query:
        The search query string.
    api_key:
        Tavily API key.
    search_depth:
        ``"basic"`` for fast results or ``"advanced"`` for deeper search.
    max_results:
        Maximum number of results to return (1–10).
    include_answer:
        Whether Tavily should generate a short answer summary.
    timeout_seconds:
        HTTP request timeout.

    Returns
    -------
    TavilySearchResponse
        Structured search response with results and optional answer.
    """
    if not api_key:
        return TavilySearchResponse(
            query=query,
            error="Tavily API Key 未配置，无法执行联网搜索。",
        )

    if not query.strip():
        return TavilySearchResponse(
            query=query,
            error="搜索查询不能为空。",
        )

    payload: dict[str, Any] = {
        "query": query.strip(),
        "search_depth": search_depth,
        "max_results": min(max(1, max_results), 10),
        "include_answer": include_answer,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                TAVILY_SEARCH_URL,
                json={"api_key": api_key, **payload},
                headers={"Content-Type": "application/json"},
            )

        if response.status_code != 200:
            error_detail = _extract_error_detail(response)
            logger.warning(
                "Tavily API returned %d: %s", response.status_code, error_detail,
            )
            return TavilySearchResponse(
                query=query,
                error=f"Tavily API 请求失败 (HTTP {response.status_code}): {error_detail}",
            )

        data = response.json()
        return _parse_response(query, data)

    except httpx.TimeoutException:
        logger.warning("Tavily API request timed out after %.1fs", timeout_seconds)
        return TavilySearchResponse(
            query=query,
            error=f"Tavily API 请求超时（{timeout_seconds:.0f}秒）。",
        )
    except httpx.HTTPError as exc:
        logger.warning("Tavily API HTTP error: %s", exc)
        return TavilySearchResponse(
            query=query,
            error=f"Tavily API 网络错误：{exc}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error calling Tavily API")
        return TavilySearchResponse(
            query=query,
            error=f"调用 Tavily API 时发生未预期错误：{exc}",
        )


def format_tavily_results(
    search_response: TavilySearchResponse,
    *,
    max_content_length: int = 500,
) -> str:
    """Format Tavily search results into a readable context string for the LLM.

    Parameters
    ----------
    search_response:
        The response from ``tavily_search()``.
    max_content_length:
        Maximum characters per result's content field.

    Returns
    -------
    str
        Formatted search results ready to be inserted into LLM context.
    """
    if search_response.error:
        return f"联网搜索失败：{search_response.error}"

    if not search_response.results:
        return f"联网搜索 \"{search_response.query}\" 未找到相关结果。"

    lines: list[str] = [f"联网搜索 \"{search_response.query}\" 的结果：\n"]

    if search_response.answer:
        lines.append(f"摘要回答：{search_response.answer}\n")

    for idx, result in enumerate(search_response.results, start=1):
        content = result.content
        if len(content) > max_content_length:
            content = f"{content[:max_content_length]}..."
        lines.append(f"{idx}. **{result.title}**")
        lines.append(f"   来源：{result.url}")
        lines.append(f"   {content}\n")

    return "\n".join(lines)


def _parse_response(query: str, data: dict[str, Any]) -> TavilySearchResponse:
    """Parse the raw JSON response from Tavily into a structured object."""
    results: list[TavilyResult] = []
    for item in data.get("results", []):
        results.append(
            TavilyResult(
                title=str(item.get("title", "")),
                url=str(item.get("url", "")),
                content=str(item.get("content", "")),
                score=float(item.get("score", 0.0)),
            )
        )

    return TavilySearchResponse(
        query=query,
        results=results,
        answer=str(data.get("answer", "") or ""),
    )


def _extract_error_detail(response: httpx.Response) -> str:
    """Try to extract a human-readable error message from a Tavily error response."""
    try:
        data = response.json()
        if isinstance(data, dict):
            return str(data.get("detail") or data.get("message") or data.get("error") or data)
    except Exception:  # noqa: BLE001
        pass
    return response.text[:200] if response.text else "Unknown error"
