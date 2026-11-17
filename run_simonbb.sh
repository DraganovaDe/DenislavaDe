#!/usr/bin/env bash
# Start WebLog Observatory on the CIS438 app server.
# Registered app: path WeblogDraganovaDe · host crait10 · port 49153
#   → https://simonbb.com/app/WeblogDraganovaDe/
#
# Usage:   bash run_simonbb.sh          (start / restart)
#          bash run_simonbb.sh stop     (stop)
# If the page loads blank, try:  BASE="" bash run_simonbb.sh
set -e
cd "$(dirname "$0")"

PORT="${PORT:-49153}"
BASE="${BASE-app/WeblogDraganovaDe}"

# Stop any copy that is already running on this port
pkill -f "streamlit run app.py --server.port $PORT" 2>/dev/null || true
[ "$1" = "stop" ] && { echo "Stopped."; exit 0; }

# One-time setup: private Python environment with the app's packages
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

nohup streamlit run app.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.baseUrlPath "$BASE" \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  > streamlit.log 2>&1 &

sleep 5
if curl -s "http://localhost:$PORT/${BASE:+$BASE/}_stcore/health" | grep -q ok; then
  echo "✅ Running on $(hostname):$PORT  →  https://simonbb.com/app/WeblogDraganovaDe/"
else
  echo "⚠️  Not answering yet. Check the log:  tail -n 30 $(pwd)/streamlit.log"
fi
