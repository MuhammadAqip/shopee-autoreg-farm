#!/usr/bin/env python3
"""stats.py — #6: agregasi statistik akurat utk dashboard bot.

Hitung dari : account_result.json, accounts_health.json, captcha_cache.db,
proxy_health.json, limited_numbers.txt, sadkey_db.json.
Return dict siap tampil. Import: from stats import summary; summary()
"""
import os, json, sqlite3, time

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def accounts():
    out = []
    try:
        for l in open(f"{ROOT}/account_result.json"):
            l = l.strip()
            if l.startswith("{"):
                try: out.append(json.loads(l))
                except Exception: pass
    except Exception:
        pass
    return out


def summary():
    accs = accounts()
    total = len(accs)
    valid = sum(1 for a in accs if a.get("validated") is True)
    invalid = total - valid
    # per-hari
    today = time.strftime("%Y-%m-%d")
    today_n = 0
    for a in accs:
        ts = a.get("ctime") or a.get("ts")
        try:
            if ts and time.strftime("%Y-%m-%d", time.localtime(int(ts))) == today:
                today_n += 1
        except Exception:
            pass
    # cache
    cache_n = cache_hits = 0
    try:
        con = sqlite3.connect(f"{ROOT}/captcha_cache.db")
        cache_n, cache_hits = con.execute("SELECT COUNT(*), COALESCE(SUM(hits),0) FROM puzzles").fetchone()
        con.close()
    except Exception:
        pass
    # proxy
    proxy_ok = proxy_id = proxy_n = 0
    try:
        ph = json.load(open(f"{ROOT}/proxy_health.json"))
        proxy_n = len(ph)
        proxy_ok = sum(1 for p in ph if p.get("ok"))
        proxy_id = sum(1 for p in ph if p.get("id_ok"))
    except Exception:
        pass
    # key pool
    keys_n = keys_credits = 0
    try:
        kd = json.load(open(f"{ROOT}/sadkey_db.json"))
        vals = kd.values() if isinstance(kd, dict) else []
        keys_n = len([v for v in vals if (v.get("credits") or 0) > 0])
        keys_credits = sum((v.get("credits") or 0) for v in vals)
    except Exception:
        pass
    # limited
    lim = 0
    try:
        lim = sum(1 for l in open(f"{ROOT}/limited_numbers.txt") if l.strip())
    except Exception:
        pass
    return {
        "accounts_total": total, "accounts_valid": valid, "accounts_invalid": invalid,
        "today": today_n, "cache_puzzles": cache_n, "cache_hits": int(cache_hits),
        "proxy_n": proxy_n, "proxy_ok": proxy_ok, "proxy_id": proxy_id,
        "keys_alive": keys_n, "keys_credits": keys_credits, "limited": lim,
    }


def text_block():
    s = summary()
    hitrate = (s["cache_hits"] * 100 // s["cache_puzzles"]) if s["cache_puzzles"] else 0
    return (
        f"\U0001F4CA *Dashboard*\n\n"
        f"\U0001F464 Akun: *{s['accounts_total']}* total | *{s['accounts_valid']}* valid | *{s['accounts_invalid']}* mati\n"
        f"\U0001F4C5 Hari ini: *{s['today']}* akun\n"
        f"\U0001F5C3\uFE0F Cache: *{s['cache_puzzles']}* puzzle | *{s['cache_hits']}* hit (*{hitrate}%*)\n"
        f"\U0001F310 Proxy: *{s['proxy_ok']}/{s['proxy_n']}* ok | *{s['proxy_id']}* ID\n"
        f"\U0001F511 Key: *{s['keys_alive']}* hidup | *{s['keys_credits']}* kredit\n"
        f"\U0001F6AB Nomor limit: *{s['limited']}*\n"
    )


if __name__ == "__main__":
    print(text_block())
    print(json.dumps(summary(), indent=1))
