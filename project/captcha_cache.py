#!/usr/bin/env python3
"""captcha_cache.py — DB cache untuk Shopee captcha yang BERHASIL tersolve.

FIX v2 (2026-10-16):
  - Lookup by **CONTENT MATCH puzzle-only** (bukan sha256(puzzle+piece)).
    Alasan: piece_b64 bisa beda tiap render (anti-aliasing/DPR), bikin hash
    mismatch walau puzzle SAMA → cache selalu miss. Puzzle image-lah yang
    menentukan solusi, jadi match cukup di puzzle_b64.
  - WAL mode (reader tidak diblok writer).
  - Kolom `verified` (dari hits) + `prune()` untuk bersihkan entry basi.

Skema:
  puzzles(puzzle_b64 TEXT PRIMARY KEY, hash TEXT, piece_b64 TEXT,
          target REAL, hits INTEGER, misses INTEGER, verified INTEGER,
          created REAL, last_used REAL)

Pemakaian:
  cc = CaptchaCache()
  hit = cc.lookup(puzzle_b64)                 # → target (float 0..1) atau None
  cc.record(puzzle_b64, piece_b64, target)    # simpan solusi (proporsional)
  cc.mark_result(puzzle_b64, ok=True/False)
"""
import hashlib
import os
import sqlite3
import time

DB = "/root/shopee-farm/captcha_cache.db"
VERIFIED_HITS = 2          # hits >= N → entry 'verified' (boleh dipakai tanpa ragu)
DEFAULT_MAX_AGE_DAYS = 30  # prune entry lebih tua dari ini


def _canon_puzzle(puzzle_b64: str) -> str:
    """Kanonikalisasi puzzle: strip whitespace + samakan padding b64."""
    s = (puzzle_b64 or "").strip()
    # buang prefix data-url kalau ada
    if s.startswith("data:") and "," in s[:80]:
        s = s.split(",", 1)[1]
    # buang whitespace internal (b64 tidak boleh ada newline)
    s = "".join(s.split())
    return s


def _hash(puzzle_b64: str) -> str:
    return hashlib.sha256(_canon_puzzle(puzzle_b64).encode()).hexdigest()


