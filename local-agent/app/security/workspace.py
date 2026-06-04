from pathlib import Path

from app.config import Settings


class WorkspaceAccessError(ValueError):
    """Raised when a file path is outside the selected workspace."""


class WorkspaceNotSelectedError(ValueError):
    """Raised when a file operation needs a workspace but none is selected."""


def normalize_workspace_path(raw_path: str) -> str:
    raw_path = raw_path.strip()
    if not raw_path:
        return ""

    try:
        path = Path(raw_path).expanduser().resolve(strict=True)
    except OSError as exc:
        raise ValueError("工作空间必须是一个已存在的文件夹。") from exc
    if not path.is_dir():
        raise ValueError("工作空间必须是一个已存在的文件夹。")
    return str(path)


def get_workspace_root(settings: Settings) -> Path | None:
    workspace_path = settings.workspace_path.strip()
    if not workspace_path:
        return None
    return Path(normalize_workspace_path(workspace_path))


def resolve_workspace_scoped_path(settings: Settings, raw_path: str | Path) -> Path:
    workspace_root = get_workspace_root(settings)
    if workspace_root is None:
        raise WorkspaceNotSelectedError("请先选择工作空间，再进行文件操作。")

    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        target = workspace_root / target

    resolved_target = target.resolve(strict=False)
    try:
        resolved_target.relative_to(workspace_root)
    except ValueError as exc:
        raise WorkspaceAccessError("文件路径超出当前工作空间范围。") from exc

    return resolved_target
