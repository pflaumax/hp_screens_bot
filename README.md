# Harry Potter Random Movie Screengrab Bot

A Bluesky bot that posts random screengrabs from the Harry Potter film series
every 30 minutes, each captioned with a short Wizarding World fact.

This project absorbed the separate `hp_facts_bot` project, which was
configured for the same Bluesky account. There is now one service, one post
ledger, and one post format.

## How It Works

1. Picks a random Harry Potter movie from pre-downloaded screenshot folders
2. Selects a random screenshot JPEG from that movie's folder
3. Resizes, centre-crops to 1:1, and compresses to meet Bluesky's image limits
4. Looks up a short fact from the [Potter DB API](https://potterdb.com/)
5. Posts the fact above the film title, with a single #HarryPotter tag

A post looks like this:

```
Alohomora (Charm) — unlocked doors and other locked objects.

Harry Potter and the Deathly Hallows – Part 2
#HarryPotter
```

The fact is decoration, not a dependency: if Potter DB is unreachable the
screengrab still goes out with just the title. Facts are deliberately plain —
no emoji, no extra hashtags, one sentence.

### A note on the facts

Facts are drawn independently of the frame, so the fact will not relate to the
scene on screen. Potter DB's `movies` and `books` collections are excluded for
this reason — a fact naming a different film or book directly above the film
title reads as a bug. Characters, spells, and potions are used instead, behind
quality filters that skip wiki stubs (spells need an incantation, characters
need a distinctive Patronus/boggart/Animagus form).

## Requirements

- Python 3.10+
- Pre-downloaded screenshot JPEGs from movie-screencaps.com
- A Bluesky account with an app password

## Quick Start

```bash
# Clone and enter the project
git clone <repo-url> harry-potter-screengrab-bot
cd harry-potter-screengrab-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Bluesky credentials and screenshots path

# Run the bot
python main.py
```

## Screenshot Setup

1. Go to https://movie-screencaps.com/category/movie-series/harry-potter/
2. Download the ZIP archive for each of the 8 Harry Potter movies
3. Extract each ZIP into a named subfolder:

```
/mnt/hp_screenshots/
├── philosophers_stone/
├── chamber_of_secrets/
├── prisoner_of_azkaban/
├── goblet_of_fire/
├── order_of_the_phoenix/
├── half_blood_prince/
├── deathly_hallows_part1/
└── deathly_hallows_part2/
```

4. Set `SCREENSHOTS_DIR=/mnt/hp_screenshots` in your `.env`
5. Verify: `python scripts/stats.py` (should show ~6000+ frames per movie)

## Configuration

All settings are in `.env`:

| Variable | Default | Description |
|---|---|---|
| `BLUESKY_USERNAME` | (required) | Your Bluesky handle |
| `BLUESKY_PASSWORD` | (required) | App password from Bluesky settings |
| `SCREENSHOTS_DIR` | `/mnt/hp_screenshots` | Directory containing screenshot folders |
| `INTERVAL_MINUTES` | `30` | Minutes between posts |
| `FACTS_ENABLED` | `true` | Set to `false` to post the title only |
| `MAX_FACT_LENGTH` | `180` | Character cap on the fact line |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Scripts

```bash
python scripts/preview_facts.py 20  # Print sample captions, post nothing
python scripts/manual_post.py       # Post once immediately
python scripts/test_extraction.py   # Process a frame without posting
python scripts/stats.py             # View posting statistics
```

`preview_facts.py` needs no screenshots on disk — use it to judge fact
wording before anything goes live.

## Testing

```bash
pip install pytest
pytest tests/ -v
```

## Raspberry Pi Deployment

```bash
chmod +x deployment/setup.sh
./deployment/setup.sh
# Edit .env, mount movies, then:
sudo systemctl start hp-screengrab-bot
```

The live unit on the Pi is named `hp-bot.service` (a legacy name — it runs
*this* project, not the facts bot) and is installed from
`deployment/hp-screengrab-bot.service`:

```bash
sudo systemctl restart hp-bot.service
sudo systemctl status hp-bot.service
tail -f logs/bot.log
```

## License

For personal/educational use only. Harry Potter films are property of Warner Bros.
