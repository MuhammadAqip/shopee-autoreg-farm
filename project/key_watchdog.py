#!/usr/bin/env python3
"""key_watchdog.py — #6+#7: auto-feed key dari sadfarm + jaga pool hidup.

- Baca /root/sadfarm/accounts.json (+ keypool.json) → key belum terdaftar → KDB.add_key
- Cek kredit semua key di pool (refresh). Dead (401/0) → dibuang oleh refresh().
- Kalau pool hidup < MIN_ALIVE atau total kredit < MIN_CREDITS → jalankan sadfarm utk panen baru.
- Tulis ringkasan ke bot_key.txt (best) + notify (opsional via env BOT_TOKEN/CHAT).

Usage: key_watchdog.py [--harvest N] [--min-alive 2] [--min-credits 20]
"""
import json, os, sys, subprocess, time

ROOT = "/root/shopee-farm"
SADFARM = "/root/sadfarm"
sys.path.insert(0, ROOT)
import sadkey_db as KDB

MIN_ALIVE = 2
MIN_CREDITS = 20
HARVEST_N = 0
for a in sys.argv:
    if a.startswith("--min-alive="): MIN_ALIVE = int(a.split("=", 1)[1])
    if a.startswith("--min-credits="): MIN_CREDITS = int(a.split("=", 1)[1])
    if a.startswith("--harvest="): HARVEST_N = int(a.split("=", 1)[1])


def feed_from_sadfarm():
    """Tambah key dari sadfarm/accounts.json + keypool.json yg belum ada di DB."""
    added = 0
    for path, keyfield in (
        (f"{SADFARM}/accounts.json", "apikey"),
        (f"{SADFARM}/keypool.json", None),
    ):
        if not os.path.exists(path):
            continue
        try:
            data = json.load(open(path))
        except Exception:
            continue
        if isinstance(data, dict):
            keys = list(data.keys())
        else:
            keys = [r.get(keyfield) for r in data if isinstance(r, dict)]
        for k in keys:
            if not k:
                continue
            try:
                if KDB.add_key(k):
                    added += 1
                    print(f"  [feed] +{k[:12]}...")
            except Exception as e:
                print(f"  [feed] err {k[:10]}: {e}")
    return added


def pool_stats():
    r = KDB.refresh()
    alive = [k for k, v in r.items() if (v.get("credits") or 0) > 0]
    total = sum((v.get("credits") or 0) for v in r.values())
    return alive, total, r


def run_harvest(n):
    print(f"[watchdog] sadfarm harvest {n} akun...")
    try:
        subprocess.run(["/root/sniffenv/bin/python", "sadfarm.py", "--count", str(n)],
                       cwd=SADFARM, timeout=1800)
    except Exception as e:
        print(f"[watchdog] harvest err: {e}")


if __name__ == "__main__":
    print("[watchdog] mulai")
    added = feed_from_sadfarm()
    alive, total, r = pool_stats()
    print(f"[watchdog] pool: alive={len(alive)} total_credits={total}")
    if HARVEST_N > 0:
        run_harvest(HARVEST_N)
        feed_from_sadfarm()
        alive, total, r = pool_stats()
        print(f"[watchdog] setelah harvest: alive={len(alive)} total={total}")
    # top-up otomatis kalau kurang
    if len(alive) < MIN_ALIVE or total < MIN_CREDITS:
        print(f"[watchdog] pool kurang (alive={len(alive)}/{MIN_ALIVE} credits={total}/{MIN_CREDITS}) → harvest")
        run_harvest(max(3, MIN_ALIVE - len(alive) + 2))
        feed_from_sadfarm()
        alive, total, r = pool_stats()
        print(f"[watchdog] final pool: alive={len(alive)} total={total}")
    best = KDB.best_key()
    if best:
        open(f"{ROOT}/bot_key.txt", "w").write(best)
        print(f"[watchdog] bot_key.txt → {best[:16]}...")
    print(f"[watchdog] selesai. alive={len(alive)} credits={total}")
