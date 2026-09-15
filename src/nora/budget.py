"""An atomic daily request counter; independent of conversation checkpoints."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


class BudgetExceeded(Exception):
    pass


class RequestBudget:
    def __init__(self, path: Path, limit: int):
        self.path = path
        self.limit = limit
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=10)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS requests (day TEXT PRIMARY KEY, count INTEGER NOT NULL)"
            )
        path.chmod(0o600)

    def take(self, *, day: str | None = None) -> int:
        day = day or datetime.now(timezone.utc).date().isoformat()
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT count FROM requests WHERE day=?", (day,)).fetchone()
            count = row[0] if row else 0
            if count >= self.limit:
                raise BudgetExceeded("Daily request limit reached")
            db.execute(
                "INSERT INTO requests(day,count) VALUES (?,?) ON CONFLICT(day) DO UPDATE SET count=excluded.count",
                (day, count + 1),
            )
            db.execute("DELETE FROM requests WHERE day < ?", (day,))
            return count + 1
