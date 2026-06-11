from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus, urlparse

from app.agent.windows_mcp_client import WindowsMcpClient, windows_mcp_result_text
from app.config import Settings
from app.models.ollama_client import OllamaClient, OllamaClientError
from app.models.schemas import ChatMessage, ChatRequest, ComputerActionResult


ALLOWED_TOOLS = {
    "open_url",
    "web_search",
    "open_app",
    "type_text",
    "press_key",
    "hotkey",
    "click",
    "scroll",
    "wait",
    "screenshot",
    "snapshot",
    "wait_for",
}

CONTROL_KEYWORDS = (
    "打开",
    "启动",
    "访问",
    "进入",
    "搜索",
    "搜一下",
    "查一下",
    "点击",
    "点一下",
    "输入",
    "打字",
    "按下",
    "快捷键",
    "滚动",
    "截图",
    "屏幕",
    "观察",
    "查看屏幕",
    "等待",
    "浏览器",
    "网页",
    "app",
    "应用",
    "软件",
    "open ",
    "launch ",
    "search ",
    "click",
    "type ",
    "press ",
)

SENSITIVE_KEYWORDS = (
    "删除",
    "卸载",
    "格式化",
    "付款",
    "支付",
    "转账",
    "下单",
    "购买",
    "发邮件",
    "发送邮件",
    "发送消息",
    "发消息",
    "提交",
)

ANSWER_REQUEST_KEYWORDS = (
    "告诉我",
    "回答我",
    "跟我说",
    "给我说",
    "说一下",
    "汇报",
    "结果",
    "答案",
    "是什么",
    "是多少",
    "怎么样",
    "天气",
    "温度",
    "今天",
    "现在",
    "最新",
)

BROWSER_LOOKUP_KEYWORDS = (
    "浏览器",
    "网页",
    "搜索",
    "搜一下",
    "查一下",
    "查询",
    "百度",
    "谷歌",
    "bing",
    "必应",
)

WEBSITE_ALIASES = {
    "百度": "https://www.baidu.com",
    "谷歌": "https://www.google.com",
    "google": "https://www.google.com",
    "bing": "https://www.bing.com",
    "必应": "https://www.bing.com",
    "github": "https://github.com",
    "b站": "https://www.bilibili.com",
    "哔哩哔哩": "https://www.bilibili.com",
    "知乎": "https://www.zhihu.com",
    "淘宝": "https://www.taobao.com",
    "京东": "https://www.jd.com",
    "邮箱": "https://mail.qq.com",
    "outlook": "https://outlook.live.com/mail",
    "爱奇艺": "https://www.iqiyi.com",
    "iqiyi": "https://www.iqiyi.com",
}



KEY_ALIASES = {
    "回车": "enter",
    "确认": "enter",
    "空格": "space",
    "删除": "delete",
    "退格": "backspace",
    "退出": "esc",
    "取消": "esc",
    "上": "up",
    "下": "down",
    "左": "left",
    "右": "right",
    "控制": "ctrl",
    "win": "win",
    "windows": "win",
    "command": "command",
    "cmd": "command",
}

CONTROL_SYSTEM_PROMPT = """
你是本地电脑控制指令规划器。请把用户的一句话转换成 JSON，不要输出解释文字。

允许的工具全部由 Windows-MCP 执行：
- open_url: {"url": "https://example.com"}
- web_search: {"query": "搜索关键词"}
- open_app: {"target": "应用名称"}，target 直接填写用户说的应用名（中文名或英文名均可，如"微信"、"记事本"、"Chrome"），不要自行转换为 exe 文件名
- type_text: {"text": "要输入的文字"}，可选 x/y 或 label 表示输入到指定元素
- press_key: {"key": "enter"}
- hotkey: {"keys": ["ctrl", "l"]}
- click: {"x": 100, "y": 200} 或 {"label": 3}，点击必须有坐标或 Snapshot 返回的 label
- scroll: {"clicks": -5}，负数向下，正数向上，可选 x/y 或 label
- wait: {"seconds": 1}
- screenshot: {"use_annotation": false}
- snapshot: {"use_vision": false, "use_dom": false}
- wait_for: {"condition": "text_exists", "text": "目标文本", "timeout": 10}

只返回这个 JSON 结构：
{
  "should_control": true,
  "summary": "一句话说明要做什么",
  "requires_confirmation": false,
  "confirmation_reason": "",
  "actions": [{"tool": "open_url", "args": {"url": "https://example.com"}}]
}

如果用户只是询问“怎么做”，should_control 为 false。
如果用户要求打开网页、搜索或查询后“告诉我/回答我/汇报结果”，
动作必须包含读取结果所需的 wait 和 snapshot。
支付、下单、删除、卸载、发送邮件/消息等敏感或不可逆操作不要执行，
requires_confirmation 设为 true，并在 confirmation_reason 里说明需要用户确认。
""".strip()


