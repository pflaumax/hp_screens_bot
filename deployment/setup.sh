#!/usr/bin/env bash
# Automated Raspberry Pi setup for the Harry Potter Screengrab Bot.
set -euo pipefail

BOT_DIR="/home/pi/harry-potter-screengrab-bot"
SERVICE_NAME="hp-screengrab-bot"

echo "=== Harry Potter Screengrab Bot — Raspberry Pi Setup ==="

# 1. System packages
echo "[1/6] Installing system dependencies..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv
sudo apt install -y exfat-fuse exfat-utils

# 2. Virtual environment
echo "[2/6] Creating Python virtual environment..."
python3 -m venv "$BOT_DIR/venv"
source "$BOT_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$BOT_DIR/requirements.txt"

# 3. Directories
echo "[3/6] Creating runtime directories..."
mkdir -p "$BOT_DIR/temp" "$BOT_DIR/logs" "$BOT_DIR/data"

# 4. Environment file
echo "[4/6] Setting up environment file..."
if [ ! -f "$BOT_DIR/.env" ]; then
    cp "$BOT_DIR/.env.example" "$BOT_DIR/.env"
    echo "  → Created .env from template. Please edit it with your credentials:"
    echo "    nano $BOT_DIR/.env"
else
    echo "  → .env already exists, skipping."
fi

# 5. Logrotate
echo "[5/6] Configuring logrotate..."
sudo tee /etc/logrotate.d/$SERVICE_NAME > /dev/null <<EOF
$BOT_DIR/logs/bot.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
EOF

# 6. Systemd service
echo "[6/6] Installing systemd service..."
sudo cp "$BOT_DIR/deployment/$SERVICE_NAME.service" "/etc/systemd/system/"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME.service"

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Edit your credentials:  nano $BOT_DIR/.env"
echo "  2. Mount your screenshots at: /mnt/hp_screenshots"
echo "  3. Start the bot:          sudo systemctl start $SERVICE_NAME"
echo "  4. Check status:           sudo systemctl status $SERVICE_NAME"
echo "  5. View logs:              tail -f $BOT_DIR/logs/bot.log"
