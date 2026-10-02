#!/bin/bash
echo "[SYSTEM] Starting UTHM Academic Telegram Bot 24/7 background worker..."
python bot.py &

echo "[SYSTEM] Starting Gunicorn Web Dashboard on port ${PORT:-8080}..."
exec gunicorn --bind 0.0.0.0:${PORT:-8080} reporting_web:app
