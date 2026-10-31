#!/usr/bin/env python3
"""cache_cli.py — tools monitor/kelola captcha cache.

Usage:
  cache_cli.py stats              # ringkasan (entries, hits, misses, hit-rate)
  cache_cli.py top                # 10 entry paling sering dipakai
  cache_cli.py list               # semua entry (hash pendek + target + hits)
  cache_cli.py export             # dump ke JSON
  cache_cli.py clear              # hapus semua
  cache_cli.py prune N            # hapus entry yang hits < N (bersih-bersih)
"""
import sys, sqlite3
from captcha_cache import CaptchaCache, DB


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    cc = CaptchaCache()
    con = sqlite3.connect(DB)

    if cmd == "stats":
        n, hits, misses = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(hits),0), COALESCE(SUM(misses),0) FROM puzzles"
        ).fetchone()
        print(f"entries : {n}")
        print(f"hits    : {hits}")
        print(f"misses  : {misses}")
        # penghematan: tiap hit = 1 solve tidak perlu = ~$0.002 & ~3 detik
        print(f"hemat   : {hits} panggilan API (~${hits*0.002:.3f}, ~{hits*3}s)")
        if n + misses:
            print(f"hit-rate: {hits/(hits+misses)*100:.1f}%" if (hits+misses) else "hit-rate: n/a")

    elif cmd == "top":
        rows = con.execute(
            "SELECT substr(hash,1,12), target, hits, misses FROM puzzles ORDER BY hits DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            print(f"{r[0]}  target={r[1]:.4f}  hits={r[2]}  misses={r[3]}")

    elif cmd == "list":
        rows = con.execute(
            "SELECT substr(hash,1,12), target, hits, misses FROM puzzles ORDER BY last_used DESC"
        ).fetchall()
        print(f"{len(rows)} entries")
        for r in rows:
            print(f"  {r[0]}  target={r[1]:.4f}  hit={r[2]} miss={r[3]}")

    elif cmd == "export":
        print("exported:", cc.export(), "entries")

    elif cmd == "clear":
        con.execute("DELETE FROM puzzles"); con.commit()
        print("cleared")

    elif cmd == "prune":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        con.execute("DELETE FROM puzzles WHERE hits < ?", (n,)); con.commit()
        print(f"pruned entries with hits < {n}")

    else:
        print(__doc__)
    con.close()


if __name__ == "__main__":
    main()
