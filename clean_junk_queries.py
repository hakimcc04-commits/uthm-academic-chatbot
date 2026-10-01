import sqlite3
import pymysql
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "chatbot.db"

def is_academic(q):
    q_str = str(q or "").strip().lower()
    junk_words = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "yes", "no", "ok", "okay", "hi", "hello", "test", "tq", "thanks"}
    if q_str in junk_words or len(q_str) < 8 or q_str.isdigit():
        return False
    return True

# 1. Clean SQLite
if SQLITE_PATH.exists():
    conn = sqlite3.connect(SQLITE_PATH)
    cur = conn.cursor()
    cur.execute("SELECT query_id, user_question FROM User_Query WHERE status = 'unanswered'")
    rows = cur.fetchall()
    cleaned = 0
    for q_id, q_text in rows:
        if not is_academic(q_text):
            cur.execute("UPDATE User_Query SET status = 'ignored_non_question' WHERE query_id = ?", (q_id,))
            cleaned += 1
    conn.commit()
    conn.close()
    print(f"SQLite: Cleaned {cleaned} junk unanswered queries from chatbot.db.")

# 2. Clean MySQL (if running on XAMPP)
try:
    from db import connect_db
    m_conn = connect_db()
    m_cur = m_conn.cursor()
    m_cur.execute("SELECT query_id, user_question FROM User_Query WHERE status = 'unanswered'")
    m_rows = m_cur.fetchall()
    m_cleaned = 0
    for q_id, q_text in m_rows:
        if not is_academic(q_text):
            m_cur.execute("UPDATE User_Query SET status = 'ignored_non_question' WHERE query_id = %s", (q_id,))
            m_cleaned += 1
    m_conn.commit()
    m_conn.close()
    print(f"MySQL: Cleaned {m_cleaned} junk unanswered queries from MySQL database.")
except Exception as err:
    print("MySQL cleanup skipped (offline):", err)
