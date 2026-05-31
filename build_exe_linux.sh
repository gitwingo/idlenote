#!/bin/bash
set -e
echo "========================================"
echo " IdleNote -- Build Linux Binary"
echo "========================================"

echo "[1/4] Installing system deps..."
sudo apt-get install -y python3-tk python3-pip -q 2>/dev/null || true

echo "[2/4] Installing Python deps..."
pip3 install pynput pystray pillow pyinstaller --break-system-packages -q

echo "[3/4] Building binary..."
pyinstaller --onefile --noconsole --name idlenote \
    --hidden-import pynput.keyboard._xorg \
    --hidden-import pynput.mouse._xorg \
    --hidden-import pystray._gtk \
    idlenote.py

echo "[4/4] Done!"
echo ""
echo "Your binary: dist/idlenote"
echo "Run it: ./dist/idlenote"
