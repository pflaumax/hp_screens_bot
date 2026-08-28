"""Tests for config.load_config.

Bad settings must exit with a readable message. Under systemd
(Restart=always) an unhandled exception here becomes a restart loop, so
these are boot-safety tests, not cosmetics.
"""

import pytest

from config import load_config

CREDENTIALS = {"BLUESKY_USERNAME": "handle.bsky.social", "BLUESKY_PASSWORD": "pw"}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start from a known environment for every case."""
    for name in (
        "BLUESKY_USERNAME",
        "BLUESKY_PASSWORD",
        "INTERVAL_MINUTES",
        "FACTS_ENABLED",
        "MAX_FACT_LENGTH",
        "FRAME_QUALITY_ENABLED",
        "FRAME_CANDIDATES",
        "IMAGE_ASPECT_RATIO",
    ):
        monkeypatch.delenv(name, raising=False)
    for key, value in CREDENTIALS.items():
        monkeypatch.setenv(key, value)


class TestDefaults:
    """The shipped defaults."""

    def test_defaults_are_the_documented_ones(self) -> None:
        cfg = load_config()
        assert cfg.interval_minutes == 30
        assert cfg.facts_enabled is True
        assert cfg.max_fact_length == 180
        assert cfg.frame_quality_enabled is True
        assert cfg.frame_candidates == 2
        assert abs(cfg.image_aspect_ratio - 4 / 3) < 0.001


class TestBooleans:
    """Feature switches accept the spellings people actually type."""

    @pytest.mark.parametrize("value", ["false", "False", "0", "no", "off", " NO "])
    def test_falsy_spellings(
        self, value: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FACTS_ENABLED", value)
        assert load_config().facts_enabled is False

    @pytest.mark.parametrize("value", ["true", "1", "yes", "anything"])
    def test_truthy_spellings(
        self, value: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FACTS_ENABLED", value)
        assert load_config().facts_enabled is True


class TestBadValues:
    """Every rejection is an explained exit, never a traceback."""

    @pytest.mark.parametrize(
        "name,value",
        [
            ("FRAME_CANDIDATES", "two"),
            ("FRAME_CANDIDATES", "0"),
            ("FRAME_CANDIDATES", "-1"),
            ("INTERVAL_MINUTES", ""),
            ("INTERVAL_MINUTES", "0"),
            ("MAX_FACT_LENGTH", "5"),
            ("IMAGE_ASPECT_RATIO", "abc"),
            ("IMAGE_ASPECT_RATIO", "0"),
        ],
    )
    def test_rejected_with_a_message(
        self,
        name: str,
        value: str,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        monkeypatch.setenv(name, value)
        with pytest.raises(SystemExit) as exit_info:
            load_config()
        assert exit_info.value.code == 1
        assert name in capsys.readouterr().err

    @pytest.mark.parametrize("missing", ["BLUESKY_USERNAME", "BLUESKY_PASSWORD"])
    def test_missing_credentials_exit_cleanly(
        self,
        missing: str,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        monkeypatch.delenv(missing)
        with pytest.raises(SystemExit) as exit_info:
            load_config()
        assert exit_info.value.code == 1
        assert "BLUESKY" in capsys.readouterr().err

    def test_whitespace_is_tolerated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FRAME_CANDIDATES", " 3 ")
        assert load_config().frame_candidates == 3
