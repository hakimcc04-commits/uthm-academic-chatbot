"""Production 24/7 combined entrypoint for UTHM Academic Chatbot & Web Reporting Module.

Starts the Telegram Bot in a background subprocess and serves the Flask Web Dashboard.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def start_bot_worker():
    run_bot_val = str(os.environ.get("RUN_BOT", "0")).strip().lower()
    if run_bot_val not in ("1", "true", "yes", "on", "enabled"):
        print("[SYSTEM] Telegram Bot worker disabled (RUN_BOT is not set to 1).", flush=True)
        return

    if os.environ.get("BOT_STARTED") == "1":
        return

    # Use a localhost socket lock to ensure only ONE bot subprocess is started even with multiple Gunicorn workers
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(("127.0.0.1", 50099))
        globals()["_bot_lock_socket"] = lock_socket
    except OSError:
        print("[SYSTEM] Bot process lock active in another worker. Skipping duplicate launch.", flush=True)
        return

    os.environ["BOT_STARTED"] = "1"
    print("[SYSTEM] Starting UTHM Academic Telegram Bot subprocess...", flush=True)
    try:
        proc = subprocess.Popen([sys.executable, "bot.py"], cwd=str(BASE_DIR))
        print(f"[SYSTEM] Telegram Bot subprocess launched successfully (PID: {proc.pid}).", flush=True)
    except Exception as err:
        print(f"[ERROR] Failed to start Telegram bot subprocess: {err}", flush=True)


start_bot_worker()

from reporting_web import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[SYSTEM] Starting UTHM Academic Analytics Web Dashboard on port {port}...")
    app.run(host="0.0.0.0", port=port)
