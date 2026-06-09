from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.agent.windows_mcp_client import (
    WindowsMcpClient,
    WindowsMcpError,
    windows_mcp_result_text,
)
from app.config import Settings
from app.models.ollama_client import OllamaClient, OllamaClientError
from app.models.schemas import ChatMessage, ChatRequest, FileActionResult
from app.security.workspace import (
    WorkspaceAccessError,
    WorkspaceNotSelectedError,
    resolve_workspace_scoped_path,
)


ALLOWED_FILE_ACTIONS = {
    "write_file",
    "append_file",
    "replace_in_file",
    "clear_file",
    "delete_path",
    "create_directory",
    "read_file",
    "list_directory",
    "file_info",
}

FILE_KEYWORDS = (
    "文件",
    "文件夹",
    "目录",
    "代码",
    "脚本",
    "组件",
    "页面",
    "配置",
    "函数",
    "方法",
    "类",
    "接口",
    "模块",
    "workspace",
    "工作空间",
)

FILE_ACTION_KEYWORDS = (
    "新建",
    "新增",
    "创建",
    "生成",
    "实现",
    "开发",
    "补全",
    "写入",
    "保存",
    "修改",
    "更新",
    "调整",
    "改写",
    "改成",
    "替换",
    "修复",
    "优化",
    "重构",
    "增加",
    "加上",
    "追加",
    "删除",
    "移除",
    "删掉",
    "清空",
    "查看",
    "读取",
    "查询",
    "列出",
    "搜索",
)

PATH_SUFFIXES = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".vue",
    ".json",
    ".md",
    ".txt",
    ".css",
    ".less",
    ".html",
    ".yml",
    ".yaml",
    ".toml",
    ".env",
)

MAX_CONTEXT_CHARS = 24_000
MAX_ACTIONS = 8
DEFAULT_DIRECTORY_NAME = "新建文件夹"

FILE_CONTROL_SYSTEM_PROMPT = """
你是本地工作空间文件操作规划器。请把用户的一句话转换成 JSON，不要输出解释文字。

所有文件操作都只允许在用户已经选择的工作空间内执行。路径可以是相对路径；
如果用户给了绝对路径，也只能表示工作空间内的路径。不要访问工作空间外的文件。

允许的动作：
- write_file: {"path": "relative/path.ext", "content": "完整文件内容", "overwrite": true}
- append_file: {"path": "relative/path.ext", "content": "要追加的内容"}
- replace_in_file: {"path": "relative/path.ext", "old_text": "原文片段", "new_text": "替换文本", "replace_all": false}
- clear_file: {"path": "relative/path.ext"}
- delete_path: {"path": "relative/path.ext", "recursive": false}
- create_directory: {"path": "relative/folder"}
- read_file: {"path": "relative/path.ext"}
- list_directory: {"path": "relative/folder", "pattern": "*.txt", "recursive": false}
- file_info: {"path": "relative/path.ext"}

规则：
- 用户要求新建、生成、实现、开发、补全代码并写入文件时，用 write_file，content 必须是完整可保存的代码文件内容。
- 用户要求修改、修复、优化、重构指定代码文件时，优先读取上下文后用 write_file 返回修改后的完整文件内容。
- write_file 用于改写已有文件时，必须保留用户未要求改变的代码，不要用省略号、占位符或“保持不变”等文字代替真实代码。
- 用户要求在已有文件末尾增加内容时，用 append_file。
- 只有用户要求非常小的精确文本替换，并且可以从上下文确定原文片段时，才用 replace_in_file。
- 用户要求清空文件、删除文件内容、删掉文本内容时，用 clear_file，不要用 delete_path。
- 用户明确要求删除、移除、删掉文件或目录时，才使用 delete_path。
- 删除目录时，只有用户明确说删除文件夹/目录或递归删除，recursive 才能为 true。
- 用户要求查看、读取文件内容时，用 read_file。
- 用户要求列出、查看目录内容时，用 list_directory。
- 用户要求查询文件或目录信息、大小、修改时间时，用 file_info。
- 缺少路径或缺少必要内容时，不要编造路径，返回空 actions，并在 summary 说明缺少什么。
- JSON 必须有效；content 内的换行请作为 JSON 字符串换行转义，不要返回 Markdown 代码块。

只返回这个 JSON 结构：
{
  "should_edit_files": true,
  "summary": "一句话说明要做什么",
  "actions": [{"action": "write_file", "args": {"path": "example.txt", "content": "hello", "overwrite": true}}]
}
""".strip()


