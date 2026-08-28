"""Potter DB fact source for screengrab captions.

Fetches characters, spells, potions, and books from the public Potter DB
API (https://api.potterdb.com/v1), caches them on disk, applies quality
filters, and returns one short, already-formatted fact per call.

The fact is decoration on top of a screengrab post, so nothing here is
allowed to break the post cycle: every failure path returns ``None`` and
the caller posts without a fact.
"""

import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from bot.fact_formatter import character_signature, format_fact

logger = logging.getLogger("hp_bot.fact_fetcher")

POTTERDB_BASE_URL = "https://api.potterdb.com/v1"

ENDPOINTS: dict[str, str] = {
    "characters": "/characters",
    "spells": "/spells",
    "potions": "/potions",
}

# Relative odds of drawing each content type. Potter DB's "movies" and
# "books" collections are deliberately absent: every post already ends
# with a film title, so a fact naming a *different* title reads as a bug
# ("...runs to 607 pages." above a Philosopher's Stone frame).
# Spells and potions carry most posts: Potter DB documents ~200 spells
# and ~90 potions well, but only a few dozen characters distinctively.
CONTENT_WEIGHTS: dict[str, float] = {
    "spells": 0.45,
    "potions": 0.30,
    "characters": 0.25,
}

# How many candidates to format before giving up on a content type.
# A fact that does not fit the caption budget is skipped, not truncated.
MAX_CANDIDATES = 25

CACHE_TTL_SECONDS = 604_800  # 7 days — Potter DB content barely changes
PAGE_SIZE = 50
REQUEST_TIMEOUT = 15
PAGE_DELAY = 0.25


@dataclass(frozen=True)
class Fact:
    """A formatted fact ready to be placed above a screengrab caption."""

    fact_id: str
    content_type: str
    text: str


