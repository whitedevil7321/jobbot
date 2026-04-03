@echo off
title JobBot
echo Starting JobBot...
call .venv\Scripts\activate.bat
start "" "http://localhost:8000"
uvicorn backend.main:app --host 127.0.0.1 --port 8000
