#!/usr/bin/env bash
# ============================================================
# FRIDAY :: INSTALL SCRIPT
# Sets up venv, installs deps, verifies boot.
# ============================================================
set -e

FRIDAY_HOME="$HOME/AI/friday"
cd "$FRIDAY_HOME"

echo "╔══════════════════════════════════════╗"
echo "║  FRIDAY :: INSTALL                   ║"
echo "╚══════════════════════════════════════╝"

# 1. Python venv
if [ ! -d "venv" ]; then
    echo "[1/4] Creating venv..."
    python3 -m venv venv
else
    echo "[1/4] venv exists ✓"
fi

source venv/bin/activate

# 2. Dependencies (minimal — Friday uses urllib/stdlib)
echo "[2/4] Installing deps (PyYAML + certifi)..."
pip install --quiet --upgrade pip
pip install --quiet PyYAML certifi

# 3. Make CLI executable
echo "[3/4] Making friday executable..."
chmod +x "$FRIDAY_HOME/cli.py"
chmod +x "$FRIDAY_HOME/daemon.py"

# 4. Add `friday` alias
ALIAS_LINE="alias friday='$FRIDAY_HOME/venv/bin/python3 $FRIDAY_HOME/cli.py'"
for rc in ~/.zshrc ~/.bashrc ~/.bash_profile; do
    if [ -f "$rc" ]; then
        if ! grep -q "alias friday=" "$rc"; then
            echo "" >> "$rc"
            echo "# Friday sovereign AI" >> "$rc"
            echo "$ALIAS_LINE" >> "$rc"
            echo "   added alias to $rc"
        fi
    fi
done

echo "[4/4] Running boot test..."
python3 "$FRIDAY_HOME/cli.py" test

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  ✓ FRIDAY INSTALLED                  ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Try:"
echo "   friday ask \"status check\""
echo "   friday chat"
echo "   friday briefing"
echo "   python3 ~/AI/friday/daemon.py   # launch 24/7"
echo ""
echo "Or run as PM2 service:"
echo "   pm2 start ~/AI/friday/daemon.py --interpreter python3 --name friday"
echo "   pm2 save"
echo "   pm2 startup   # auto-boot on login"
