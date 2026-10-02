import os
import sqlite3
from pathlib import Path
import pymysql

MYSQL_HOST = os.getenv("MYSQL_HOST") or "127.0.0.1"
raw_port = (os.getenv("MYSQL_PORT") or "3306").strip()
try:
    MYSQL_PORT = int(raw_port) if raw_port.isdigit() else 3306
except Exception:
    MYSQL_PORT = 3306
MYSQL_USER = os.getenv("MYSQL_USER") or "root"
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD") or ""
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE") or "academic_chatbot"

BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "chatbot.db"


class SQLiteWrapperCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = None

    @property
    def description(self):
        return getattr(self._cursor, "description", None)

    def _clean_sql(self, sql):
        sql_sqlite = sql.replace("%s", "?").replace("INSERT IGNORE", "INSERT OR IGNORE")
        if "ENGINE=" in sql_sqlite.upper():
            import re
            sql_sqlite = re.sub(r"ENGINE=\w+\s*(DEFAULT\s+CHARSET=\w+)?", "", sql_sqlite, flags=re.IGNORECASE)
        sql_sqlite = sql_sqlite.replace("INT AUTO_INCREMENT PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        sql_sqlite = sql_sqlite.replace("AUTO_INCREMENT PRIMARY KEY", "PRIMARY KEY AUTOINCREMENT")
        return sql_sqlite

    def execute(self, sql, params=()):
        sql_sqlite = self._clean_sql(sql)
        res = self._cursor.execute(sql_sqlite, params)
        self.lastrowid = getattr(self._cursor, "lastrowid", None)
        return res

    def executemany(self, sql, seq_params):
        sql_sqlite = self._clean_sql(sql)
        res = self._cursor.executemany(sql_sqlite, seq_params)
        self.lastrowid = getattr(self._cursor, "lastrowid", None)
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
        self._conn.row_factory = sqlite3.Row

    def cursor(self):
        return SQLiteWrapperCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def connect_server():
    kwargs = {
        "host": MYSQL_HOST,
        "port": MYSQL_PORT,
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "charset": "utf8mb4",
        "autocommit": True,
        "connect_timeout": 5,
    }
    if os.getenv("MYSQL_SSL", "false").lower() in ("true", "1", "yes"):
        kwargs["ssl"] = {"ca": None}
    return pymysql.connect(**kwargs)


def ensure_database():
    try:
        conn = connect_server()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
        finally:
            conn.close()
    except Exception as err:
        print(f"[WARN] Could not ensure database creation: {err}")


def connect_db():
    try:
        kwargs = {
            "host": MYSQL_HOST,
            "port": MYSQL_PORT,
            "user": MYSQL_USER,
            "password": MYSQL_PASSWORD,
            "charset": "utf8mb4",
            "autocommit": False,
            "connect_timeout": 3,
        }
        if os.getenv("MYSQL_SSL", "false").lower() in ("true", "1", "yes"):
            kwargs["ssl"] = {"ca": None}

        db_kwargs = dict(kwargs)
        db_kwargs["database"] = MYSQL_DATABASE
        return pymysql.connect(**db_kwargs)
    except Exception as err:
        print(f"[WARN] MySQL connection unavailable ({err}). Falling back to SQLite.", flush=True)

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    return SQLiteWrapperConnection(sqlite_conn)

