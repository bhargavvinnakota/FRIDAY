#!/bin/bash
# F.R.I.D.A.Y. Master Launcher

FRIDAY_DIR="/Users/bhargav/AI/friday"
LOG_DIR="$FRIDAY_DIR/logs"
mkdir -p "$LOG_DIR"

echo "Stopping existing services..."
pkill -f "FridayHUD"
pkill -f "v2_voice_streaming"

echo "Initializing State..."
"$FRIDAY_DIR/venv/bin/python3" "$FRIDAY_DIR/brain/state_relay.py"

echo "Launching Native HUD..."
open "$FRIDAY_DIR/native_hud/Build/FridayHUD.app"

echo "Launching Voice Backend..."
export PYTHONPATH="$PYTHONPATH:/Users/bhargav/AI"
nohup "$FRIDAY_DIR/venv/bin/python3" "$FRIDAY_DIR/senses/v2_voice_streaming.py" > "$LOG_DIR/voice.log" 2>&1 &

echo "Services started. Checking status..."
sleep 3
ps aux | grep -E "FridayHUD|v2_voice_streaming" | grep -v grep