@dataclass(frozen=True)
class FileAction:
    action: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FileOperationPlan:
    summary: str
    actions: list[FileAction] = field(default_factory=list)


def should_control_files(request: ChatRequest) -> bool:
    text = _latest_user_text(request)
    if not text:
        return False

    if re.search(r"(怎么|如何|怎样).*(新建|创建|修改|删除|写入|替换).*文件", text):
        asks_agent_to_act = any(token in text for token in ("帮我", "请你", "替我", "给我"))
        if not asks_agent_to_act:
            return False

    lowered = text.lower()
    has_file_target = (
        any(keyword in text for keyword in FILE_KEYWORDS)
        or any(suffix in lowered for suffix in PATH_SUFFIXES)
        or "/" in text
        or "\\" in text
    )
    has_action = any(keyword in text for keyword in FILE_ACTION_KEYWORDS)
    if not has_file_target or not has_action:
        return False

    if ("赋予" in text or "能力" in text) and not _extract_probable_paths(text):
        return False

    return True


async def plan_file_operations(
    settings: Settings,
    client: OllamaClient,
    request: ChatRequest,
) -> FileOperationPlan:
    heuristic_plan = _build_heuristic_plan(request)
    if heuristic_plan is not None:
        return heuristic_plan

    text = _latest_user_text(request)
    if not text:
        return FileOperationPlan(summary="没有识别到文件操作指令。")

    context = _build_file_context(settings, request)
    conversation_context = _conversation_context(request)
    try:
        planning_request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=FILE_CONTROL_SYSTEM_PROMPT),
                ChatMessage(
                    role="user",
                    content=(
                        f"{context}\n\n"
                        f"最近对话上下文：\n{conversation_context}\n\n"
                        f"当前用户指令：{text}"
                    ),
                ),
            ],
            temperature=0.1,
            max_tokens=8192,
            think=False,
        )
        response = await client.chat(planning_request)
        return _parse_file_plan(response.reply)
    except (OllamaClientError, ValueError) as exc:
        return FileOperationPlan(summary=f"我理解这是文件操作请求，但规划失败：{exc}")


def execute_file_operation_plan(
    settings: Settings,
    plan: FileOperationPlan,
) -> list[FileActionResult]:
    if not plan.actions:
        return [
            FileActionResult(
                action="none",
                status="skipped",
                message=plan.summary or "没有生成可执行的文件动作。",
            )
        ]

    client = _create_windows_mcp_client(settings)
    results: list[FileActionResult] = []
    try:
        for action in plan.actions[:MAX_ACTIONS]:
            results.append(_execute_action(settings, client, action))
        return results
    finally:
        client.close()


def build_file_operation_reply(
    plan: FileOperationPlan,
    results: list[FileActionResult],
) -> str:
    if not results:
        return plan.summary or "没有可执行的文件动作。"

    lines = [plan.summary or "已处理工作空间文件操作。"]
    for result in results:
        prefix = {
            "success": "完成",
            "error": "失败",
            "skipped": "跳过",
        }.get(result.status, result.status)
        lines.append(f"{prefix}：{result.message}")
    return "\n".join(lines)


def _latest_user_text(request: ChatRequest) -> str:
    if request.prompt:
        return request.prompt.strip()

    for message in reversed(request.messages):
        if message.role == "user":
            return message.content.strip()

    return ""


