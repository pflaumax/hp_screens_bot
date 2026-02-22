"""Shared helpers: logging setup, retry decorator, and temp file cleanup."""

import logging
import time
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")

logger = logging.getLogger("hp_bot")


def setup_logging(log_dir: Path, level: str) -> logging.Logger:
    """Configure rotating file + console logging.

    Args:
        log_dir: Directory for log files.
        level: Logging level string (e.g. "INFO", "DEBUG").

    Returns:
        Configured root logger for the bot.
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger("hp_bot")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler — 10MB per file, keep 5 backups
    file_handler = RotatingFileHandler(
        log_dir / "bot.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return root_logger


def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 2.0,
    exceptions: tuple = (Exception,),
) -> T:
    """Execute a callable with exponential backoff on failure.

    Args:
        func: Zero-argument callable to execute.
        max_retries: Maximum number of attempts.
        base_delay: Base delay in seconds (doubles each retry).
        exceptions: Tuple of exception types to catch.

    Returns:
        The return value of func on success.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except exceptions as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Attempt %d/%d failed: %s. Retrying in %.1fs...",
                    attempt,
                    max_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "All %d retries exhausted. Last error: %s",
                    max_retries,
                    exc,
                )
    raise last_exc  # type: ignore[misc]


def cleanup_temp_files(*paths: Path) -> None:
    """Silently remove temporary files.

    Args:
        paths: File paths to delete. Missing files are ignored.
    """
    for path in paths:
        try:
            if path.exists():
                path.unlink()
                logger.debug("Cleaned up temp file: %s", path)
        except OSError as exc:
            logger.warning("Failed to clean up %s: %s", path, exc)
