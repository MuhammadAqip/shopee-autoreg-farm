"""Store for farmed Shopee accounts -- SQLite, resumable, dedup on device id."""
import sqlite3
import json
import time
import os

DB = os.environ.get("FARM_DB", "/root/shopee-farm/accounts.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    phone         TEXT UNIQUE,
    password      TEXT,
    name          TEXT,
    email         TEXT,
    device_json   TEXT,
    proxy         TEXT,
    status        TEXT DEFAULT 'pending',   -- pending | otp_sent | active | banned
    access_token  TEXT,
    cookie_json   TEXT,
    error         TEXT,
    created_at    REAL,
    updated_at    REAL
);
CREATE INDEX IF NOT EXISTS idx_status ON accounts(status);
CREATE INDEX IF NOT EXISTS idx_phone  ON accounts(phone);
"""


class Store:
    def __init__(self, db_path: str = DB):
        self.db = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with sqlite3.connect(self.db) as c:
            c.executescript(SCHEMA)

    def _conn(self):
        c = sqlite3.connect(self.db)
        c.row_factory = sqlite3.Row
        return c

    def insert(self, profile: dict, device: dict, proxy: str | None) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT OR IGNORE INTO accounts
                   (phone,password,name,email,device_json,proxy,status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (profile["phone"], profile["password"], profile["name"],
                 profile.get("email"), json.dumps(device), proxy,
                 "pending", time.time(), time.time()),
            )
            return cur.lastrowid

    def update(self, phone: str, **fields):
        if not fields:
            return
        fields["updated_at"] = time.time()
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._conn() as c:
            c.execute(f"UPDATE accounts SET {cols} WHERE phone=?", (*fields.values(), phone))

    def get(self, phone: str):
        with self._conn() as c:
            r = c.execute("SELECT * FROM accounts WHERE phone=?", (phone,)).fetchone()
            return dict(r) if r else None

    def by_status(self, status: str):
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM accounts WHERE status=?", (status,)).fetchall()]

    def all(self):
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM accounts ORDER BY id").fetchall()]

    def stats(self) -> dict:
        with self._conn() as c:
            rows = c.execute("SELECT status, COUNT(*) n FROM accounts GROUP BY status").fetchall()
            return {r["status"]: r["n"] for r in rows}


if __name__ == "__main__":
    s = Store()
    print("stats:", s.stats())
