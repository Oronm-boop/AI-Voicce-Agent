from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    "delete_path",
    "create_directory",
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

MAX_CONTEXT_FILE_BYTES = 80_000
MAX_CONTEXT_CHARS = 24_000
MAX_ACTIONS = 8

FILE_CONTROL_SYSTEM_PROMPT = """
你是本地工作空间文件操作规划器。请把用户的一句话转换成 JSON，不要输出解释文字。

所有文件操作都只允许在用户已经选择的工作空间内执行。路径可以是相对路径；
如果用户给了绝对路径，也只能表示工作空间内的路径。不要访问工作空间外的文件。

允许的动作：
- write_file: {"path": "relative/path.ext", "content": "完整文件内容", "overwrite": true}
- append_file: {"path": "relative/path.ext", "content": "要追加的内容"}
- replace_in_file: {"path": "relative/path.ext", "old_text": "原文片段", "new_text": "替换文本", "replace_all": false}
- delete_path: {"path": "relative/path.ext", "recursive": false}
- create_directory: {"path": "relative/folder"}

规则：
- 用户要求新建、生成、实现、开发、补全代码并写入文件时，用 write_file，content 必须是完整可保存的代码文件内容。
- 用户要求修改、修复、优化、重构指定代码文件时，优先读取上下文后用 write_file 返回修改后的完整文件内容。
- write_file 用于改写已有文件时，必须保留用户未要求改变的代码，不要用省略号、占位符或“保持不变”等文字代替真实代码。
- 用户要求在已有文件末尾增加内容时，用 append_file。
- 只有用户要求非常小的精确文本替换，并且可以从上下文确定原文片段时，才用 replace_in_file。
- 用户明确要求删除、移除、删掉文件或目录时，才使用 delete_path。
- 删除目录时，只有用户明确说删除文件夹/目录或递归删除，recursive 才能为 true。
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

    results: list[FileActionResult] = []
    for action in plan.actions[:MAX_ACTIONS]:
        results.append(_execute_action(settings, action))
    return results


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

    path = _first_probable_path(text)
    if not path:
        return None

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

    directory_match = re.search(r"(?:新建|创建).{0,6}(?:文件夹|目录)", text)
    if directory_match:
        return FileOperationPlan(
            summary=f"创建工作空间目录：{path}",
            actions=[FileAction(action="create_directory", args={"path": path})],
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


def _execute_action(settings: Settings, action: FileAction) -> FileActionResult:
    try:
        if action.action == "write_file":
            return _write_file(settings, action.args)
        if action.action == "append_file":
            return _append_file(settings, action.args)
        if action.action == "replace_in_file":
            return _replace_in_file(settings, action.args)
        if action.action == "delete_path":
            return _delete_path(settings, action.args)
        if action.action == "create_directory":
            return _create_directory(settings, action.args)
    except (OSError, WorkspaceAccessError, WorkspaceNotSelectedError, ValueError) as exc:
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


def _write_file(settings: Settings, args: dict[str, Any]) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    content = _normalize_file_content(str(args.get("content", "")))
    overwrite = bool(args.get("overwrite", True))
    if path.exists() and not overwrite:
        return FileActionResult(
            action="write_file",
            status="error",
            message=f"文件已存在，未覆盖：{_display_path(settings, path)}",
            path=_display_path(settings, path),
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")
    return FileActionResult(
        action="write_file",
        status="success",
        message=f"已写入文件：{_display_path(settings, path)}",
        path=_display_path(settings, path),
        details={"bytes": len(content.encode("utf-8"))},
    )


def _append_file(settings: Settings, args: dict[str, Any]) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    content = _normalize_file_content(str(args.get("content", "")))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as file:
        file.write(content)
    return FileActionResult(
        action="append_file",
        status="success",
        message=f"已追加内容到文件：{_display_path(settings, path)}",
        path=_display_path(settings, path),
        details={"bytes": len(content.encode("utf-8"))},
    )


def _replace_in_file(settings: Settings, args: dict[str, Any]) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    old_text = str(args.get("old_text", ""))
    new_text = str(args.get("new_text", ""))
    replace_all = bool(args.get("replace_all", False))
    if not old_text:
        raise ValueError("缺少要替换的原文片段。")
    if not path.exists() or not path.is_file():
        raise ValueError(f"文件不存在：{_display_path(settings, path)}")

    content = _read_text_file(path)
    count = content.count(old_text)
    if count == 0:
        return FileActionResult(
            action="replace_in_file",
            status="error",
            message=f"未在文件中找到要替换的内容：{_display_path(settings, path)}",
            path=_display_path(settings, path),
        )

    updated = content.replace(old_text, new_text) if replace_all else content.replace(old_text, new_text, 1)
    path.write_text(updated, encoding="utf-8", newline="")
    replaced_count = count if replace_all else 1
    return FileActionResult(
        action="replace_in_file",
        status="success",
        message=f"已修改文件：{_display_path(settings, path)}（替换 {replaced_count} 处）",
        path=_display_path(settings, path),
        details={"replacements": replaced_count},
    )


def _delete_path(settings: Settings, args: dict[str, Any]) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    recursive = bool(args.get("recursive", False))
    if not path.exists():
        return FileActionResult(
            action="delete_path",
            status="skipped",
            message=f"路径不存在，无需删除：{_display_path(settings, path)}",
            path=_display_path(settings, path),
        )

    if path.is_dir() and not path.is_symlink():
        if recursive:
            shutil.rmtree(path)
        else:
            path.rmdir()
    else:
        path.unlink()

    return FileActionResult(
        action="delete_path",
        status="success",
        message=f"已删除：{_display_path(settings, path)}",
        path=_display_path(settings, path),
    )


def _create_directory(settings: Settings, args: dict[str, Any]) -> FileActionResult:
    path = _resolve_action_path(settings, args)
    path.mkdir(parents=True, exist_ok=True)
    return FileActionResult(
        action="create_directory",
        status="success",
        message=f"已创建目录：{_display_path(settings, path)}",
        path=_display_path(settings, path),
    )


def _resolve_action_path(settings: Settings, args: dict[str, Any]) -> Path:
    raw_path = str(args.get("path", "")).strip()
    if not raw_path:
        raise ValueError("缺少文件路径。")
    return resolve_workspace_scoped_path(settings, raw_path)


def _normalize_file_content(content: str) -> str:
    stripped = content.strip()
    match = re.fullmatch(r"```[\w+-]*\s*\n(.*)\n```", stripped, flags=re.DOTALL)
    if match:
        return match.group(1)
    return content


def _read_text_file(path: Path) -> str:
    if path.stat().st_size > MAX_CONTEXT_FILE_BYTES:
        raise ValueError("文件过大，当前受管文件操作不会直接修改。")
    return path.read_text(encoding="utf-8")


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
    for raw_path in paths:
        try:
            path = resolve_workspace_scoped_path(settings, raw_path)
            if not path.exists() or not path.is_file():
                blocks.append(f"文件 {raw_path}：不存在。")
                continue
            if path.stat().st_size > MAX_CONTEXT_FILE_BYTES:
                blocks.append(f"文件 {raw_path}：文件过大，未读取内容。")
                continue
            content = path.read_text(encoding="utf-8")
            blocks.append(
                f"文件 {raw_path} 当前内容：\n```\n{content[:MAX_CONTEXT_CHARS]}\n```"
            )
        except (OSError, ValueError) as exc:
            blocks.append(f"文件 {raw_path}：无法读取上下文，原因：{exc}")

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

    for token in re.split(r"[\s，。；;：:、]+", text):
        candidate = token.strip().strip("`\"'“”()（）[]【】")
        if _looks_like_path(candidate):
            paths.append(candidate)

    deduped: list[str] = []
    for path in paths:
        if path not in deduped:
            deduped.append(path)
    return deduped


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
