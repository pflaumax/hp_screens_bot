"""Configuration loader and validator.

Loads settings from environment variables (via .env file) with sensible defaults.
Validates that all required settings are present before the bot starts.
"""

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Immutable application configuration."""

    # Required — no defaults
    bluesky_username: str = ""
    bluesky_password: str = ""

    # Paths
    screenshots_dir: Path = field(default_factory=lambda: Path("/mnt/hp_screenshots"))
    data_dir: Path = field(default_factory=lambda: Path("data/"))
    log_dir: Path = field(default_factory=lambda: Path("logs/"))

    # Scheduling
    interval_minutes: int = 30

    # Facts (Potter DB)
    facts_enabled: bool = True
    max_fact_length: int = 180

    # Frame quality
    frame_quality_enabled: bool = True
    frame_candidates: int = 2

    # Image crop: width:height of the centre crop
    image_aspect_ratio: float = 4 / 3

    # Logging
    log_level: str = "INFO"


def _fail(message: str) -> "NoReturn":  # type: ignore[valid-type]
    """Exit with a readable message rather than a traceback.

    Under systemd (Restart=always) an unhandled exception here becomes a
    restart loop, so every bad setting must be reported and exited on
    deliberately.
    """
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def _number_env(
    name: str, default: str, cast: "Callable[[str], Any]", minimum: float
) -> Any:
    """Read a numeric environment variable, or exit explaining why not.

    Args:
        name: Environment variable name.
        default: Value used when the variable is unset.
        cast: ``int`` or ``float``.
        minimum: Smallest value that makes sense for this setting.

    Returns:
        The parsed number.
    """
    raw = os.getenv(name, default).strip()
    try:
        value = cast(raw)
    except ValueError:
        _fail(f"{name} must be a number, got {raw!r}")
    if value < minimum:
        _fail(f"{name} must be at least {minimum}, got {value}")
    return value


def _bool_env(name: str, default: bool = True) -> bool:
    """Read a boolean environment variable."""
    raw = os.getenv(name, str(default)).strip().lower()
    return raw not in ("0", "false", "no", "off")


def load_config() -> Config:
    """Load configuration from environment variables.

    Returns:
        Validated Config instance.

    Raises:
        SystemExit: If required environment variables are missing.
    """
    bluesky_username = os.getenv("BLUESKY_USERNAME", "")
    bluesky_password = os.getenv("BLUESKY_PASSWORD", "")

    if not bluesky_username or not bluesky_password:
        _fail("BLUESKY_USERNAME and BLUESKY_PASSWORD must be set in .env")

    return Config(
        bluesky_username=bluesky_username,
        bluesky_password=bluesky_password,
        screenshots_dir=Path(os.getenv("SCREENSHOTS_DIR", "/mnt/hp_screenshots")),
        data_dir=Path(os.getenv("DATA_DIR", "data/")),
        log_dir=Path(os.getenv("LOG_DIR", "logs/")),
        interval_minutes=_number_env("INTERVAL_MINUTES", "30", int, minimum=1),
        facts_enabled=_bool_env("FACTS_ENABLED"),
        max_fact_length=_number_env("MAX_FACT_LENGTH", "180", int, minimum=20),
        frame_quality_enabled=_bool_env("FRAME_QUALITY_ENABLED"),
        frame_candidates=_number_env("FRAME_CANDIDATES", "2", int, minimum=1),
        image_aspect_ratio=_number_env(
            "IMAGE_ASPECT_RATIO", "1.3333", float, minimum=0.1
        ),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