def _build_heuristic_plan(request: ChatRequest) -> FileOperationPlan | None:
    text = _latest_user_text(request).strip()
    if not text:
        return None

    directory_match = re.search(r"(?:新建|创建).{0,12}(?:文件夹|目录)", text)
    if directory_match:
        path = _first_probable_path(text) or _extract_directory_name(text) or DEFAULT_DIRECTORY_NAME
        return FileOperationPlan(
            summary=f"创建工作空间目录：{path}",
            actions=[
                FileAction(
                    action="create_directory",
                    args={
                        "path": path,
                        "ensure_unique": path == DEFAULT_DIRECTORY_NAME,
                    },
                )
            ],
        )

    path = _first_probable_path(text)
    if not path:
        return None

    if _is_clear_file_content_request(text):
        return FileOperationPlan(
            summary=f"清空工作空间文件内容：{path}",
            actions=[FileAction(action="clear_file", args={"path": path})],
        )

    if any(keyword in text for keyword in ("删除", "移除", "删掉")):
        recursive = any(keyword in text for keyword in ("文件夹", "目录", "递归", "整个"))
        return FileOperationPlan(
            summary=f"删除工作空间内路径：{path}",
            actions=[
                FileAction(
                    action="delete_path",
                    args={"path": path, "recursive": recursive},
                )
            ],
        )

    if any(keyword in text for keyword in ("列出", "查看")) and any(
        keyword in text for keyword in ("目录", "文件夹")
    ):
        return FileOperationPlan(
            summary=f"列出工作空间目录内容：{path}",
            actions=[FileAction(action="list_directory", args={"path": path})],
        )

    if any(keyword in text for keyword in ("查看", "读取")) and any(
        keyword in text for keyword in ("内容", "文本", "文件")
    ):
        return FileOperationPlan(
            summary=f"读取工作空间文件内容：{path}",
            actions=[FileAction(action="read_file", args={"path": path})],
        )

    if any(keyword in text for keyword in ("查询", "查看")) and any(
        keyword in text for keyword in ("信息", "大小", "修改时间", "属性")
    ):
        return FileOperationPlan(
            summary=f"查询工作空间路径信息：{path}",
            actions=[FileAction(action="file_info", args={"path": path})],
        )

    append_content = _extract_content_after(
        text,
        ("追加内容是", "追加内容为", "末尾加上", "末尾添加"),
    )
    if append_content:
        return FileOperationPlan(
            summary=f"向工作空间文件追加内容：{path}",
            actions=[
                FileAction(
                    action="append_file",
                    args={"path": path, "content": append_content},
                )
            ],
        )

    replacement = _extract_replacement(text)
    if replacement:
        old_text, new_text = replacement
        return FileOperationPlan(
            summary=f"替换工作空间文件内容：{path}",
            actions=[
                FileAction(
                    action="replace_in_file",
                    args={
                        "path": path,
                        "old_text": old_text,
                        "new_text": new_text,
                        "replace_all": False,
                    },
                )
            ],
        )

    content = _extract_content_after(text, ("内容是", "内容为", "写入", "保存为"))
    if content and any(keyword in text for keyword in ("新建", "创建", "生成", "写入", "保存")):
        return FileOperationPlan(
            summary=f"写入工作空间文件：{path}",
            actions=[
                FileAction(
                    action="write_file",
                    args={"path": path, "content": content, "overwrite": True},
                )
            ],
        )

    return None


def _parse_file_plan(reply: str) -> FileOperationPlan:
    start = reply.find("{")
    end = reply.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("模型没有返回有效 JSON。")

    payload = json.loads(reply[start : end + 1])
    if not payload.get("should_edit_files", False):
        return FileOperationPlan(summary="这不是需要执行的工作空间文件操作。")

    actions: list[FileAction] = []
    for item in payload.get("actions", []):
        action = str(item.get("action", "")).strip()
        args = item.get("args", {})
        if action not in ALLOWED_FILE_ACTIONS or not isinstance(args, dict):
            continue
        actions.append(FileAction(action=action, args=args))

    return FileOperationPlan(
        summary=str(payload.get("summary") or "执行工作空间文件操作。"),
        actions=actions,
    )


