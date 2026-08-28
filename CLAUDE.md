# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Bluesky bot that posts a random Harry Potter screengrab on a fixed interval (default 30 min), captioned with a short Potter DB fact above the film title. It does **not** extract frames from video — it picks a random JPEG from pre-downloaded screenshot folders (movie-screencaps.com), compresses it for Bluesky, and posts it. Target deployment is a Raspberry Pi under systemd.

This repo absorbed a second project, `../hp_facts_bot`, which was configured for the **same** Bluesky account (`dailypotter.bsky.social`). That project was never deployed to the Pi; it is now superseded and its code lives on here as `bot/fact_fetcher.py` and `bot/fact_formatter.py`.

## Commands

The venv is `.venv/` (the README's `venv/` refers to the Pi deploy). Dev tools live in `requirements-dev.txt`, not `requirements.txt`.

A virtualenv hardcodes its own absolute path, so **moving the project breaks it**: `activate` puts a non-existent directory on `PATH` and `python3` silently resolves to the system interpreter, where the dependencies are missing — which reads as random `ModuleNotFoundError`s. This already happened once when the project moved under `pi-services/`. The fix is to delete `.venv` and recreate it, not to work around it.

```bash
.venv/bin/python -m pytest tests/ -q          # full suite (149 tests, all passing)
.venv/bin/python -m ruff check .               # lint (clean)
.venv/bin/python -m pytest tests/test_fact_fetcher.py::TestQualityFilters -v   # one class
.venv/bin/python main.py                      # run the bot (posts immediately, then every INTERVAL_MINUTES)

.venv/bin/python scripts/preview_facts.py 20  # print sample captions, post nothing
.venv/bin/python scripts/calibrate_quality.py 500  # measure the frame filter
.venv/bin/python scripts/health_check.py      # config, library, model, credentials
.venv/bin/python scripts/test_extraction.py   # dry run: pick + process a frame
.venv/bin/python scripts/manual_post.py       # one real post to Bluesky
.venv/bin/python scripts/stats.py             # read data/posted_frames.json
```

`preview_facts.py` is the fastest way to judge a change to fact wording or filtering — it renders the exact post text and needs neither screenshots nor credentials.

Lint config is in `ruff.toml`; `BLE001` is ignored there because three bare `except Exception` handlers are load-bearing (see the post-cycle invariants below). `ruff format` is deliberately unused — it would churn most of the tree. There is no pyproject/pytest.ini/mypy config — `ruff.toml` rather than `pyproject.toml` keeps pytest's rootdir discovery untouched. Always run from the repo root so `bot/`, `config.py`, and `main.py` are importable. `tests/` is a package (`__init__.py`), so pytest puts the root on `sys.path`.

## Architecture

`main.py` wires everything and owns the post cycle. Components are passed as explicit arguments (no module globals), so every call site — `main.main()` and `scripts/manual_post.py` — must be updated together when the signature of `post_random_frame()` changes.

- **`config.py`** — frozen `Config` dataclass loaded from `.env`. `load_config()` calls `sys.exit(1)` if Bluesky credentials are missing.
- **`bot/frame_quality.py`** — `FrameScorer.assess()`: Pillow exposure guards, then OpenCV YuNet face detection. OpenCV and the model are both optional; either missing degrades to the guards alone.
- **`bot/frame_selector.py`** — draws candidates, skips unusable ones, prefers a face, falls back to the best seen. Returns None when nothing is usable, and the cycle is skipped.
- **`bot/movie_library.py`** — reads `data/movie_metadata.json` and globs `SCREENSHOTS_DIR/<folder_name>/*.jpg` **once at construction**. Adding screenshots on disk requires a restart. Missing/empty folders log a warning and are skipped.
- **`bot/image_processor.py`** — centre-crops to `IMAGE_ASPECT_RATIO` (default 4:3), resizes longest side to ≤2000px, then steps JPEG quality 95→15 at 4:4:4 chroma until under 950KB.
- **`bot/fact_fetcher.py`** — Potter DB client: paginated fetch, disk cache, quality gates, weighted draw. Returns a formatted `Fact` or `None`.
- **`bot/fact_formatter.py`** — turns one Potter DB item into one plain sentence. Owns the house style.
- **`bot/caption_generator.py`** — assembles `fact\n\n{title}`, and `fact_budget()` computes how many characters a fact may use.
- **`bot/bluesky_client.py`** — atproto wrapper. Two things here are easy to break silently, and `tests/test_bluesky_client.py` pins both:
  - `_build_facets()` hand-computes UTF-8 byte offsets so the hashtag is clickable, assuming the exact layout `f"{caption}\n{tags}"`. Change the caption shape and the facet math must change with it. Facts contain em dashes (3 bytes), so character offsets are not interchangeable with byte offsets.
  - `image_aspect_ratio` **must** be passed to `send_image`. Without it the Bluesky client cannot size the container before the blob loads and letterboxes the image inside a default one — visible as bars around the post. Dimensions are read from the file being uploaded so the declared ratio cannot drift from the bytes.
- **`bot/scheduler.py`** — APScheduler `BackgroundScheduler` (UTC), `coalesce=True`, `max_instances=1`, 300s misfire grace, so a sleeping Pi or a slow post won't pile up jobs.

### Post cycle invariants

`post_random_frame()` must never raise — the scheduler thread would die. It wraps everything in a bare `except Exception` and cleans up the temp file in `finally`. Its degradation ladder: frame selection (skips unusable, prefers a face; `None` skips the cycle) → fact lookup (best effort, `None` on any failure) → image post with 3 exponential-backoff retries → text-only post → give up and log. **A Potter DB outage must never cost a post**; `FactFetcher.get_random_fact()` swallows everything and returns `None`, and `tests/test_post_history.py` pins that.

### Caption shape

```
Alohomora (Charm) — unlocked doors and other locked objects.

Harry Potter and the Deathly Hallows – Part 2
#HarryPotter
```

House style, decided deliberately: no emoji, exactly one hashtag, one sentence. The old facts bot's `🧙 Name: House: X | Patronus: Y` field-dump format was the reason it went unused. `tests/test_fact_formatter.py::TestHouseStyle` enforces the emoji and hashtag rules.

The single tag is appended by `bluesky_client`, not by `caption_generator` — do not bake it into the caption.

### Fact selection, and why the filters are aggressive

Facts are drawn independently of the frame, so **the fact does not relate to the scene**. This was a considered trade-off, not an oversight. Two consequences are baked into the design:

- `movies` and `books` are excluded from `CONTENT_WEIGHTS`. A fact naming a *different* film or book sits directly above the film title and reads as a bug ("...runs to 607 pages." under a Philosopher's Stone frame).
- Potter DB is a wiki dump, and unfiltered it produces embarrassing posts. The gates in `_passes_quality` were tuned against the real cached data:
  - **spells** need an `incantation` — the cleanest notability signal available, separating `Expelliarmus` from placeholders like "Fur spell" (214 of 345 pass).
  - **characters** need `wiki`, `image`, and a distinctive field via `character_signature()`. Of ~5400 characters, ~76 pass; the rest are walk-ons and video-game-only names.
  - **potions** need a ≥25-char `effect`, which drops entries whose whole effect is "poisonous".

`fact_formatter.clean_field()` is the shared sanitiser and the reason the gate and the formatter agree. It drops hedged values (`"Pure-blood or half-blood"`), placeholders (`"Non-corporeal"`, `"None"` — 134 of ~200 Patronus entries), overlong text, and trailing parentheticals. `GENERIC_BOGGARTS` exists because the wiki lists Voldemort as the boggart of 68 of the ~100 characters that have one; posting it would repeat the same sentence endlessly.

Character phrasings are **weighted**, not uniform: boggart/Patronus/Animagus at 10, wand/species at 3, house/blood status at 1. Nearly every documented character has a house, so an even draw made the feed almost entirely "X was sorted into Y".

### Dedup ledgers

`main.py:PostHistory` writes `data/posted_frames.json` atomically via `.tmp` + rename, and holds two separate things:

- `posted` — a **500-entry ring buffer** of frames. Dedup only sees the last 500 posts, which is fine against ~48k frames.
- `posted_fact_ids` — an **unbounded** list, deliberately outside the ring buffer so the fact pool doesn't recycle merely because the frame log rolled over. Files written before facts existed lack this key; `posted_fact_ids()` and `add()` both tolerate that.

Fact IDs are `f"{content_type}_{slug}"`. Changing that format silently invalidates the whole fact history. When every quality fact has been posted, `FactFetcher` recycles rather than returning nothing — at 48 posts/day the pool is expected to wrap around, and this is the intended behaviour, not a bug.

### Image sharpness is set by the crop ratio, not the encoder

Sources are uniformly 1920x800 (2.40:1). Feeds fit an image to the column width, so the crop's **width in pixels** decides sharpness, and the source height caps it at 800. A 1:1 crop is 800px wide and a phone stretches it ~1.46x; 4:3 is 1067px and stretches ~1.10x. **Squarer is softer** — counterintuitive, and the reason the default moved off 1:1.

Do not look for wins in the encoder. Measured on real frames, re-encoding at quality 95 costs an RMSE of ~0.35 on a 0-255 scale, and output lands at 50-115KB against the 950KB cap — the quality ladder essentially never steps down. Chroma is set to 4:4:4 because the budget is there, not because it was a problem.

`MAX_DIMENSION` is 2000, not 1000: at 4:3 a downscale would otherwise trigger on any source taller than 750px and silently undo the crop's gain.

Bluesky serves back exactly what is uploaded (verified: an 800x800 upload came back 800x800), so there is no server-side resampling to lean on. The embed must also declare `aspectRatio` — see `bot/bluesky_client.py` — or the post renders with bars whatever the crop.

### Frame quality, and what does not work

The library is a fixed-interval sample of each film, so it is full of fades, blur, and texture close-ups. Two things were established by measuring, not guessing — rerun `scripts/calibrate_quality.py` before touching any of it:

- **Luminance statistics cannot judge whether a frame is interesting.** The films are shot dark: library brightness has a median of 28 and p5 of 9.2, and legitimate close-ups of faces measure 14-15. A user-reported bad frame (a close-up of a mosaic floor) measured brightness 36 / contrast 11 — squarely among *good* dark frames at the same percentiles. Grid-based composition metrics failed the same way. Do not reintroduce a "contrast threshold"; it rejects cinematography, not junk.
- **Face detection does separate them**, at ~16 ms per frame on the Pi. YuNet finds a face in ~65% of the library, evenly across all eight films (52-77%), and correctly rejected the reported bad frame while accepting very dark shots of Harry at 0.9+ confidence.

The exposure guards that remain are only for frames that are *never* postable: unreadable files (~0.3% of the library — these used to cost a whole post cycle) and near-black fades (brightness < 10 or contrast < 6).

Faces are preferred, not required: a wide shot of the castle is a legitimate screengrab that YuNet cannot see a face in. `FRAME_CANDIDATES` (default 2) is the knob — the chance of a faceless post is roughly `0.37 ** FRAME_CANDIDATES`, so 2 gives ~14% and 3 gives ~5%.

The model is vendored at `models/face_detection_yunet_2023mar.onnx` (227 KB) so deployment needs no download. `opencv-python-headless` installs on the Pi in about 8 seconds; note OpenCV 5 dropped `CascadeClassifier` and the bundled Haar cascades, so `FaceDetectorYN` is the path.

### Metadata is the source of truth

`data/movie_metadata.json` (8 entries) drives which folders are scanned; `folder_name` must match the on-disk directory exactly. Its `hashtag` field is **unused** — `caption_generator` hardcodes the single `HarryPotter` tag. `scripts/stats.py` keeps its own hardcoded part-number → title map instead of reading the metadata, and needs updating alongside any change to the movie list.

### Potter DB cache

`data/cache/<type>.json` holds the full collections (~4.6 MB, gitignored) with a 7-day TTL. On a cache miss the fetch happens inside a post cycle — `characters` is ~109 pages at 0.25s apiece, so budget ~30s. A network failure falls back to a **stale** cache when one exists, so an offline Pi keeps producing facts. Delete files in `data/cache/` to force a refetch.

## Config

Via `.env` (see `.env.example`): `BLUESKY_USERNAME`, `BLUESKY_PASSWORD` (app password, required), `SCREENSHOTS_DIR` (default `/mnt/hp_screenshots`), `INTERVAL_MINUTES`, `FACTS_ENABLED`, `MAX_FACT_LENGTH`, `LOG_LEVEL`, plus undocumented `DATA_DIR` and `LOG_DIR`. `temp/`, `logs/`, `data/posted_frames.json`, and `data/cache/` are gitignored runtime state.

## Deployment

The Raspberry Pi is reached through the SSH alias `pi` (user `reiberry`, key-based, no password) — run remote commands as `ssh pi "..."`.

| | |
|---|---|
| Checkout | `/home/reiberry/personal/hp_screens_bot` |
| Remote | `origin` → HTTPS GitHub (locally the remote is named `github`, over SSH) |
| Virtualenv | `venv/` (not `.venv/`), Python 3.13 on aarch64 |
| Service | **`hp-bot.service`** — a legacy name; it runs *this* project, not the old facts bot |
| Screenshots | `screenshots/` inside the checkout, untracked, 8 folders |

Deploy is `git pull` + `sudo systemctl restart hp-bot.service`. Restarting posts immediately — `main.py` runs one cycle before starting the scheduler — so a restart is a real public post, not a dry run. `.env` is gitignored and lives only on the Pi; new settings must be added there by hand.

`deployment/hp-screengrab-bot.service` and `deployment/setup.sh` mirror the live unit. Both hardcode the user and path, so they must be edited together if either changes.

## Tests

Fixtures in `tests/conftest.py` synthesize screenshot folders, metadata, and Potter DB items. Nothing touches the network or Bluesky: `FactFetcher._fetch_all` is stubbed, `tests/test_bluesky_client.py` swaps in a recording stand-in for the atproto `Client`, and `tests/test_post_history.py` drives the real `post_random_frame()` against fake client and fetcher objects.
