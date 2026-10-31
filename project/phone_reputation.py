#!/usr/bin/env python3
"""phone_reputation.py — P1b: reputasi nomor (pre-check anti-LIMIT).

Tujuan: sebelum coba daftar, tolak nomor yang kemungkinan besar kena
"Identifikasi Tambahan" (LIMIT). Belajar dari hasil sebelumnya.

Aturan:
  - Track per NOMOR dan per PREFIX (4 digit pertama setelah 62).
  - Nomor sukses → reputasi naik. Nomor LIMIT → turun.
  - Kalau prefix punya limit-rate tinggi → TOLAK nomor baru dari prefix itu.
  - Nomor yang pernah sukses/terpakai → skip (sudah ada akun).

DB: phone_rep.db
  phones(phone TEXT PK, prefix TEXT, status TEXT, tries INT, created REAL, updated REAL)
  prefixes(prefix TEXT PK, ok INT, limit INT, fail INT, updated REAL)

API:
  rep = PhoneReputation()
  rep.allow(phone) -> (bool, reason)
  rep.record(phone, status)   # status in {ok, limit, fail}
  rep.prefix_stats(prefix) -> dict
"""
import os
import sqlite3
import time

DB = "/root/shopee-farm/phone_rep.db"
PREFIX_LEN = 4              # 6283|1924... → prefix "8319" (4 digit setelah 62)
MIN_PREFIX_SAMPLES = 3      # minimal N sampel sebelum prefix dinilai
LIMIT_RATE_BLOCK = 0.60     # prefix dgn limit-rate >= 60% → block


def norm_phone(phone: str) -> str:
    """Normalisasi ke 62xxxxxxxxxx."""
    s = "".join(ch for ch in str(phone) if ch.isdigit())
    if s.startswith("0"):
        s = "62" + s[1:]
    if not s.startswith("62"):
        s = "62" + s
    return s


def prefix_of(phone: str) -> str:
    s = norm_phone(phone)
    return s[2:2 + PREFIX_LEN]


class PhoneReputation:
    def __init__(self, db=DB):
        self.db = db
        self._init()

    def _con(self):
        c = sqlite3.connect(self.db, timeout=15)
        c.execute("PRAGMA busy_timeout=10000")
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _init(self):
        c = self._con()
        c.execute("""CREATE TABLE IF NOT EXISTS phones(
            phone TEXT PRIMARY KEY, prefix TEXT, status TEXT, tries INTEGER DEFAULT 0,
            created REAL, updated REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS prefixes(
            prefix TEXT PRIMARY KEY, ok INTEGER DEFAULT 0, lim INTEGER DEFAULT 0,
            fail INTEGER DEFAULT 0, updated REAL)""")
        c.commit()
        c.close()

    def allow(self, phone: str):
        """Return (allowed: bool, reason: str)."""
        p = norm_phone(phone)
        pfx = prefix_of(p)
        c = self._con()
        row = c.execute("SELECT status, tries FROM phones WHERE phone=?", (p,)).fetchone()
        pr = c.execute("SELECT ok,lim,fail FROM prefixes WHERE prefix=?", (pfx,)).fetchone()
        c.close()
        if row:
            st, tries = row
            if st == "ok":
                return False, f"nomor sudah pernah sukses (akun ada)"
            if st == "limit" and tries >= 2:
                return False, f"nomor limit {tries}x — skip"
        if pr:
            ok, lim, fail = pr
            n = ok + lim + fail
            if n >= MIN_PREFIX_SAMPLES:
                lr = lim / n
                if lr >= LIMIT_RATE_BLOCK:
                    return False, f"prefix {pfx} limit-rate {lr*100:.0f}% ({n} sampel) — block"
        return True, "ok"

    def record(self, phone: str, status: str):
        """status in {ok, limit, fail}."""
        p = norm_phone(phone)
        pfx = prefix_of(p)
        col = {"ok": "ok", "limit": "lim", "fail": "fail"}.get(status, "fail")
        now = time.time()
        c = self._con()
        c.execute("""INSERT INTO phones(phone,prefix,status,tries,created,updated)
                     VALUES(?,?,?,1,?,?)
                     ON CONFLICT(phone) DO UPDATE SET status=excluded.status,
                       tries=tries+1, updated=excluded.updated""", (p, pfx, status, now, now))
        c.execute("""INSERT INTO prefixes(prefix,ok,lim,fail,updated) VALUES(?,?,?,?,?)
                     ON CONFLICT(prefix) DO UPDATE SET {}= {}+1, updated=excluded.updated""".format(
                     col, col), (pfx, 1 if col == "ok" else 0, 1 if col == "lim" else 0,
                                 1 if col == "fail" else 0, now))
        c.commit()
        c.close()

    def prefix_stats(self, prefix: str):
        c = self._con()
        r = c.execute("SELECT ok,lim,fail FROM prefixes WHERE prefix=?", (prefix,)).fetchone()
        c.close()
        if not r:
            return {"prefix": prefix, "samples": 0}
        ok, lim, fail = r
        n = ok + lim + fail or 1
        return {"prefix": prefix, "ok": ok, "limit": lim, "fail": fail,
                "samples": n, "limit_rate": round(lim / n, 3), "ok_rate": round(ok / n, 3)}

    def top_blocked(self, k=10):
        c = self._con()
        rows = c.execute("SELECT prefix,ok,lim,fail FROM prefixes WHERE (ok+lim+fail)>=? "
                         "ORDER BY CAST(lim AS REAL)/(ok+lim+fail) DESC LIMIT ?",
                         (MIN_PREFIX_SAMPLES, k)).fetchall()
        c.close()
        return [{"prefix": r[0], "ok": r[1], "limit": r[2], "fail": r[3],
                 "limit_rate": round(r[2] / (r[1] + r[2] + r[3]), 3)} for r in rows]


if __name__ == "__main__":
    import sys
    rep = PhoneReputation()
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        print(rep.allow(sys.argv[2]))
    elif len(sys.argv) > 1 and sys.argv[1] == "record":
        rep.record(sys.argv[2], sys.argv[3]); print("recorded")
    elif len(sys.argv) > 1 and sys.argv[1] == "blocked":
        for b in rep.top_blocked(): print(b)
    else:
        print("usage: phone_reputation.py check <phone>|record <phone> <ok|limit|fail>|blocked")
