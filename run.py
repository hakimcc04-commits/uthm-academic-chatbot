"""Production 24/7 combined entrypoint for UTHM Academic Chatbot & Web Reporting Module.

Starts the Telegram Bot in a background process and serves the Flask Web Dashboard.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Ensure Telegram Bot worker is spawned cleanly
import threading

def run_bot_in_thread():
    try:
        print("[SYSTEM] Starting UTHM Academic Telegram Bot background thread...", flush=True)
        from bot import main as bot_main
        bot_main()
    except Exception as err:
        print(f"[ERROR] Telegram bot background thread error: {err}", flush=True)

def start_bot_worker():
    run_bot_val = str(os.environ.get("RUN_BOT", "0")).strip().lower()
    if run_bot_val in ("1", "true", "yes", "on", "enabled") and os.environ.get("BOT_STARTED") != "1":
        os.environ["BOT_STARTED"] = "1"
        t = threading.Thread(target=run_bot_in_thread, daemon=True)
        t.start()
        print("[SYSTEM] Telegram Bot background thread launched successfully.", flush=True)

start_bot_worker()

from reporting_web import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[SYSTEM] Starting UTHM Academic Analytics Web Dashboard on port {port}...")
    app.run(host="0.0.0.0", port=port)
