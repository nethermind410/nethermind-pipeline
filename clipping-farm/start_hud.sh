#!/bin/bash
# Start Clipping Farm HUD with whisper transcriber
# Usage: ./start_hud.sh

cd "$(dirname "$0")"

# Kill any existing HUD
pkill -f "clipping_farm.cli hud" 2>/dev/null
sleep 1

# Start HUD with whisper transcriber
echo "Starting HUD with whisper transcriber..."
CLIP_FARM_TRANSCRIBER=whisper ../.venv/bin/python -m clipping_farm.cli hud --db clipping_farm.db --source-id hud:da11feb3829d &
HUD_PID=$!

# Wait for HUD to be ready
echo "Waiting for HUD to start..."
for i in {1..30}; do
    if curl -sS http://127.0.0.1:8765/ > /dev/null 2>&1; then
        echo ""
        echo "✅ HUD is running at http://127.0.0.1:8765"
        echo "   PID: $HUD_PID"
        echo "   Press Ctrl+C to stop"
        # Open browser
        open http://127.0.0.1:8765 2>/dev/null || xdg-open http://127.0.0.1:8765 2>/dev/null || echo "   Open manually: http://127.0.0.1:8765"
        wait $HUD_PID
        exit 0
    fi
    sleep 1
done

echo "❌ HUD failed to start within 30 seconds"
exit 1