@dataclass(frozen=True)
class ComputerAction:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ComputerControlPlan:
    summary: str
    actions: list[ComputerAction] = field(default_factory=list)
    requires_confirmation: bool = False
    confirmation_reason: str = ""


def should_control_computer(request: ChatRequest) -> bool:
    text = _latest_user_text(request)
    if not text:
        return False

    lowered = text.lower()
    asks_how_to = re.search(r"(怎么|如何|怎样).*(打开|启动|点击|输入|搜索|控制)", text)
    asks_agent_to_act = any(token in text for token in ("帮我", "请你", "替我", "给我"))
    if asks_how_to and not asks_agent_to_act:
        return False

    return any(keyword in lowered or keyword in text for keyword in CONTROL_KEYWORDS)


async def plan_computer_control(
    client: OllamaClient,
    request: ChatRequest,
) -> ComputerControlPlan:
    heuristic_plan = _build_heuristic_plan(request)
    if heuristic_plan is not None:
        return heuristic_plan

    text = _latest_user_text(request)
    if not text:
        return ComputerControlPlan(summary="没有识别到可执行的本地控制指令。")

    try:
        planning_request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=CONTROL_SYSTEM_PROMPT),
                ChatMessage(role="user", content=text),
            ],
            temperature=0.1,
            max_tokens=1024,
            think=False,
        )
        response = await client.chat(planning_request)
        return _parse_control_plan(response.reply)
    except (OllamaClientError, ValueError) as exc:
        return ComputerControlPlan(
            summary=f"我理解这是电脑控制请求，但 Windows-MCP 工具规划失败：{exc}",
        )


def execute_computer_control_plan(
    plan: ComputerControlPlan,
    settings: Settings | None = None,
) -> list[ComputerActionResult]:
    if plan.requires_confirmation:
        return [
            ComputerActionResult(
                tool="confirm",
                status="confirm_required",
                message=plan.confirmation_reason or "这个操作需要你先明确确认。",
            )
        ]

    if not plan.actions:
        return [
            ComputerActionResult(
                tool="none",
                status="skipped",
                message="没有生成可执行的 Windows-MCP 电脑动作。",
            )
        ]

    settings = settings or Settings()
    client = _create_windows_mcp_client(settings)
    results: list[ComputerActionResult] = []
    try:
        for action in plan.actions[:8]:
            results.append(_execute_action(action, client))
        return results
    finally:
        client.close()


