# Harry Potter Random Movie Screengrab Bot

A Bluesky bot that posts random screengrabs from the Harry Potter film series every 30 minutes.

## How It Works

1. Picks a random Harry Potter movie from pre-downloaded screenshot folders
2. Selects a random screenshot JPEG from that movie's folder
3. Resizes and compresses to meet Bluesky's image limits
4. Posts with a caption including movie title, year, and hashtags

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
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Scripts

```bash
python scripts/manual_post.py      # Post once immediately
python scripts/test_extraction.py   # Extract a frame without posting
python scripts/stats.py             # View posting statistics
```

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

## License

For personal/educational use only. Harry Potter films are property of Warner Bros.