def _execute_action(
    settings: Settings,
    client: WindowsMcpClient,
    action: FileAction,
) -> FileActionResult:
    try:
        if action.action == "write_file":
            return _write_file(settings, client, action.args)
        if action.action == "append_file":
            return _append_file(settings, client, action.args)
        if action.action == "replace_in_file":
            return _replace_in_file(settings, client, action.args)
        if action.action == "clear_file":
            return _clear_file(settings, client, action.args)
        if action.action == "delete_path":
            return _delete_path(settings, client, action.args)
        if action.action == "create_directory":
            return _create_directory(settings, client, action.args)
        if action.action == "read_file":
            return _read_file_action(settings, client, action.args)
        if action.action == "list_directory":
            return _list_directory(settings, client, action.args)
        if action.action == "file_info":
            return _file_info(settings, client, action.args)
    except (
        WindowsMcpError,
        WorkspaceAccessError,
        WorkspaceNotSelectedError,
        ValueError,
    ) as exc:
        return FileActionResult(
            action=action.action,
            status="error",
            message=str(exc) or exc.__class__.__name__,
            path=str(action.args.get("path", "")),
        )

    return FileActionResult(
        action=action.action,
        status="error",
        message=f"未知文件动作：{action.action}",
        path=str(action.args.get("path", "")),
    )


def _write_file(
    settings: Settings,
    client: WindowsMcpClient,
    args: dict[str, Any],
) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    content = _normalize_file_content(str(args.get("content", "")))
    overwrite = bool(args.get("overwrite", True))
    if not overwrite and _mcp_path_exists(client, path):
        return FileActionResult(
            action="write_file",
            status="error",
            message=f"文件已存在，未覆盖：{_display_path(settings, path)}",
            path=_display_path(settings, path),
        )

    _mcp_filesystem_call(
        client,
        {
            "mode": "write",
            "path": str(path),
            "content": content,
            "append": False,
            "encoding": "utf-8",
        },
    )
    return FileActionResult(
        action="write_file",
        status="success",
        message=f"已通过 Windows-MCP 写入文件：{_display_path(settings, path)}",
        path=_display_path(settings, path),
        details={"bytes": len(content.encode("utf-8"))},
    )


def _append_file(
    settings: Settings,
    client: WindowsMcpClient,
    args: dict[str, Any],
) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    content = _normalize_file_content(str(args.get("content", "")))
    _mcp_filesystem_call(
        client,
        {
            "mode": "write",
            "path": str(path),
            "content": content,
            "append": True,
            "encoding": "utf-8",
        },
    )
    return FileActionResult(
        action="append_file",
        status="success",
        message=f"已通过 Windows-MCP 追加内容到文件：{_display_path(settings, path)}",
        path=_display_path(settings, path),
        details={"bytes": len(content.encode("utf-8"))},
    )


def _replace_in_file(
    settings: Settings,
    client: WindowsMcpClient,
    args: dict[str, Any],
) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    old_text = str(args.get("old_text", ""))
    new_text = str(args.get("new_text", ""))
    replace_all = bool(args.get("replace_all", False))
    if not old_text:
        raise ValueError("缺少要替换的原文片段。")

    content = _read_file_via_mcp(client, path)
    count = content.count(old_text)
    if count == 0:
        return FileActionResult(
            action="replace_in_file",
            status="error",
            message=f"未在文件中找到要替换的内容：{_display_path(settings, path)}",
            path=_display_path(settings, path),
        )

    updated = (
        content.replace(old_text, new_text)
        if replace_all
        else content.replace(old_text, new_text, 1)
    )
    _mcp_filesystem_call(
        client,
        {
            "mode": "write",
            "path": str(path),
            "content": updated,
            "append": False,
            "encoding": "utf-8",
        },
    )
    replaced_count = count if replace_all else 1
    return FileActionResult(
        action="replace_in_file",
        status="success",
        message=f"已通过 Windows-MCP 修改文件：{_display_path(settings, path)}（替换 {replaced_count} 处）",
        path=_display_path(settings, path),
        details={"replacements": replaced_count},
    )