class FactFetcher:
    """Selects a random, unposted, quality-filtered Potter DB fact."""

    def __init__(
        self,
        cache_dir: Path,
        base_url: str = POTTERDB_BASE_URL,
        cache_ttl: int = CACHE_TTL_SECONDS,
    ) -> None:
        """Initialise the fetcher.

        Args:
            cache_dir: Directory for cached API responses.
            base_url: Potter DB API root.
            cache_ttl: Seconds before a cache file is considered stale.
        """
        self._cache_dir = cache_dir
        self._base_url = base_url
        self._cache_ttl = cache_ttl
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get_random_fact(
        self, exclude_ids: set[str], max_length: int
    ) -> Fact | None:
        """Pick one formatted fact that fits within ``max_length``.

        Content types are drawn by weight. Within a type, unposted
        quality items are shuffled and formatted until one fits. If every
        quality item of every type has already been posted, the pool is
        recycled rather than returning nothing — at 48 posts a day the
        pool is expected to wrap around.

        Args:
            exclude_ids: Fact IDs already posted.
            max_length: Maximum characters the fact text may occupy.

        Returns:
            A Fact, or None if nothing could be fetched or formatted.
        """
        try:
            fact = self._select(exclude_ids, max_length, recycle=False)
            if fact is None:
                fact = self._select(exclude_ids, max_length, recycle=True)
                if fact is not None:
                    logger.info("Fact pool exhausted — recycling posted facts.")
            return fact
        except Exception as exc:  # never break the post cycle
            logger.warning("Fact lookup failed, posting without a fact: %s", exc)
            return None

    def _select(
        self, exclude_ids: set[str], max_length: int, recycle: bool
    ) -> Fact | None:
        """Draw a fact, optionally ignoring the posted-ID exclusion list."""
        weights = dict(CONTENT_WEIGHTS)

        while weights:
            types = list(weights)
            chosen = random.choices(types, weights=[weights[t] for t in types])[0]
            del weights[chosen]

            items = self._fetch_all(chosen)
            candidates = [i for i in items if _passes_quality(i, chosen)]
            if not recycle:
                candidates = [
                    i for i in candidates if _make_id(chosen, i) not in exclude_ids
                ]

            random.shuffle(candidates)
            for item in candidates[:MAX_CANDIDATES]:
                text = format_fact(item.get("attributes", {}), chosen)
                if text and len(text) <= max_length:
                    return Fact(
                        fact_id=_make_id(chosen, item),
                        content_type=chosen,
                        text=text,
                    )

        return None

    def _fetch_all(self, content_type: str) -> list[dict]:
        """Return all items for a type, from cache when fresh.

        A network failure falls back to a stale cache if one exists, so a
        Pi with no connectivity still produces facts.

        Args:
            content_type: Key of ``ENDPOINTS``.

        Returns:
            List of Potter DB item dicts, possibly empty.
        """
        cache_path = self._cache_dir / f"{content_type}.json"

        if self._cache_fresh(cache_path):
            return self._read_cache(cache_path)

        items = self._fetch_from_api(content_type)
        if items:
            cache_path.write_text(
                json.dumps(items, ensure_ascii=False), encoding="utf-8"
            )
            logger.info("Cached %d %s items", len(items), content_type)
            return items

        # API gave us nothing — fall back to whatever is on disk.
        stale = self._read_cache(cache_path)
        if stale:
            logger.info("Using stale cache for %s (%d items)", content_type, len(stale))
        return stale

    def _fetch_from_api(self, content_type: str) -> list[dict]:
        """Walk the paginated collection for one content type."""
        endpoint = ENDPOINTS[content_type]
        all_items: list[dict] = []
        page = 1

        while True:
            url = (
                f"{self._base_url}{endpoint}"
                f"?page[number]={page}&page[size]={PAGE_SIZE}"
            )
            try:
                resp = self._session.get(url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                body = resp.json()
            except (requests.RequestException, ValueError) as exc:
                logger.warning(
                    "Potter DB request failed (%s page %d): %s",
                    content_type, page, exc,
                )
                break

            data = body.get("data", [])
            if not data:
                break
            all_items.extend(data)

            last = body.get("meta", {}).get("pagination", {}).get("last", page)
            if page >= last:
                break
            page += 1
            time.sleep(PAGE_DELAY)

        return all_items

    def _cache_fresh(self, path: Path) -> bool:
        """Check whether a cache file exists and is within the TTL."""
        if not path.exists():
            return False
        return (time.time() - path.stat().st_mtime) < self._cache_ttl

    @staticmethod
    def _read_cache(path: Path) -> list[dict]:
        """Read a cache file, returning an empty list if unreadable."""
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Unreadable cache %s: %s", path, exc)
            return []
        return data if isinstance(data, list) else []


def _make_id(content_type: str, item: dict) -> str:
    """Build a stable dedup ID for a Potter DB item.

    Changing this format invalidates the posted-fact history — every
    previously posted fact becomes eligible again.
    """
    slug = item.get("attributes", {}).get("slug") or item.get("id", "")
    return f"{content_type}_{slug}"


# Potter DB carries ~5400 characters, the overwhelming majority of them
# one-line walk-ons and video-game-only names. Notability is approximated
# by whether the wiki records a distinctive detail for them — see
# fact_formatter.character_signature — which also guarantees the fact is
# worth reading rather than "was sorted into Hufflepuff".
MIN_SPELL_EFFECT = 15
MIN_POTION_EFFECT = 25

_JUNK_NAME_TERMS = (
    "unidentified",
    "unknown",
    "unnamed",
    "student",
    "'s ",
)


def _passes_quality(item: dict, content_type: str) -> bool:
    """Reject stub entries that would produce a hollow or odd fact."""
    attrs = item.get("attributes", {})
    name = attrs.get("name") or ""
    if not _is_usable_name(name):
        return False

    if content_type == "spells":
        # An incantation is the cleanest notability signal Potter DB
        # offers: it separates "Expelliarmus" from wiki placeholders
        # like "Fur spell" and "Shooting spell".
        return (
            bool(attrs.get("incantation"))
            and len(attrs.get("effect") or "") >= MIN_SPELL_EFFECT
        )
    if content_type == "potions":
        return len(attrs.get("effect") or "") >= MIN_POTION_EFFECT
    if content_type == "characters":
        return _is_notable_character(attrs)
    return False


def _is_usable_name(name: str) -> bool:
    """Reject wiki placeholders and descriptors used in place of a name."""
    if not name:
        return False
    if any(ch.isdigit() for ch in name):
        # e.g. "1980s Hogwarts Gobstones Tournament champion"
        return False
    lowered = name.lower()
    return not any(term in lowered for term in _JUNK_NAME_TERMS)


def _is_notable_character(attrs: dict) -> bool:
    """Approximate notability from how completely the wiki documents them."""
    if not attrs.get("wiki") or not attrs.get("image"):
        return False
    return bool(character_signature(attrs))
