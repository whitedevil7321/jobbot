#!/bin/bash
set -e

echo "============================================================"
echo "  JobBot - Automated Job Application Platform"
echo "============================================================"
echo

# Check dependencies
command -v python3 >/dev/null 2>&1 || { echo "[ERROR] Python 3 not found. Install from https://python.org"; exit 1; }
echo "[OK] Python found: $(python3 --version)"

command -v node >/dev/null 2>&1 || { echo "[ERROR] Node.js not found. Install from https://nodejs.org"; exit 1; }
echo "[OK] Node.js found: $(node --version)"

command -v ollama >/dev/null 2>&1 && echo "[OK] Ollama found" || echo "[WARN] Ollama not found — install from https://ollama.ai"

echo
echo "[1/6] Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo
echo "[2/6] Installing Python dependencies..."
pip install -r requirements.txt -q

echo
echo "[3/6] Installing Playwright browsers..."
playwright install chromium || echo "[WARN] Playwright browser install failed"

echo
echo "[4/6] Building React frontend..."
cd frontend
npm install --silent
npm run build
cd ..

echo
echo "[5/6] Initializing database..."
python backend/migrations/init_db.py

echo
echo "[6/6] Pulling default Ollama model (llama3)..."
ollama pull llama3 2>/dev/null || echo "[WARN] Could not pull llama3. Pull manually: ollama pull llama3"

# Copy .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo
    echo "[!] Created .env file. Edit it to add your Telegram bot token."
fi

echo
echo "============================================================"
echo "  Installation complete!"
echo
echo "  Start JobBot:  ./start.sh"
echo "  Then open:     http://localhost:8000"
echo "============================================================"