def _clear_file(
    settings: Settings,
    client: WindowsMcpClient,
    args: dict[str, Any],
) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    if not _mcp_path_exists(client, path):
        raise ValueError(f"文件不存在：{_display_path(settings, path)}")

    _mcp_filesystem_call(
        client,
        {
            "mode": "write",
            "path": str(path),
            "content": "",
            "append": False,
            "encoding": "utf-8",
        },
    )
    return FileActionResult(
        action="clear_file",
        status="success",
        message=f"已通过 Windows-MCP 清空文件内容：{_display_path(settings, path)}",
        path=_display_path(settings, path),
        details={"bytes": 0},
    )


def _delete_path(
    settings: Settings,
    client: WindowsMcpClient,
    args: dict[str, Any],
) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    recursive = bool(args.get("recursive", False))
    if not _mcp_path_exists(client, path):
        return FileActionResult(
            action="delete_path",
            status="skipped",
            message=f"路径不存在，无需删除：{_display_path(settings, path)}",
            path=_display_path(settings, path),
        )

    _mcp_filesystem_call(
        client,
        {
            "mode": "delete",
            "path": str(path),
            "recursive": recursive,
        },
    )
    return FileActionResult(
        action="delete_path",
        status="success",
        message=f"已通过 Windows-MCP 删除：{_display_path(settings, path)}",
        path=_display_path(settings, path),
    )


def _create_directory(
    settings: Settings,
    client: WindowsMcpClient,
    args: dict[str, Any],
) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    if bool(args.get("ensure_unique", False)):
        response = _mcp_powershell_call(
            client,
            (
                f"$base = {_ps_single_quote(str(path))}; "
                "$target = $base; "
                "$index = 2; "
                "while (Test-Path -LiteralPath $target) { "
                '$target = "$base $index"; '
                "$index++ "
                "} "
                "New-Item -ItemType Directory -LiteralPath $target -Force | Out-Null; "
                "Write-Output $target"
            ),
        )
        actual_path = _extract_powershell_response_path(response) or path
    else:
        _mcp_powershell_call(
            client,
            (
                "New-Item -ItemType Directory -Force "
                f"-LiteralPath {_ps_single_quote(str(path))} | Out-Null"
            ),
        )
        actual_path = path

    return FileActionResult(
        action="create_directory",
        status="success",
        message=f"已通过 Windows-MCP 创建目录：{_display_path(settings, actual_path)}",
        path=_display_path(settings, actual_path),
    )


def _read_file_action(
    settings: Settings,
    client: WindowsMcpClient,
    args: dict[str, Any],
) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    content = _read_file_via_mcp(client, path)
    display_path = _display_path(settings, path)
    return FileActionResult(
        action="read_file",
        status="success",
        message=f"已通过 Windows-MCP 读取文件：{display_path}\n{content[:MAX_CONTEXT_CHARS]}",
        path=display_path,
        details={"chars": len(content)},
    )


def _list_directory(
    settings: Settings,
    client: WindowsMcpClient,
    args: dict[str, Any],
) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    pattern = str(args.get("pattern") or "").strip() or None
    recursive = bool(args.get("recursive", False))
    response = _mcp_filesystem_call(
        client,
        {
            "mode": "list",
            "path": str(path),
            "pattern": pattern,
            "recursive": recursive,
            "show_hidden": bool(args.get("show_hidden", False)),
        },
        max_length=MAX_CONTEXT_CHARS,
    )
    display_path = _display_path(settings, path)
    return FileActionResult(
        action="list_directory",
        status="success",
        message=f"已通过 Windows-MCP 列出目录：{display_path}\n{response}",
        path=display_path,
        details={"recursive": recursive, "pattern": pattern or ""},
    )


def _file_info(
    settings: Settings,
    client: WindowsMcpClient,
    args: dict[str, Any],
) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    response = _mcp_filesystem_call(
        client,
        {
            "mode": "info",
            "path": str(path),
        },
        max_length=MAX_CONTEXT_CHARS,
    )
    display_path = _display_path(settings, path)
    return FileActionResult(
        action="file_info",
        status="success",
        message=f"已通过 Windows-MCP 查询路径信息：{display_path}\n{response}",
        path=display_path,
    )


