"""Structured, human-readable logging via Rich."""

from __future__ import annotations

import logging
from logging import Logger

from rich.logging import RichHandler

from research_crew.settings import settings

_CONFIGURED = False


def configure_logging() -> None:
    """Idempotently configure the root logger."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False, markup=True)],
    )
    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "openai", "litellm"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> Logger:
    configure_logging()
    return logging.getLogger(name)
