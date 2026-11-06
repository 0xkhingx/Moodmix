"""Mood-correction feedback store (SQLite, stdlib only).

Each row records what the model predicted and what the user said their mood
actually was. Text is stored only when the user explicitly opts in; audio is
never stored. These rows are the labelled, in-domain data for retraining.

Note: on hosts with an ephemeral filesystem, point FEEDBACK_DB at a mounted
volume (or export regularly via GET /feedback/export) or rows are lost on
redeploy.
"""

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "data" / "feedback.sqlite3"

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    source      TEXT NOT NULL,
    predicted   TEXT NOT NULL,
    corrected   TEXT NOT NULL,
    confidence  REAL,
    text        TEXT
)
"""


def _db_path() -> Path:
    return Path(os.getenv("FEEDBACK_DB", str(DEFAULT_DB)))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(SCHEMA)
    return conn


def add(source: str, predicted: str, corrected: str, confidence: float | None, text: str | None) -> int:
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO feedback (created_at, source, predicted, corrected, confidence, text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                source,
                predicted,
                corrected,
                confidence,
                text,
            ),
        )
        return int(cur.lastrowid)


def export(limit: int = 10_000) -> list[dict]:
    with _lock, _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
