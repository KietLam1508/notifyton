"""Kết nối SQLite và các hàm truy vấn tiện ích."""
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SKYLINE_DATA", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
SCHEMA = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")


def db_path() -> str:
    return os.environ.get("SKYLINE_DB", str(DATA_DIR / "skyline.db"))


def connect(path: str | None = None) -> sqlite3.Connection:
    path = path or db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, detect_types=0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def q(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def q1(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def val(conn, sql, params=(), default=None):
    row = conn.execute(sql, params).fetchone()
    if row is None or row[0] is None:
        return default
    return row[0]


def insert(conn, table: str, data: dict) -> int:
    cols = ", ".join(data.keys())
    marks = ", ".join("?" for _ in data)
    cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values()))
    return cur.lastrowid


def update(conn, table: str, key: str, key_val, data: dict) -> None:
    sets = ", ".join(f"{k} = ?" for k in data)
    conn.execute(f"UPDATE {table} SET {sets} WHERE {key} = ?", (*data.values(), key_val))


def row_dict(row) -> dict | None:
    return dict(row) if row is not None else None
