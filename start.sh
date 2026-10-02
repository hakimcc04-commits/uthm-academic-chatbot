#!/bin/bash
echo "[SYSTEM] Starting UTHM Academic Telegram Bot in background process..."
python bot.py &

echo "[SYSTEM] Starting Gunicorn Web Dashboard on port ${PORT:-5000}..."
exec gunicorn --bind 0.0.0.0:${PORT:-5000} reporting_web:app