def _create_windows_mcp_client(settings: Settings) -> WindowsMcpClient:
    return WindowsMcpClient(
        settings.windows_mcp_url,
        auth_token=settings.windows_mcp_auth_token,
        timeout_seconds=settings.windows_mcp_timeout_seconds,
    )


def _mcp_filesystem_call(
    client: WindowsMcpClient,
    args: dict[str, Any],
    *,
    max_length: int = 1200,
    raise_on_error: bool = True,
) -> str:
    result = client.call_tool("FileSystem", args)
    text = windows_mcp_result_text(result, max_length=max_length)
    if raise_on_error and _is_mcp_error_text(text):
        raise ValueError(text)
    return text


def _mcp_powershell_call(client: WindowsMcpClient, command: str) -> str:
    result = client.call_tool("PowerShell", {"command": command, "timeout": 30})
    text = windows_mcp_result_text(result)
    if "Status Code: 0" not in text:
        raise ValueError(text or "Windows-MCP PowerShell 执行失败。")
    return text


def _mcp_path_exists(client: WindowsMcpClient, path: Path) -> bool:
    response = _mcp_filesystem_call(
        client,
        {
            "mode": "info",
            "path": str(path),
        },
        raise_on_error=False,
    )
    normalized = response.strip().lower()
    if normalized.startswith("error: path not found"):
        return False
    if _is_mcp_error_text(response):
        raise ValueError(response)
    return True


def _extract_mcp_read_content(response: str) -> str:
    if _is_mcp_error_text(response):
        raise ValueError(response)
    if "\n" not in response:
        return ""
    return response.split("\n", 1)[1]


def _is_mcp_error_text(text: str) -> bool:
    return text.strip().lower().startswith("error")


def _ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _extract_powershell_response_path(response: str) -> Path | None:
    match = re.search(r"Response:\s*(.*?)\s*Status Code:\s*0", response, flags=re.DOTALL)
    if not match:
        return None
    value = match.group(1).strip()
    if not value:
        return None
    return Path(value.splitlines()[-1].strip())


def _resolve_action_path(settings: Settings, args: dict[str, Any]) -> Path:
    raw_path = _normalize_workspace_path_hint(str(args.get("path", "")).strip())
    if not raw_path:
        raise ValueError("缺少文件路径。")
    return resolve_workspace_scoped_path(settings, raw_path)


def _normalize_workspace_path_hint(raw_path: str) -> str:
    value = raw_path.strip().strip("`\"'“”")
    if not value:
        return value

    normalized = value.replace("\\", "/").lstrip("/")
    workspace_prefixes = (
        "当前工作空间/",
        "工作空间/",
        "当前工作区/",
        "工作区/",
        "workspace/",
    )
    lowered = normalized.lower()
    for prefix in workspace_prefixes:
        if lowered.startswith(prefix.lower()):
            return normalized[len(prefix) :].strip("/")
    return value


def _normalize_file_content(content: str) -> str:
    stripped = content.strip()
    match = re.fullmatch(r"```[\w+-]*\s*\n(.*)\n```", stripped, flags=re.DOTALL)
    if match:
        return match.group(1)
    return content


def _read_file_via_mcp(client: WindowsMcpClient, path: Path) -> str:
    response = _mcp_filesystem_call(
        client,
        {
            "mode": "read",
            "path": str(path),
            "encoding": "utf-8",
        },
        max_length=MAX_CONTEXT_CHARS + 4096,
    )
    return _extract_mcp_read_content(response)


def _display_path(settings: Settings, path: Path) -> str:
    try:
        root = resolve_workspace_scoped_path(settings, ".")
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _build_file_context(settings: Settings, request: ChatRequest) -> str:
    lookup_text = _request_text_for_path_lookup(request)
    paths = _extract_probable_paths(lookup_text)[:4]
    if not paths:
        return "已知文件上下文：无明确文件路径。"

    blocks = []
    client = _create_windows_mcp_client(settings)
    try:
        for raw_path in paths:
            try:
                path = resolve_workspace_scoped_path(settings, raw_path)
                content = _read_file_via_mcp(client, path)
                blocks.append(
                    f"文件 {raw_path} 当前内容：\n```\n{content[:MAX_CONTEXT_CHARS]}\n```"
                )
            except (WindowsMcpError, ValueError) as exc:
                blocks.append(f"文件 {raw_path}：无法通过 Windows-MCP 读取上下文，原因：{exc}")
    finally:
        client.close()

    return "已知文件上下文：\n" + "\n\n".join(blocks)


