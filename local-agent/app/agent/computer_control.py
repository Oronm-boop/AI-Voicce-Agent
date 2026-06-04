from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

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
}

APP_ALIASES = {
    "记事本": "notepad.exe",
    "notepad": "notepad.exe",
    "计算器": "calc.exe",
    "calculator": "calc.exe",
    "画图": "mspaint.exe",
    "资源管理器": "explorer.exe",
    "文件资源管理器": "explorer.exe",
    "explorer": "explorer.exe",
    "命令行": "cmd.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "浏览器": "msedge.exe",
    "edge": "msedge.exe",
    "chrome": "chrome.exe",
    "谷歌浏览器": "chrome.exe",
    "微信": "WeChat.exe",
    "wechat": "WeChat.exe",
}

WINDOWS_COMMON_APP_PATHS = {
    "chrome.exe": (
        r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
        r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    ),
    "msedge.exe": (
        r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
        r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    ),
    "WeChat.exe": (
        r"%ProgramFiles%\Tencent\WeChat\WeChat.exe",
        r"%ProgramFiles(x86)%\Tencent\WeChat\WeChat.exe",
        r"%LocalAppData%\Tencent\WeChat\WeChat.exe",
    ),
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

允许的工具：
- open_url: {"url": "https://example.com"}
- web_search: {"query": "搜索关键词"}
- open_app: {"target": "应用名、exe 名或绝对路径"}
- type_text: {"text": "要输入的文字"}
- press_key: {"key": "enter"}
- hotkey: {"keys": ["ctrl", "l"]}
- click: {"x": 100, "y": 200}，没有坐标时可省略 x/y 表示点击当前位置
- scroll: {"clicks": -5}，负数向下，正数向上
- wait: {"seconds": 1}

只返回这个 JSON 结构：
{
  "should_control": true,
  "summary": "一句话说明要做什么",
  "requires_confirmation": false,
  "confirmation_reason": "",
  "actions": [{"tool": "open_url", "args": {"url": "https://example.com"}}]
}

如果用户只是询问“怎么做”，should_control 为 false。
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
            summary=f"我理解这是电脑控制请求，但本地工具规划失败：{exc}",
        )


def execute_computer_control_plan(
    plan: ComputerControlPlan,
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
                message="没有生成可执行的本地电脑动作。",
            )
        ]

    results: list[ComputerActionResult] = []
    for action in plan.actions[:8]:
        results.append(_execute_action(action))
    return results


def build_computer_control_reply(
    plan: ComputerControlPlan,
    results: list[ComputerActionResult],
) -> str:
    if plan.requires_confirmation:
        reason = plan.confirmation_reason or "这个操作需要你先明确确认。"
        return f"需要确认：{reason}"

    if not results:
        return plan.summary or "没有可执行的本地电脑动作。"

    lines = [plan.summary or "已执行本地电脑控制指令。"]
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
        return ComputerControlPlan(
            summary=f"打开浏览器搜索：{search_query}",
            actions=[ComputerAction(tool="web_search", args={"query": search_query})],
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
        summary="执行本地电脑控制指令。",
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
        summary=str(payload.get("summary") or "执行本地电脑控制指令。"),
        actions=actions,
        requires_confirmation=bool(payload.get("requires_confirmation", False)),
        confirmation_reason=str(payload.get("confirmation_reason") or ""),
    )


def _execute_action(action: ComputerAction) -> ComputerActionResult:
    try:
        if action.tool == "open_url":
            return _open_url(str(action.args.get("url", "")))
        if action.tool == "web_search":
            return _web_search(str(action.args.get("query", "")))
        if action.tool == "open_app":
            return _open_app(str(action.args.get("target", "")))
        if action.tool == "type_text":
            return _type_text(str(action.args.get("text", "")))
        if action.tool == "press_key":
            return _press_key(str(action.args.get("key", "")))
        if action.tool == "hotkey":
            return _hotkey(action.args.get("keys", []))
        if action.tool == "click":
            return _click(action.args)
        if action.tool == "scroll":
            return _scroll(action.args)
        if action.tool == "wait":
            return _wait(action.args)
    except Exception as exc:  # noqa: BLE001 - surface tool failures to the chat UI.
        return ComputerActionResult(
            tool=action.tool,
            status="error",
            message=str(exc) or exc.__class__.__name__,
        )

    return ComputerActionResult(
        tool=action.tool,
        status="error",
        message=f"未知本地工具：{action.tool}",
    )


def _open_url(raw_url: str) -> ComputerActionResult:
    url = _normalize_url(raw_url)
    if not url:
        return ComputerActionResult(
            tool="open_url",
            status="error",
            message="缺少要打开的网址。",
        )

    opened = webbrowser.open(url, new=2)
    status = "success" if opened else "error"
    message = f"已打开网页 {url}" if opened else f"无法打开网页 {url}"
    return ComputerActionResult(
        tool="open_url",
        status=status,
        message=message,
        details={"url": url},
    )


def _web_search(query: str) -> ComputerActionResult:
    query = query.strip()
    if not query:
        return ComputerActionResult(
            tool="web_search",
            status="error",
            message="缺少搜索关键词。",
        )

    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    opened = webbrowser.open(url, new=2)
    status = "success" if opened else "error"
    message = f"已打开浏览器搜索：{query}" if opened else f"无法打开搜索：{query}"
    return ComputerActionResult(
        tool="web_search",
        status=status,
        message=message,
        details={"query": query, "url": url},
    )


