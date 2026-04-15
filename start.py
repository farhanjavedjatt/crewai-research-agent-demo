"""Process-launcher used by every deploy target.

Why this exists:
    Railway Nixpacks sometimes execs the configured start command directly
    instead of through a shell. When that happens, `$PORT` is passed as a
    literal four-character string and Streamlit rejects it:

        Error: Invalid value for '--server.port': '$PORT' is not a valid
        integer.

    Doing the env lookup in Python removes every shell-quoting surface and
    works identically on Railway (Nixpacks or Dockerfile), Fly, Heroku, and
    local dev.
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    port = os.environ.get("PORT", "8501")
    if not port.isdigit():
        sys.stderr.write(f"start.py: invalid PORT={port!r}; falling back to 8501\n")
        port = "8501"

    argv = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "streamlit_app.py",
        "--server.port",
        port,
        "--server.address",
        "0.0.0.0",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    # Replace this process so Streamlit receives PID 1 semantics (signals,
    # healthcheck readiness, etc.) directly from the platform.
    os.execvp(argv[0], argv)


if __name__ == "__main__":
    main()
