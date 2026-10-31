#!/usr/bin/env python3
"""captcha_resolve.py — resolver cache-first (tanpa API kalau hit).

Alur:
  1. Hash puzzle_b64 → cari di captcha_cache.db
  2. HIT → pakai target (instant, no API)
  3. MISS → fallback: local gap-detect (gap_v6) ATAU API solver

Karena Shopee rotate captcha per-session, cache hit rendah. Tapi kombinasi:
  - prewarm: solve banyak puzzle → isi cache
  - + local detector yang di-calibrate

Output: offset x (drag distance).
"""
import sqlite3, hashlib, base64, os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))

def cache_lookup(puzzle_b64):
    """Lookup by CONTENT (hash di cache gak reliable — pakai b64 langsung)."""
    db=f"{ROOT}/captcha_cache.db"
    if not os.path.exists(db): return None
    pb = puzzle_b64 if isinstance(puzzle_b64,str) else base64.b64encode(puzzle_b64).decode()
    c=sqlite3.connect(db, timeout=10)
    try: c.execute("PRAGMA busy_timeout=8000")
    except Exception: pass
    # exact b64 match dulu
    r=c.execute("SELECT target FROM puzzles WHERE puzzle_b64=? LIMIT 1", (pb,)).fetchone()
    if r:
        try:
            c.execute("UPDATE puzzles SET hits=hits+1,last_used=? WHERE puzzle_b64=?", (str(__import__('time').time()), pb))
            c.commit()
        except Exception:
            pass  # best-effort; lock tidak fatal utk read
        return float(r[0])
    # fallback: hash (mungkin cocok utk sebagian)
    h=hashlib.sha256(pb.encode()).hexdigest()
    r=c.execute("SELECT target FROM puzzles WHERE hash=?", (h,)).fetchone()
    if r: return float(r[0])
    return None

def cache_stats():
    c=sqlite3.connect(f"{ROOT}/captcha_cache.db")
    n=c.execute("SELECT COUNT(*) FROM puzzles").fetchone()[0]
    hits=c.execute("SELECT SUM(hits) FROM puzzles").fetchone()[0] or 0
    return {"cached":n, "total_hits":hits}

def local_detect(puzzle_b64):
    """Fallback: local gap detect."""
    import base64, tempfile
    sys.path.insert(0,f"{ROOT}")
    import tools.gap_v6 as g6
    fd,path=tempfile.mkstemp(suffix=".png")
    os.write(fd, base64.b64decode(puzzle_b64)); os.close(fd)
    try:
        d=g6.detect(path)
        return d.get("offset") if d else None
    finally:
        try: os.unlink(path)
        except: pass

def resolve(puzzle_b64, W=280):
    """Resolve offset: cache → local → None."""
    t=cache_lookup(puzzle_b64)
    if t is not None:
        return {"offset": round(t*W), "src":"cache", "target": t}
    off=local_detect(puzzle_b64)
    if off is not None:
        return {"offset": off, "src":"local"}
    return {"offset": None, "src":"miss"}

if __name__=="__main__":
    print("cache stats:", cache_stats())
    # test resolve on cached samples
    c=sqlite3.connect(f"{ROOT}/captcha_cache.db")
    for row in c.execute("SELECT puzzle_b64,target FROM puzzles LIMIT 3"):
        r=resolve(row[0])
        print(f"  GT_target={row[1]}  resolve={r}")
