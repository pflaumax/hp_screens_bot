"""Tests for bot.fact_fetcher (Potter DB selection, caching, resilience).

Nothing here touches the network: `_fetch_all` is stubbed, or the cache
directory is pre-populated.
"""

import json
from pathlib import Path

import pytest
import requests

from bot.fact_fetcher import (
    CONTENT_WEIGHTS,
    Fact,
    FactFetcher,
    _make_id,
    _passes_quality,
)


@pytest.fixture
def fetcher(tmp_path: Path) -> FactFetcher:
    """A fetcher pointed at an empty temporary cache."""
    return FactFetcher(tmp_path / "cache")


def _stub_pool(fetcher: FactFetcher, pools: dict[str, list[dict]]) -> None:
    """Replace network access with fixed per-type item lists."""
    fetcher._fetch_all = lambda content_type: pools.get(content_type, [])  # type: ignore[method-assign]


class TestSelection:
    """Drawing, deduplication, and the length budget."""

    def test_returns_a_formatted_fact(
        self, fetcher: FactFetcher, sample_spell: dict
    ) -> None:
        _stub_pool(fetcher, {"spells": [sample_spell]})
        fact = fetcher.get_random_fact(exclude_ids=set(), max_length=180)
        assert isinstance(fact, Fact)
        assert fact.content_type == "spells"
        assert fact.fact_id == "spells_alohomora"
        assert "Alohomora" in fact.text

    def test_skips_already_posted_facts(
        self, fetcher: FactFetcher, sample_spell: dict
    ) -> None:
        _stub_pool(fetcher, {"spells": [sample_spell]})
        fact = fetcher.get_random_fact(
            exclude_ids={"spells_alohomora"}, max_length=180
        )
        # Recycling kicks in only once nothing new is left anywhere.
        assert fact is not None
        assert fact.fact_id == "spells_alohomora"

    def test_prefers_unposted_over_recycled(
        self, fetcher: FactFetcher, sample_spell: dict, sample_potion: dict
    ) -> None:
        _stub_pool(
            fetcher, {"spells": [sample_spell], "potions": [sample_potion]}
        )
        for _ in range(20):
            fact = fetcher.get_random_fact(
                exclude_ids={"spells_alohomora"}, max_length=180
            )
            assert fact is not None and fact.fact_id == "potions_amortentia"

    def test_respects_the_length_budget(
        self, fetcher: FactFetcher, sample_spell: dict
    ) -> None:
        _stub_pool(fetcher, {"spells": [sample_spell]})
        assert fetcher.get_random_fact(exclude_ids=set(), max_length=10) is None

    def test_empty_pools_yield_no_fact(self, fetcher: FactFetcher) -> None:
        _stub_pool(fetcher, {})
        assert fetcher.get_random_fact(exclude_ids=set(), max_length=180) is None

    def test_never_raises_when_the_pool_blows_up(
        self, fetcher: FactFetcher
    ) -> None:
        """A broken fetch degrades to "no fact", never to an exception."""

        def _explode(_content_type: str) -> list[dict]:
            raise RuntimeError("Potter DB is down")

        fetcher._fetch_all = _explode  # type: ignore[method-assign]
        assert fetcher.get_random_fact(exclude_ids=set(), max_length=180) is None

    def test_movies_and_books_are_not_drawn(self) -> None:
        """A fact naming another title would clash with the caption footer."""
        assert "movies" not in CONTENT_WEIGHTS
        assert "books" not in CONTENT_WEIGHTS


class TestQualityFilters:
    """Gates that keep wiki stubs out of the feed."""

    def test_quality_spell_accepted(self, sample_spell: dict) -> None:
        assert _passes_quality(sample_spell, "spells")

    def test_spell_without_incantation_rejected(self, sample_spell: dict) -> None:
        sample_spell["attributes"]["incantation"] = None
        assert not _passes_quality(sample_spell, "spells")

    def test_spell_with_thin_effect_rejected(self, sample_spell: dict) -> None:
        sample_spell["attributes"]["effect"] = "Sparks"
        assert not _passes_quality(sample_spell, "spells")

    def test_quality_potion_accepted(self, sample_potion: dict) -> None:
        assert _passes_quality(sample_potion, "potions")

    def test_potion_with_thin_effect_rejected(self, sample_potion: dict) -> None:
        sample_potion["attributes"]["effect"] = "Purple"
        assert not _passes_quality(sample_potion, "potions")

    def test_quality_character_accepted(self, sample_character: dict) -> None:
        assert _passes_quality(sample_character, "characters")

    def test_character_without_signature_rejected(
        self, sample_character: dict
    ) -> None:
        sample_character["attributes"]["patronus"] = "Non-corporeal"
        sample_character["attributes"]["boggart"] = "Lord Voldemort"
        sample_character["attributes"]["animagus"] = None
        assert not _passes_quality(sample_character, "characters")

    def test_character_without_image_rejected(
        self, sample_character: dict
    ) -> None:
        sample_character["attributes"]["image"] = None
        assert not _passes_quality(sample_character, "characters")

    @pytest.mark.parametrize(
        "name",
        [
            "Unidentified Slytherin boy",
            "Unnamed witch",
            "1980s Hogwarts Gobstones Tournament champion",
            "",
        ],
    )
    def test_placeholder_names_rejected(
        self, sample_character: dict, name: str
    ) -> None:
        sample_character["attributes"]["name"] = name
        assert not _passes_quality(sample_character, "characters")

    def test_make_id_prefers_the_slug(self, sample_spell: dict) -> None:
        assert _make_id("spells", sample_spell) == "spells_alohomora"

    def test_make_id_falls_back_to_the_api_id(self) -> None:
        assert _make_id("spells", {"id": "abc", "attributes": {}}) == "spells_abc"


class TestCaching:
    """Disk cache behaviour, including the offline fallback."""

    def test_fresh_cache_is_read_instead_of_the_api(
        self, tmp_path: Path, sample_spell: dict
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "spells.json").write_text(json.dumps([sample_spell]))

        fetcher = FactFetcher(cache_dir)
        fetcher._fetch_from_api = _never_called  # type: ignore[method-assign]
        assert fetcher._fetch_all("spells") == [sample_spell]

    def test_stale_cache_is_used_when_the_api_fails(
        self, tmp_path: Path, sample_spell: dict
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "spells.json").write_text(json.dumps([sample_spell]))

        fetcher = FactFetcher(cache_dir, cache_ttl=0)  # everything is stale
        fetcher._fetch_from_api = lambda _t: []  # type: ignore[method-assign]
        assert fetcher._fetch_all("spells") == [sample_spell]

    def test_corrupt_cache_is_ignored(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "spells.json").write_text("{not json")

        fetcher = FactFetcher(cache_dir)
        assert fetcher._read_cache(cache_dir / "spells.json") == []

    def test_api_failure_without_a_cache_returns_empty(
        self, fetcher: FactFetcher, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _fail(*_args: object, **_kwargs: object) -> None:
            raise requests.RequestException("no network")

        monkeypatch.setattr(fetcher._session, "get", _fail)
        assert fetcher._fetch_all("spells") == []


def _never_called(_content_type: str) -> list[dict]:
    raise AssertionError("API should not be hit when the cache is fresh")
