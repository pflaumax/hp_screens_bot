"""Configuration loader and validator.

Loads settings from environment variables (via .env file) with sensible defaults.
Validates that all required settings are present before the bot starts.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

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
    frame_candidates: int = 3

    # Image crop: width:height of the centre crop
    image_aspect_ratio: float = 4 / 3

    # Logging
    log_level: str = "INFO"


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
        print(
            "ERROR: BLUESKY_USERNAME and BLUESKY_PASSWORD must be set in .env",
            file=sys.stderr,
        )
        sys.exit(1)

    return Config(
        bluesky_username=bluesky_username,
        bluesky_password=bluesky_password,
        screenshots_dir=Path(os.getenv("SCREENSHOTS_DIR", "/mnt/hp_screenshots")),
        data_dir=Path(os.getenv("DATA_DIR", "data/")),
        log_dir=Path(os.getenv("LOG_DIR", "logs/")),
        interval_minutes=int(os.getenv("INTERVAL_MINUTES", "30")),
        facts_enabled=os.getenv("FACTS_ENABLED", "true").strip().lower()
        not in ("0", "false", "no"),
        max_fact_length=int(os.getenv("MAX_FACT_LENGTH", "180")),
        frame_quality_enabled=os.getenv("FRAME_QUALITY_ENABLED", "true")
        .strip()
        .lower()
        not in ("0", "false", "no"),
        frame_candidates=int(os.getenv("FRAME_CANDIDATES", "3")),
        image_aspect_ratio=float(os.getenv("IMAGE_ASPECT_RATIO", "1.3333")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
