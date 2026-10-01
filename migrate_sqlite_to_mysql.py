import sqlite3
from pathlib import Path

from db import MYSQL_DATABASE, connect_db
from database import create_tables

SQLITE_PATH = Path(__file__).resolve().parent / "chatbot.db"

TABLES = [
    ("Admin", "admin_id"),
    ("Student", "student_id"),
    ("FAQ", "faq_id"),
    ("User_Query", "query_id"),
    ("Chatbot_Response", "response_id"),
    ("Reports", "report_id"),
]


def fetch_sqlite_rows(table_name):
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        return columns, [tuple(row) for row in rows]
    finally:
        conn.close()


def copy_table(mysql_cursor, table_name, pk_column):
    columns, rows = fetch_sqlite_rows(table_name)
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(f"`{column}`" for column in columns)
    mysql_cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
    existing = mysql_cursor.fetchone()[0]
    if existing:
        print(f"{table_name}: skipped ({existing} rows already in MySQL)")
        return existing

    if rows:
        mysql_cursor.executemany(
            f"INSERT INTO `{table_name}` ({column_sql}) VALUES ({placeholders})",
            rows,
        )

    max_id = 0
    if rows:
        pk_index = columns.index(pk_column)
        max_id = max(row[pk_index] for row in rows if row[pk_index] is not None)
    mysql_cursor.execute(f"ALTER TABLE `{table_name}` AUTO_INCREMENT = {int(max_id) + 1}")
    print(f"{table_name}: copied {len(rows)} rows")
    return len(rows)


def main():
    if not SQLITE_PATH.exists():
        raise SystemExit(f"SQLite file not found: {SQLITE_PATH}")

    create_tables()
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        copied = {}
        for table_name, pk_column in TABLES:
            copied[table_name] = copy_table(cursor, table_name, pk_column)
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"\nMigration complete. Database: {MYSQL_DATABASE}")
    print("Open phpMyAdmin and select academic_chatbot to view the tables.")
    print("SQLite backup kept at chatbot.db")
    for table_name, count in copied.items():
        print(f"  {table_name}: {count}")


if __name__ == "__main__":
    main()