def build_computer_control_reply(
    plan: ComputerControlPlan,
    results: list[ComputerActionResult],
) -> str:
    if plan.requires_confirmation:
        reason = plan.confirmation_reason or "这个操作需要你先明确确认。"
        return f"需要确认：{reason}"

    if not results:
        return plan.summary or "没有可执行的 Windows-MCP 电脑动作。"

    lines = [plan.summary or "已执行 Windows-MCP 电脑控制指令。"]
    for result in results:
        prefix = {
            "success": "完成",
            "error": "失败",
            "skipped": "跳过",
            "confirm_required": "需要确认",
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


def _build_heuristic_plan(request: ChatRequest) -> ComputerControlPlan | None:
    text = _clean_command_text(_latest_user_text(request))
    if not text:
        return None

    if any(keyword in text for keyword in SENSITIVE_KEYWORDS):
        return ComputerControlPlan(
            summary="这个指令涉及敏感操作。",
            requires_confirmation=True,
            confirmation_reason="涉及删除、支付、下单或发送内容等敏感动作，请明确确认后再执行。",
        )

    actions: list[ComputerAction] = []

    search_query = _extract_search_query(text)
    if search_query:
        include_snapshot = _should_collect_lookup_snapshot(text)
        return ComputerControlPlan(
            summary=(
                f"打开浏览器搜索并读取结果：{search_query}"
                if include_snapshot
                else f"打开浏览器搜索：{search_query}"
            ),
            actions=_browser_lookup_actions(search_query, include_snapshot=include_snapshot),
        )

    information_query = _extract_information_query(text)
    if information_query and _requests_browser_lookup(text):
        return ComputerControlPlan(
            summary=f"打开浏览器查询并读取结果：{information_query}",
            actions=_browser_lookup_actions(information_query, include_snapshot=True),
        )

    open_target = _extract_open_target(text)
    if open_target:
        url = _target_to_url(open_target)
        if url:
            actions.append(ComputerAction(tool="open_url", args={"url": url}))
        else:
            actions.append(ComputerAction(tool="open_app", args={"target": open_target}))

    type_text = _extract_type_text(text)
    if type_text:
        actions.append(ComputerAction(tool="type_text", args={"text": type_text}))

    hotkey = _extract_hotkey(text)
    if hotkey:
        actions.append(ComputerAction(tool="hotkey", args={"keys": hotkey}))

    press_key = _extract_press_key(text)
    if press_key and not hotkey:
        actions.append(ComputerAction(tool="press_key", args={"key": press_key}))

    click_args = _extract_click_args(text)
    if click_args is not None:
        actions.append(ComputerAction(tool="click", args=click_args))

    scroll_clicks = _extract_scroll_clicks(text)
    if scroll_clicks is not None:
        actions.append(ComputerAction(tool="scroll", args={"clicks": scroll_clicks}))

    if not actions:
        return None

    return ComputerControlPlan(
        summary="执行 Windows-MCP 电脑控制指令。",
        actions=actions,
    )


def _parse_control_plan(reply: str) -> ComputerControlPlan:
    start = reply.find("{")
    end = reply.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("模型没有返回有效 JSON。")

    payload = json.loads(reply[start : end + 1])
    if not payload.get("should_control", False):
        return ComputerControlPlan(summary="这不是需要执行的电脑控制请求。")

    actions: list[ComputerAction] = []
    for item in payload.get("actions", []):
        tool = str(item.get("tool", "")).strip()
        args = item.get("args", {})
        if tool not in ALLOWED_TOOLS or not isinstance(args, dict):
            continue
        actions.append(ComputerAction(tool=tool, args=args))

    return ComputerControlPlan(
        summary=str(payload.get("summary") or "执行 Windows-MCP 电脑控制指令。"),
        actions=actions,
        requires_confirmation=bool(payload.get("requires_confirmation", False)),
        confirmation_reason=str(payload.get("confirmation_reason") or ""),
    )


def _execute_action(action: ComputerAction, client: WindowsMcpClient) -> ComputerActionResult:
    try:
        return _execute_mcp_action(action, client)
    except Exception as exc:  # noqa: BLE001 - surface tool failures to the chat UI.
        return ComputerActionResult(
            tool=action.tool,
            status="error",
            message=str(exc) or exc.__class__.__name__,
        )


def _execute_mcp_action(
    action: ComputerAction,
    client: WindowsMcpClient,
) -> ComputerActionResult:
    if action.tool == "open_url":
        return _mcp_open_url(client, str(action.args.get("url", "")))
    if action.tool == "web_search":
        return _mcp_web_search(client, str(action.args.get("query", "")))
    if action.tool == "open_app":
        return _mcp_open_app(client, str(action.args.get("target", "")))
    if action.tool == "type_text":
        return _mcp_type_text(client, action.args)
    if action.tool == "press_key":
        return _mcp_press_key(client, str(action.args.get("key", "")))
    if action.tool == "hotkey":
        return _mcp_hotkey(client, action.args.get("keys", []))
    if action.tool == "click":
        return _mcp_click(client, action.args)
    if action.tool == "scroll":
        return _mcp_scroll(client, action.args)
    if action.tool == "wait":
        return _mcp_wait(client, action.args)
    if action.tool == "screenshot":
        return _mcp_screenshot(client, action.args)
    if action.tool == "snapshot":
        return _mcp_snapshot(client, action.args)
    if action.tool == "wait_for":
        return _mcp_wait_for(client, action.args)

    return ComputerActionResult(
        tool=action.tool,
        status="error",
        message=f"Windows-MCP 后端不支持工具：{action.tool}",
    )


def _create_windows_mcp_client(settings: Settings) -> WindowsMcpClient:
    return WindowsMcpClient(
        settings.windows_mcp_url,
        auth_token=settings.windows_mcp_auth_token,
        timeout_seconds=settings.windows_mcp_timeout_seconds,
    )


def _mcp_open_url(client: WindowsMcpClient, raw_url: str) -> ComputerActionResult:
    url = _normalize_url(raw_url)
    if not url:
        return ComputerActionResult(
            tool="open_url",
            status="error",
            message="缺少要打开的网址。",
        )

    _mcp_open_url_sequence(client, url)
    return ComputerActionResult(
        tool="open_url",
        status="success",
        message=f"已通过 Windows-MCP 打开网页 {url}",
        details={"url": url, "backend": "windows-mcp"},
    )


def _mcp_web_search(client: WindowsMcpClient, query: str) -> ComputerActionResult:
    query = query.strip()
    if not query:
        return ComputerActionResult(
            tool="web_search",
            status="error",
            message="缺少搜索关键词。",
        )

    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    _mcp_open_url_sequence(client, url)
    return ComputerActionResult(
        tool="web_search",
        status="success",
        message=f"已通过 Windows-MCP 打开浏览器搜索：{query}",
        details={"query": query, "url": url, "backend": "windows-mcp"},
    )


def _mcp_open_url_sequence(client: WindowsMcpClient, url: str) -> None:
    _mcp_call(client, "Shortcut", {"shortcut": "win+r"})
    _mcp_call(client, "Wait", {"duration": 1})
    _mcp_call(client, "Clipboard", {"mode": "set", "text": url})
    _mcp_call(client, "Shortcut", {"shortcut": "ctrl+v"})
    _mcp_call(client, "Shortcut", {"shortcut": "enter"})


def _mcp_open_app(client: WindowsMcpClient, target: str) -> ComputerActionResult:
    target = _trim_target(target)
    if not target:
        return ComputerActionResult(
            tool="open_app",
            status="error",
            message="缺少要打开的应用名称。",
        )

    response_text = _mcp_call(client, "App", {"mode": "launch", "name": target})
    lowered_response = response_text.lower()
    status = "error" if "not found" in lowered_response else "success"
    message = (
        f"Windows-MCP 未找到应用：{target}。"
        if status == "error"
        else f"已通过 Windows-MCP 启动应用：{target}"
    )
    return ComputerActionResult(
        tool="open_app",
        status=status,
        message=message,
        details={
            "target": target,
            "mcp_response": response_text,
            "backend": "windows-mcp",
        },
    )


def _mcp_type_text(client: WindowsMcpClient, args: dict[str, Any]) -> ComputerActionResult:
    text = str(args.get("text", "")).strip()
    if not text:
        return ComputerActionResult(
            tool="type_text",
            status="error",
            message="缺少要输入的文字。",
        )

    loc = _mcp_loc_from_args(args)
    label = _mcp_label_from_args(args)
    if loc is not None or label is not None:
        tool_args: dict[str, Any] = {"text": text}
        if loc is not None:
            tool_args["loc"] = loc
        if label is not None:
            tool_args["label"] = label
        _mcp_call(client, "Type", tool_args)
    else:
        _mcp_call(client, "Clipboard", {"mode": "set", "text": text})
        _mcp_call(client, "Shortcut", {"shortcut": "ctrl+v"})

    return ComputerActionResult(
        tool="type_text",
        status="success",
        message="已通过 Windows-MCP 向当前焦点窗口输入文字。",
        details={"text_length": len(text), "backend": "windows-mcp"},
    )


def _mcp_press_key(client: WindowsMcpClient, key: str) -> ComputerActionResult:
    normalized_key = _normalize_key(key)
    if not normalized_key:
        return ComputerActionResult(
            tool="press_key",
            status="error",
            message="缺少要按下的按键。",
        )

    shortcut = _mcp_shortcut_name(normalized_key)
    _mcp_call(client, "Shortcut", {"shortcut": shortcut})
    return ComputerActionResult(
        tool="press_key",
        status="success",
        message=f"已通过 Windows-MCP 按下按键：{normalized_key}",
        details={"key": normalized_key, "backend": "windows-mcp"},
    )


def _mcp_hotkey(client: WindowsMcpClient, keys: Any) -> ComputerActionResult:
    if isinstance(keys, str):
        raw_keys = re.split(r"[+\s,，]+", keys)
    elif isinstance(keys, list):
        raw_keys = [str(key) for key in keys]
    else:
        raw_keys = []

    normalized_keys = [_normalize_key(key) for key in raw_keys]
    normalized_keys = [key for key in normalized_keys if key]
    if not normalized_keys:
        return ComputerActionResult(
            tool="hotkey",
            status="error",
            message="缺少快捷键组合。",
        )

    shortcut = "+".join(_mcp_shortcut_name(key) for key in normalized_keys)
    _mcp_call(client, "Shortcut", {"shortcut": shortcut})
    return ComputerActionResult(
        tool="hotkey",
        status="success",
        message=f"已通过 Windows-MCP 按下快捷键：{'+'.join(normalized_keys)}",
        details={"keys": normalized_keys, "backend": "windows-mcp"},
    )


def _mcp_click(client: WindowsMcpClient, args: dict[str, Any]) -> ComputerActionResult:
    loc = _mcp_loc_from_args(args)
    label = _mcp_label_from_args(args)
    if loc is None and label is None:
        return ComputerActionResult(
            tool="click",
            status="error",
            message="Windows-MCP 点击需要坐标 x/y 或 Snapshot 返回的元素 label。",
        )

    button = str(args.get("button") or "left").lower()
    if button not in {"left", "right", "middle"}:
        button = "left"
    clicks = max(0, min(int(args.get("clicks", 1)), 2))
    tool_args: dict[str, Any] = {"button": button, "clicks": clicks}
    if loc is not None:
        tool_args["loc"] = loc
    if label is not None:
        tool_args["label"] = label

    _mcp_call(client, "Click", tool_args)
    detail_target: dict[str, Any] = (
        {"label": label} if label is not None else {"x": loc[0], "y": loc[1]}
    )
    return ComputerActionResult(
        tool="click",
        status="success",
        message=(
            f"已通过 Windows-MCP 点击元素 label={label}。"
            if label is not None
            else f"已通过 Windows-MCP 点击坐标：{loc[0]}, {loc[1]}"
        ),
        details={**detail_target, "button": button, "clicks": clicks, "backend": "windows-mcp"},
    )


def _mcp_scroll(client: WindowsMcpClient, args: dict[str, Any]) -> ComputerActionResult:
    clicks = int(args.get("clicks", -5))
    loc = _mcp_loc_from_args(args)
    label = _mcp_label_from_args(args)
    direction = str(args.get("direction") or "").lower()
    if direction not in {"up", "down", "left", "right"}:
        direction = "up" if clicks > 0 else "down"
    scroll_type = "horizontal" if direction in {"left", "right"} else "vertical"

    tool_args: dict[str, Any] = {
        "type": scroll_type,
        "direction": direction,
        "wheel_times": max(1, abs(clicks)),
    }
    if loc is not None:
        tool_args["loc"] = loc
    if label is not None:
        tool_args["label"] = label

    _mcp_call(client, "Scroll", tool_args)
    direction_text = {
        "up": "向上",
        "down": "向下",
        "left": "向左",
        "right": "向右",
    }[direction]
    return ComputerActionResult(
        tool="scroll",
        status="success",
        message=f"已通过 Windows-MCP {direction_text}滚动。",
        details={"clicks": clicks, "direction": direction, "backend": "windows-mcp"},
    )


def _mcp_wait(client: WindowsMcpClient, args: dict[str, Any]) -> ComputerActionResult:
    seconds = max(0.0, min(float(args.get("seconds", 1)), 30.0))
    if seconds > 0:
        _mcp_call(client, "Wait", {"duration": max(1, int(round(seconds)))})
    return ComputerActionResult(
        tool="wait",
        status="success",
        message=f"已通过 Windows-MCP 等待 {seconds:.1f} 秒。",
        details={"seconds": seconds, "backend": "windows-mcp"},
    )


def _mcp_screenshot(client: WindowsMcpClient, args: dict[str, Any]) -> ComputerActionResult:
    tool_args = {
        "use_annotation": _mcp_bool_arg(args.get("use_annotation", False)),
    }
    response_text = _mcp_call(client, "Screenshot", tool_args)
    return ComputerActionResult(
        tool="screenshot",
        status="success",
        message=response_text or "已通过 Windows-MCP 截取屏幕。",
        details={"backend": "windows-mcp"},
    )


def _mcp_snapshot(client: WindowsMcpClient, args: dict[str, Any]) -> ComputerActionResult:
    tool_args = {
        "use_vision": _mcp_bool_arg(args.get("use_vision", False)),
        "use_dom": _mcp_bool_arg(args.get("use_dom", False)),
        "use_annotation": _mcp_bool_arg(args.get("use_annotation", True)),
        "use_ui_tree": _mcp_bool_arg(args.get("use_ui_tree", True)),
    }
    response_text = _mcp_call(client, "Snapshot", tool_args, max_length=6000)
    return ComputerActionResult(
        tool="snapshot",
        status="success",
        message=_compact_text(response_text) or "已通过 Windows-MCP 获取屏幕状态。",
        details={"backend": "windows-mcp", "snapshot_text": response_text},
    )


def _mcp_wait_for(client: WindowsMcpClient, args: dict[str, Any]) -> ComputerActionResult:
    condition = str(args.get("condition") or "text_exists")
    tool_args: dict[str, Any] = {
        "condition": condition,
        "timeout": max(0.1, min(float(args.get("timeout", 10)), 120.0)),
        "interval": max(0.1, min(float(args.get("interval", 0.25)), 5.0)),
        "use_dom": _mcp_bool_arg(args.get("use_dom", False)),
    }
    if args.get("text") is not None:
        tool_args["text"] = str(args.get("text"))
    if args.get("window_name") is not None:
        tool_args["window_name"] = str(args.get("window_name"))

    response_text = _mcp_call(client, "WaitFor", tool_args)
    return ComputerActionResult(
        tool="wait_for",
        status="success",
        message=response_text or "Windows-MCP 等待条件已满足。",
        details={"condition": condition, "backend": "windows-mcp"},
    )


def _mcp_call(
    client: WindowsMcpClient,
    tool: str,
    args: dict[str, Any],
    *,
    max_length: int = 1200,
) -> str:
    result = client.call_tool(tool, args)
    return windows_mcp_result_text(result, max_length=max_length)


def _compact_text(text: str, *, max_length: int = 1200) -> str:
    value = text.strip()
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}..."