class CaptchaCache:
    def __init__(self, db=DB):
        self.db = db
        self._init()

    def _con(self):
        con = sqlite3.connect(self.db, timeout=15)
        con.execute("PRAGMA busy_timeout=10000")
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init(self):
        con = self._con()
        con.execute("""CREATE TABLE IF NOT EXISTS puzzles(
            puzzle_b64 TEXT PRIMARY KEY,
            hash TEXT,
            piece_b64 TEXT,
            target REAL,
            hits INTEGER DEFAULT 0,
            misses INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0,
            created REAL,
            last_used REAL
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_hash ON puzzles(hash)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_used ON puzzles(last_used)")
        con.commit()
        con.close()

    def lookup(self, puzzle_b64: str, piece_b64: str = ""):
        """Return target proporsional (0..1) atau None. Content-match di puzzle.

        `piece_b64` sengaja DIABAIKAN untuk pencocokan (lihat docstring modul),
        tapi diterima supaya call-site lama tetap kompatibel.
        """
        if not puzzle_b64:
            return None
        key = _canon_puzzle(puzzle_b64)
        con = self._con()
        row = con.execute(
            "SELECT target FROM puzzles WHERE puzzle_b64=? AND target IS NOT NULL LIMIT 1",
            (key,),
        ).fetchone()
        if row is not None:
            con.execute("UPDATE puzzles SET last_used=? WHERE puzzle_b64=?", (time.time(), key))
            con.commit()
            con.close()
            return float(row[0])
        # fallback: hash match (untuk entry lama sebelum migrasi)
        h = _hash(puzzle_b64)
        row = con.execute(
            "SELECT target FROM puzzles WHERE hash=? AND target IS NOT NULL LIMIT 1", (h,)
        ).fetchone()
        con.close()
        return float(row[0]) if (row and row[0] is not None) else None

    def record(self, puzzle_b64: str, piece_b64: str, target):
        """Upsert solusi. `target` = proporsional (target_px / bar_width)."""
        if not puzzle_b64 or target is None:
            return
        key = _canon_puzzle(puzzle_b64)
        now = time.time()
        con = self._con()
        con.execute("""INSERT INTO puzzles(puzzle_b64, hash, piece_b64, target, created, last_used, verified)
                       VALUES(?,?,?,?,?,?,0)
                       ON CONFLICT(puzzle_b64) DO UPDATE SET
                         target=excluded.target,
                         piece_b64=excluded.piece_b64,
                         last_used=excluded.last_used""",
                    (key, _hash(puzzle_b64), piece_b64, float(target), now, now))
        con.commit()
        con.close()

    def mark_result(self, puzzle_b64: str, piece_b64: str = "", ok: bool = True):
        """ok=True → hits+1 (verified kalau >= VERIFIED_HITS).
        ok=False → misses+1 dan HAPUS entry (solusi terbukti salah)."""
        if not puzzle_b64:
            return
        key = _canon_puzzle(puzzle_b64)
        con = self._con()
        if ok:
            con.execute("UPDATE puzzles SET hits=hits+1, last_used=? WHERE puzzle_b64=?",
                        (time.time(), key))
            con.execute("UPDATE puzzles SET verified=1 WHERE puzzle_b64=? AND hits>=?",
                        (key, VERIFIED_HITS))
        else:
            con.execute("UPDATE puzzles SET misses=misses+1 WHERE puzzle_b64=?", (key,))
            con.execute("DELETE FROM puzzles WHERE puzzle_b64=?", (key,))
        con.commit()
        con.close()

    def prune(self, max_age_days: float = DEFAULT_MAX_AGE_DAYS):
        """Buang entry basi (last_used lebih tua) — hemat disk. Return jumlah dihapus."""
        cutoff = time.time() - max_age_days * 86400
        con = self._con()
        n = con.execute("SELECT COUNT(*) FROM puzzles WHERE COALESCE(last_used,created) < ?",
                        (cutoff,)).fetchone()[0]
        con.execute("DELETE FROM puzzles WHERE COALESCE(last_used,created) < ?", (cutoff,))
        con.commit()
        con.close()
        return int(n)

    def stats(self):
        con = self._con()
        n, hits, misses, ver = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(hits),0), COALESCE(SUM(misses),0), "
            "COALESCE(SUM(verified),0) FROM puzzles").fetchone()
        used = con.execute("SELECT COUNT(*) FROM puzzles WHERE hits>0").fetchone()[0]
        con.close()
        return {"entries": int(n), "total_hits": int(hits), "total_misses": int(misses),
                "verified": int(ver), "ever_hit": int(used)}

    def export(self, path=None):
        import json
        path = path or "/root/shopee-farm/captcha_cache_export.json"
        con = self._con()
        rows = con.execute(
            "SELECT puzzle_b64,piece_b64,target,hits,misses,verified FROM puzzles").fetchall()
        con.close()
        data = [{"puzzle_b64": r[0], "piece_b64": r[1], "target": r[2],
                 "hits": r[3], "misses": r[4], "verified": r[5]} for r in rows]
        with open(path, "w") as f:
            json.dump(data, f)
        return len(data)


if __name__ == "__main__":
    import sys
    cc = CaptchaCache()
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(cc.stats())
    elif len(sys.argv) > 1 and sys.argv[1] == "prune":
        days = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_MAX_AGE_DAYS
        print(f"pruned: {cc.prune(days)}")
    elif len(sys.argv) > 1 and sys.argv[1] == "export":
        print("exported:", cc.export())
    else:
        print("usage: captcha_cache.py stats|prune [days]|export")
