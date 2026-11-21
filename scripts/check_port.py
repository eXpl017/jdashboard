"""Pre-flight check for the local development server port.

Fails fast with an actionable message when the port the dev server wants to
bind is already taken, instead of letting uvicorn die with a bare
"address already in use".

Usage:

    uv run python scripts/check_port.py [port] [host]
"""

import socket
import sys


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    """Return True when a TCP socket can bind to ``host:port``."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _hints(port: int, host: str) -> list[str]:
    return [
        "If another local process is using that port, stop it and retry.",
        f"Or use another dev port: make run DEV_PORT={port + 1}",
        "Or run the dev server on a custom port: "
        f"uv run uvicorn app.main:app --reload --port {port + 1} --host {host}",
    ]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    port = int(args[0]) if args else 8001
    host = args[1] if len(args) > 1 else "127.0.0.1"

    if port_is_free(port, host):
        return 0

    print(f"Port {port} on {host} is already in use.", file=sys.stderr)
    for hint in _hints(port, host):
        print(f"  - {hint}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
