import argparse
import os

import uvicorn

from app.main import app


def _default_host() -> str:
    return (
        os.getenv("LOCAL_AGENT_HOST")
        or os.getenv("AGENT_HOST")
        or "127.0.0.1"
    )


def _default_port() -> int:
    raw = os.getenv("LOCAL_AGENT_PORT") or os.getenv("AGENT_PORT") or "8099"
    try:
        value = int(raw)
    except ValueError:
        return 8099
    return value if value > 0 else 8099


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local-agent FastAPI runtime.")
    parser.add_argument("--host", default=_default_host())
    parser.add_argument("--port", type=int, default=_default_port())
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOCAL_AGENT_LOG_LEVEL") or "info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=False,
        workers=1,
    )


if __name__ == "__main__":
    main()