def _target_to_mcp_app_name(target: str) -> str:
    """直接透传 LLM 给出的应用名，不做任何别名映射。"""
    return target.strip()


def _mcp_loc_from_args(args: dict[str, Any]) -> list[int] | None:
    loc = args.get("loc")
    if isinstance(loc, list) and len(loc) == 2:
        return [int(loc[0]), int(loc[1])]

    x = args.get("x")
    y = args.get("y")
    if x is None or y is None:
        return None
    return [int(x), int(y)]


def _mcp_label_from_args(args: dict[str, Any]) -> int | None:
    label = args.get("label")
    if label is None:
        return None
    return int(label)


def _mcp_bool_arg(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _mcp_shortcut_name(key: str) -> str:
    aliases = {
        "win": "win",
        "ctrl": "ctrl",
        "control": "ctrl",
        "esc": "esc",
        "escape": "esc",
        "enter": "enter",
        "space": "space",
        "delete": "delete",
        "backspace": "backspace",
        "up": "up",
        "down": "down",
        "left": "left",
        "right": "right",
    }
    return aliases.get(key.lower(), key.lower())


def _clean_command_text(text: str) -> str:
    return text.strip().strip("。.!！ ")


def _extract_search_query(text: str) -> str:
    match = re.search(
        r"(?:打开.{0,8}(?:浏览器|网页).{0,8})?(?:搜索|搜一下|查一下|查询|百度一下|帮我搜|帮我查)(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return _trim_target(_strip_answer_tail(match.group(1)))


def _extract_information_query(text: str) -> str:
    match = re.search(
        r"(?:告诉我|回答我|跟我说|给我说|说一下|看一下|看看)(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""

    query = _trim_target(match.group(1))
    if query in {"结果", "答案", "查询结果", "搜索结果"}:
        return ""
    return query


def _strip_answer_tail(text: str) -> str:
    return re.split(
        r"(?:并|然后|再)?(?:告诉我|回答我|跟我说|给我说|说一下|汇报|输出)(?:结果|答案)?",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]


def _browser_lookup_actions(query: str, *, include_snapshot: bool) -> list[ComputerAction]:
    actions = [ComputerAction(tool="web_search", args={"query": query})]
    if include_snapshot:
        actions.extend(
            [
                ComputerAction(tool="wait", args={"seconds": 3}),
                ComputerAction(
                    tool="snapshot",
                    args={"use_dom": True, "use_ui_tree": True},
                ),
            ]
        )
    return actions


def _should_collect_lookup_snapshot(text: str) -> bool:
    return any(keyword in text for keyword in ANSWER_REQUEST_KEYWORDS)


def _requests_browser_lookup(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered or keyword in text for keyword in BROWSER_LOOKUP_KEYWORDS)


def _extract_open_target(text: str) -> str:
    match = re.search(r"(?:打开|启动|访问|进入)(.+)", text, flags=re.IGNORECASE)
    if not match:
        return ""

    target = match.group(1)
    target = re.split(r"(?:然后|并且|并|再|，|,|。|；|;)", target, maxsplit=1)[0]
    return _trim_target(target)


def _extract_type_text(text: str) -> str:
    match = re.search(r"(?:输入|打字|写入)(.+)", text, flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip().strip("“”\"'。.!！ ")


def _extract_hotkey(text: str) -> list[str]:
    match = re.search(
        r"(?:快捷键|按下|按)([a-zA-Z0-9+\s,，]+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match or "+" not in match.group(1):
        return []
    return [
        _normalize_key(key)
        for key in re.split(r"[+\s,，]+", match.group(1))
        if _normalize_key(key)
    ]


def _extract_press_key(text: str) -> str:
    match = re.search(r"(?:按下|按)(回车|确认|空格|删除|退格|退出|取消|上|下|左|右|[a-zA-Z0-9])", text)
    if not match:
        return ""
    return _normalize_key(match.group(1))


def _extract_click_args(text: str) -> dict[str, Any] | None:
    if "点击" not in text and "点一下" not in text:
        return None

    label_match = re.search(r"label\s*=?\s*(\d{1,5})", text, flags=re.IGNORECASE)
    if label_match:
        return {"label": int(label_match.group(1))}

    match = re.search(r"(\d{1,5})\s*[,， ]\s*(\d{1,5})", text)
    if not match:
        return None
    return {"x": int(match.group(1)), "y": int(match.group(2))}


def _extract_scroll_clicks(text: str) -> int | None:
    if "滚动" not in text:
        return None
    amount_match = re.search(r"(\d{1,2})", text)
    amount = int(amount_match.group(1)) if amount_match else 5
    if "上" in text:
        return amount
    return -amount


def _target_to_url(target: str) -> str:
    alias_url = _lookup_alias(target, WEBSITE_ALIASES)
    if alias_url:
        return alias_url
    if _is_probable_url(target):
        return _normalize_url(target)
    return ""


def _lookup_alias(target: str, aliases: dict[str, str]) -> str:
    normalized_target = target.lower().replace(" ", "")
    for alias, value in aliases.items():
        normalized_alias = alias.lower().replace(" ", "")
        if normalized_alias == normalized_target or normalized_alias in normalized_target:
            return value
    return ""


def _is_probable_url(value: str) -> bool:
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return True
    return bool(re.search(r"([\w-]+\.)+[a-zA-Z]{2,}(/.*)?$", value))


def _normalize_url(value: str) -> str:
    value = _trim_target(value)
    if not value:
        return ""
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
        value = f"https://{value}"
    return value


def _trim_target(value: str) -> str:
    value = value.strip().strip("“”\"'。.!！ ")
    value = re.sub(r"^(一下|这个|那个|网页|网站|应用|软件)\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*(一下|这个|那个|网页|网站|应用|软件)$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^app\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+app$", "", value, flags=re.IGNORECASE)
    return value.strip()


def _normalize_key(key: str) -> str:
    normalized = key.strip().lower()
    if not normalized:
        return ""
    return KEY_ALIASES.get(normalized, normalized)


# ---------------------------------------------------------------------------
# Tavily web search intent detection
# ---------------------------------------------------------------------------

WEB_SEARCH_KEYWORDS = (
    "搜索",
    "搜一下",
    "查一下",
    "查询",
    "帮我查",
    "帮我搜",
    "百度一下",
    "告诉我",
    "回答我",
    "天气",
    "温度",
    "最新",
    "新闻",
    "是什么",
    "是多少",
    "怎么样",
    "多少钱",
    "股票",
    "汇率",
    "比分",
    "时间",
    "日期",
    "search ",
    "what is",
    "how to",
    "latest",
)

EXPLICIT_BROWSER_KEYWORDS = (
    "浏览器",
    "网页",
    "打开浏览器",
    "在浏览器",
    "用浏览器",
)


def should_web_search(request: "ChatRequest") -> bool:
    """Return True when the user's request should be answered via Tavily web search.

    The request is routed to Tavily when it contains search/query keywords
    but does NOT explicitly ask to open a browser.
    """
    text = _latest_user_text(request)
    if not text:
        return False

    lowered = text.lower()

    # If user explicitly wants a browser, let computer_control handle it.
    if any(keyword in lowered for keyword in EXPLICIT_BROWSER_KEYWORDS):
        return False

    # "How to" style questions without "help me" are informational, not actionable.
    asks_how_to = re.search(r"(怎么|如何|怎样).*(打开|启动|点击|输入|控制)", text)
    asks_agent_to_act = any(token in text for token in ("帮我", "请你", "替我", "给我"))
    if asks_how_to and not asks_agent_to_act:
        return False

    return any(keyword in lowered or keyword in text for keyword in WEB_SEARCH_KEYWORDS)


def extract_search_query_for_tavily(request: "ChatRequest") -> str:
    """Extract the core search query string from the user's request."""
    text = _clean_command_text(_latest_user_text(request))
    if not text:
        return ""

    # Try explicit search pattern first: "搜索XXX", "查一下XXX"
    match = re.search(
        r"(?:帮我)?(?:搜索|搜一下|查一下|查询|百度一下|帮我搜|帮我查)\s*(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return _trim_target(_strip_answer_tail(match.group(1)))

    # Try "告诉我/回答我 XXX" pattern
    match = re.search(
        r"(?:告诉我|回答我|跟我说|给我说|说一下)\s*(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        query = _trim_target(match.group(1))
        if query not in {"结果", "答案", "查询结果", "搜索结果"}:
            return query

    # Fallback: use the full text as the query (strip common prefixes)
    cleaned = re.sub(
        r"^(请你?|帮我|替我|给我)\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return _trim_target(cleaned) or text