def _open_app(target: str) -> ComputerActionResult:
    target = _trim_target(target)
    if not target:
        return ComputerActionResult(
            tool="open_app",
            status="error",
            message="缺少要打开的应用名称。",
        )

    command = _resolve_app_command(target)
    if command is None:
        return ComputerActionResult(
            tool="open_app",
            status="error",
            message=f"未找到应用：{target}。请说常见应用名、exe 名或完整路径。",
        )

    if isinstance(command, Path):
        _start_path(command)
    else:
        subprocess.Popen(  # noqa: S603 - local desktop tool invocation by request.
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )

    return ComputerActionResult(
        tool="open_app",
        status="success",
        message=f"已启动应用：{target}",
        details={"target": target},
    )


def _type_text(text: str) -> ComputerActionResult:
    text = text.strip()
    if not text:
        return ComputerActionResult(
            tool="type_text",
            status="error",
            message="缺少要输入的文字。",
        )

    pyautogui = _load_pyautogui()
    try:
        import pyperclip

        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
    except ImportError:
        pyautogui.write(text, interval=0.01)

    return ComputerActionResult(
        tool="type_text",
        status="success",
        message="已向当前焦点窗口输入文字。",
        details={"text_length": len(text)},
    )


def _press_key(key: str) -> ComputerActionResult:
    normalized_key = _normalize_key(key)
    if not normalized_key:
        return ComputerActionResult(
            tool="press_key",
            status="error",
            message="缺少要按下的按键。",
        )

    pyautogui = _load_pyautogui()
    pyautogui.press(normalized_key)
    return ComputerActionResult(
        tool="press_key",
        status="success",
        message=f"已按下按键：{normalized_key}",
        details={"key": normalized_key},
    )


def _hotkey(keys: Any) -> ComputerActionResult:
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

    pyautogui = _load_pyautogui()
    pyautogui.hotkey(*normalized_keys)
    return ComputerActionResult(
        tool="hotkey",
        status="success",
        message=f"已按下快捷键：{'+'.join(normalized_keys)}",
        details={"keys": normalized_keys},
    )


def _click(args: dict[str, Any]) -> ComputerActionResult:
    pyautogui = _load_pyautogui()
    x = args.get("x")
    y = args.get("y")
    if x is None or y is None:
        pyautogui.click()
        message = "已点击当前鼠标位置。"
        details: dict[str, Any] = {}
    else:
        pyautogui.click(int(x), int(y))
        message = f"已点击坐标：{int(x)}, {int(y)}"
        details = {"x": int(x), "y": int(y)}

    return ComputerActionResult(
        tool="click",
        status="success",
        message=message,
        details=details,
    )


def _scroll(args: dict[str, Any]) -> ComputerActionResult:
    clicks = int(args.get("clicks", -5))
    pyautogui = _load_pyautogui()
    pyautogui.scroll(clicks)
    direction = "向上" if clicks > 0 else "向下"
    return ComputerActionResult(
        tool="scroll",
        status="success",
        message=f"已{direction}滚动。",
        details={"clicks": clicks},
    )


def _wait(args: dict[str, Any]) -> ComputerActionResult:
    seconds = max(0.0, min(float(args.get("seconds", 1)), 30.0))
    time.sleep(seconds)
    return ComputerActionResult(
        tool="wait",
        status="success",
        message=f"已等待 {seconds:.1f} 秒。",
        details={"seconds": seconds},
    )


def _resolve_app_command(target: str) -> list[str] | Path | None:
    direct_path = Path(target).expanduser()
    if direct_path.exists():
        return direct_path

    alias = _lookup_alias(target, APP_ALIASES)
    executable = alias or target

    common_path = _find_common_windows_app(executable)
    if common_path is not None:
        return common_path

    found = shutil.which(executable) or shutil.which(f"{executable}.exe")
    if found:
        return [found]

    if alias and os.name == "nt":
        return [alias]

    return None


def _start_path(path: Path) -> None:
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
        return
    subprocess.Popen(  # noqa: S603 - local desktop tool invocation by request.
        [str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def _find_common_windows_app(executable: str) -> Path | None:
    if os.name != "nt":
        return None

    for raw_path in WINDOWS_COMMON_APP_PATHS.get(executable, ()):
        path = Path(os.path.expandvars(raw_path))
        if path.exists():
            return path
    return None


def _load_pyautogui():
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError(
            "需要安装 pyautogui 才能控制鼠标和键盘，请在 local-agent 中安装依赖。"
        ) from exc

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    return pyautogui


def _clean_command_text(text: str) -> str:
    return text.strip().strip("。.!！ ")


def _extract_search_query(text: str) -> str:
    match = re.search(
        r"(?:打开.{0,8}(?:浏览器|网页).{0,8})?(?:搜索|搜一下|查一下|百度一下|帮我搜|帮我查)(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return _trim_target(match.group(1))


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

    match = re.search(r"(\d{1,5})\s*[,， ]\s*(\d{1,5})", text)
    if not match:
        return {}
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
