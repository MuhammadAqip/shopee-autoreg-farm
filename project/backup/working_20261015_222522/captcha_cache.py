#!/usr/bin/env python3
"""captcha_cache.py — DB cache untuk Shopee captcha yang BERHASIL tersolve.

Ide: puzzle Shopee image_crawl itu REUSE. Puzzle sama (hash image sama) →
solusi (pixelsFromSliderOrigin) sama. Simpan → skip SadCaptcha → hemat kredit.

Skema:
  puzzles(hash TEXT PK, puzzle_b64 TEXT, piece_b64 TEXT,
          target INTEGER, hits INTEGER, misses INTEGER,
          created REAL, last_used REAL)

Pemakaian:
  from captcha_cache import CaptchaCache
  cc = CaptchaCache()
  hit = cc.lookup(puzzle_b64)          # → target (int) atau None
  cc.record(puzzle_b64, piece_b64, target)   # simpan solusi
  cc.mark_result(puzzle_b64, ok)       # ok=True → naikkan hits, False → miss

Aturan aman:
  - Kalau puzzle sama muncul tapi solusi LAMA gagal (miss), langsung DELETE entry.
  - Kalau hits >= 2, entry dianggap "verified" (boleh dipakai tanpa ragu).
"""
import os, time, sqlite3, hashlib, base64

DB = "/root/shopee-farm/captcha_cache.db"


def _hash(puzzle_b64: str) -> str:
    """Hash puzzle image (strip whitespace biar stabil)."""
    return hashlib.sha256(puzzle_b64.strip().encode()).hexdigest()


def _hash2(puzzle_b64: str, piece_b64: str) -> str:
    """Hash puzzle+piece (lebih spesifik; piece beda = puzzle beda)."""
    h = hashlib.sha256()
    h.update(puzzle_b64.strip().encode())
    h.update(b"|")
    h.update((piece_b64 or "").strip().encode())
    return h.hexdigest()


class CaptchaCache:
    def __init__(self, db=DB):
        self.db = db
        self._init()

    def _init(self):
        con = sqlite3.connect(self.db)
        con.execute("""CREATE TABLE IF NOT EXISTS puzzles(
            hash TEXT PRIMARY KEY,
            puzzle_b64 TEXT,
            piece_b64 TEXT,
            target REAL,
            hits INTEGER DEFAULT 0,
            misses INTEGER DEFAULT 0,
            created REAL,
            last_used REAL
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_hash ON puzzles(hash)")
        con.commit()
        con.close()

    def lookup(self, puzzle_b64: str, piece_b64: str = ""):
        """Return target (float proporsional 0..1) atau None. Naikkan counter 'used'."""
        h = _hash2(puzzle_b64, piece_b64)
        con = sqlite3.connect(self.db)
        row = con.execute("SELECT target FROM puzzles WHERE hash=?", (h,)).fetchone()
        if row is not None and row[0] is not None:
            con.execute("UPDATE puzzles SET last_used=? WHERE hash=?", (time.time(), h))
            con.commit()
            con.close()
            return float(row[0])
        con.close()
        return None

    def record(self, puzzle_b64: str, piece_b64: str, target):
        """Simpan solusi baru (upsert). target = pixelsFromSliderOrigin.

        PENTING: simpan sebagai PROPORSIONAL (target/bar_width, float 0..1)
        supaya tahan terhadap beda lebar viewport/canvas.
        """
        h = _hash2(puzzle_b64, piece_b64)
        con = sqlite3.connect(self.db)
        now = time.time()
        con.execute("""INSERT INTO puzzles(hash, puzzle_b64, piece_b64, target, created, last_used)
                       VALUES(?,?,?,?,?,?)
                       ON CONFLICT(hash) DO UPDATE SET
                         target=excluded.target, last_used=excluded.last_used""",
                    (h, puzzle_b64, piece_b64, float(target), now, now))
        con.commit()
        con.close()

    def mark_result(self, puzzle_b64: str, piece_b64: str, ok: bool):
        """ok=True → naikkan hits. ok=False → naikkan misses + HAPUS entry (solusi salah)."""
        h = _hash2(puzzle_b64, piece_b64)
        con = sqlite3.connect(self.db)
        if ok:
            con.execute("UPDATE puzzles SET hits=hits+1, last_used=? WHERE hash=?", (time.time(), h))
        else:
            con.execute("UPDATE puzzles SET misses=misses+1 WHERE hash=?", (h,))
            # solusi terbukti salah → buang, biar next time re-solve
            con.execute("DELETE FROM puzzles WHERE hash=?", (h,))
        con.commit()
        con.close()

    def stats(self):
        con = sqlite3.connect(self.db)
        n, hits = con.execute("SELECT COUNT(*), COALESCE(SUM(hits),0) FROM puzzles").fetchone()
        con.close()
        return {"entries": n, "total_hits": int(hits)}

    def export(self, path=None):
        """Dump semua entry ke JSON (backup / share antar VPS)."""
        import json
        path = path or "/root/shopee-farm/captcha_cache_export.json"
        con = sqlite3.connect(self.db)
        rows = con.execute("SELECT hash,puzzle_b64,piece_b64,target,hits,misses FROM puzzles").fetchall()
        con.close()
        data = [{"hash": r[0], "puzzle_b64": r[1], "piece_b64": r[2],
                 "target": r[3], "hits": r[4], "misses": r[5]} for r in rows]
        with open(path, "w") as f:
            json.dump(data, f)
        return len(data)


if __name__ == "__main__":
    import sys
    cc = CaptchaCache()
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(cc.stats())
    elif len(sys.argv) > 1 and sys.argv[1] == "export":
        print("exported:", cc.export())
    else:
        print("usage: captcha_cache.py stats|export")