def _request_text_for_path_lookup(request: ChatRequest) -> str:
    parts = []
    for message in request.messages[-8:]:
        if message.role in ("user", "assistant"):
            parts.append(message.content)
    if request.prompt:
        parts.append(request.prompt)
    return "\n".join(parts)


def _conversation_context(request: ChatRequest) -> str:
    lines = []
    for message in request.messages[-6:]:
        role = "用户" if message.role == "user" else "助手"
        content = message.content.strip()
        if content:
            lines.append(f"{role}: {content[:3000]}")
    if request.prompt:
        lines.append(f"用户: {request.prompt.strip()[:3000]}")
    return "\n".join(lines) or "无。"


def _extract_probable_paths(text: str) -> list[str]:
    paths: list[str] = []

    for match in re.finditer(r"[`\"'“”]([^`\"'“”]+)[`\"'“”]", text):
        candidate = match.group(1).strip()
        if _looks_like_path(candidate):
            paths.append(candidate)

    suffix_pattern = "|".join(re.escape(suffix.lstrip(".")) for suffix in PATH_SUFFIXES)
    embedded_path_pattern = rf"[A-Za-z0-9_.\-\\/]+\.({suffix_pattern})"
    for match in re.finditer(embedded_path_pattern, text, flags=re.IGNORECASE):
        candidate = match.group(0).strip()
        if _looks_like_path(candidate):
            paths.append(candidate)

    for token in re.split(r"[\s，。；;：:、]+", text):
        candidate = token.strip().strip("`\"'“”()（）[]【】")
        if _looks_like_path(candidate):
            paths.append(candidate)

    deduped: list[str] = []
    for path in paths:
        if path not in deduped:
            deduped.append(path)
    return deduped


def _is_clear_file_content_request(text: str) -> bool:
    if "清空" in text:
        return True
    has_content_target = any(keyword in text for keyword in ("内容", "文本", "文字"))
    has_delete_action = any(keyword in text for keyword in ("删除", "移除", "删掉", "清除"))
    return has_content_target and has_delete_action


def _first_probable_path(text: str) -> str:
    paths = _extract_probable_paths(text)
    return paths[0] if paths else ""


def _looks_like_path(value: str) -> bool:
    lowered = value.lower()
    if lowered.startswith(("http://", "https://")):
        return False
    if "/" in value or "\\" in value:
        return True
    return any(lowered.endswith(suffix) for suffix in PATH_SUFFIXES)


def _extract_content_after(text: str, markers: tuple[str, ...]) -> str:
    for marker in markers:
        index = text.find(marker)
        if index >= 0:
            return text[index + len(marker) :].strip().strip("：: \n\r\t")
    return ""


def _extract_directory_name(text: str) -> str:
    patterns = (
        r"(?:叫|名为|名称为|命名为)\s*[`\"'“”]?([^`\"'“”，。；;]+)[`\"'“”]?\s*(?:的)?(?:文件夹|目录)?",
        r"(?:新建|创建)\s*(?:一个|1个)?\s*([^，。；;\s]+?)\s*(?:文件夹|目录)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = match.group(1).strip().strip("`\"'“”")
        candidate = re.sub(r"^(新的?|一个|1个)", "", candidate).strip()
        if candidate and candidate not in {"文件夹", "目录", "工作空间", "工作区"}:
            return candidate
    return ""


def _extract_replacement(text: str) -> tuple[str, str] | None:
    match = re.search(
        r"(?:把|将)\s*[`\"'“”](.+?)[`\"'“”]\s*(?:替换为|改成|改为)\s*[`\"'“”](.+?)[`\"'“”]",
        text,
    )
    if not match:
        return None
    old_text = match.group(1).strip()
    new_text = match.group(2).strip()
    if not old_text:
        return None
    return old_text, new_text
