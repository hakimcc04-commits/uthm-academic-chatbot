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
def start_bot_worker():
    if os.environ.get("BOT_STARTED") != "1":
        os.environ["BOT_STARTED"] = "1"
        print("[SYSTEM] Starting UTHM Academic Telegram Bot background worker...")
        try:
            subprocess.Popen([sys.executable, "bot.py"], cwd=BASE_DIR)
            print("[SYSTEM] Telegram Bot background worker started successfully.")
        except Exception as err:
            print(f"[ERROR] Could not start Telegram bot worker: {err}")

start_bot_worker()

from reporting_web import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[SYSTEM] Starting UTHM Academic Analytics Web Dashboard on port {port}...")
    app.run(host="0.0.0.0", port=port)
