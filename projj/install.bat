@echo off
title JobBot Installer
echo ============================================================
echo   JobBot - Automated Job Application Platform
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause & exit /b 1
)
echo [OK] Python found

:: Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install from https://nodejs.org
    pause & exit /b 1
)
echo [OK] Node.js found

:: Check Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Ollama not found. Install from https://ollama.ai
    echo        You can still use JobBot without LLM features.
) else (
    echo [OK] Ollama found
)

echo.
echo [1/5] Creating Python virtual environment...
python -m venv .venv
call .venv\Scripts\activate.bat

echo.
echo [2/5] Installing Python dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 ( echo [ERROR] pip install failed & pause & exit /b 1 )

echo.
echo [3/5] Installing Playwright browsers...
playwright install chromium
if errorlevel 1 ( echo [WARN] Playwright browser install failed. Browser automation may not work. )

echo.
echo [4/5] Building React frontend...
cd frontend
npm install --silent
npm run build
if errorlevel 1 ( echo [ERROR] Frontend build failed & pause & exit /b 1 )
cd ..

echo.
echo [5/5] Initializing database...
python backend/migrations/init_db.py

:: Copy .env if not exists
if not exist .env (
    copy .env.example .env
    echo.
    echo [!] Created .env file. Edit it to add your Telegram bot token.
)

echo.
echo ============================================================
echo   Installation complete!
echo.
echo   To start JobBot, run:   start.bat
echo   Then open:              http://localhost:8000
echo ============================================================
pause
