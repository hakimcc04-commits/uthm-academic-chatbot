import os
import sqlite3
from pathlib import Path
import pymysql

# Default XAMPP / phpMyAdmin login. Override with environment variables if needed.
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "academic_chatbot")

BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "chatbot.db"


class SQLiteWrapperCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = None

    def execute(self, sql, params=()):
        sql_sqlite = sql.replace("%s", "?").replace("INSERT IGNORE", "INSERT OR IGNORE")
        res = self._cursor.execute(sql_sqlite, params)
        self.lastrowid = self._cursor.lastrowid
        return res

    def executemany(self, sql, seq_params):
        sql_sqlite = sql.replace("%s", "?").replace("INSERT IGNORE", "INSERT OR IGNORE")
        res = self._cursor.executemany(sql_sqlite, seq_params)
        self.lastrowid = self._cursor.lastrowid
        return res

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        self._cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class SQLiteWrapperConnection:
    def __init__(self, sqlite_conn):
        self._conn = sqlite_conn

    def cursor(self):
        return SQLiteWrapperCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def connect_server():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
    )


def ensure_database():
    conn = connect_server()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        conn.close()


def connect_db():
    try:
        ensure_database()
        kwargs = {
            "host": MYSQL_HOST,
            "port": MYSQL_PORT,
            "user": MYSQL_USER,
            "password": MYSQL_PASSWORD,
            "database": MYSQL_DATABASE,
            "charset": "utf8mb4",
            "autocommit": False,
        }
        if os.getenv("MYSQL_SSL", "false").lower() in ("true", "1", "yes"):
            kwargs["ssl"] = {"ca": None}
        return pymysql.connect(**kwargs)
    except Exception:
        # Fallback to local SQLite database if MySQL (XAMPP/Cloud) is offline
        sqlite_conn = sqlite3.connect(SQLITE_PATH)
        return SQLiteWrapperConnection(sqlite_conn)

