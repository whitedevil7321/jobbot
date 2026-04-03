#!/bin/bash
source .venv/bin/activate
echo "Starting JobBot at http://localhost:8000"
# Open browser
(sleep 2 && open "http://localhost:8000" 2>/dev/null || xdg-open "http://localhost:8000" 2>/dev/null) &
uvicorn backend.main:app --host 127.0.0.1 --port 8000
