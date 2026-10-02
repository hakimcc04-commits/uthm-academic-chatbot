#!/bin/bash
echo "[SYSTEM] Installing missing packages in container..."
pip install --no-cache-dir SpeechRecognition pydub

echo "[SYSTEM] Starting UTHM Academic Telegram Bot background worker..."
(python bot.py || python3 bot.py) &

echo "[SYSTEM] Starting Gunicorn Web Dashboard on port ${PORT:-5000}..."
exec gunicorn --bind 0.0.0.0:${PORT:-5000} reporting_web:app
