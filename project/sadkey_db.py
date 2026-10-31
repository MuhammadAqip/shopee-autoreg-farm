#!/usr/bin/env python3
"""sadkey_db.py — database API key SadCaptcha (hasil farm) untuk bot.

Dipakai bot Shopee: sync key baru dari /root/sadfarm ke DB ini,
lalu bot auto-pakai key terbaik.

DB: /root/shopee-farm/sadkey_db.json
"""
import json, os, time, requests

ROOT = "/root/shopee-farm"
DB = f"{ROOT}/sadkey_db.json"
SAD = "https://www.sadcaptcha.com"
ACC = "/root/sadfarm/accounts.json"


def _load():
    if os.path.exists(DB):
        try:
            return json.load(open(DB))
        except Exception:
            return {}
    return {}


def _save(d):
    json.dump(d, open(DB, "w"), indent=1, ensure_ascii=False)


def credits_of(key):
    try:
        r = requests.get(f"{SAD}/api/v1/license/credits", params={"licenseKey": key}, timeout=15).json()
        return r.get("credits")
    except Exception:
        return None


def sync_from_farm():
    """tarik semua key dari /root/sadfarm/accounts.json → DB. Return (added, total)."""
    d = _load()
    added = 0
    if os.path.exists(ACC):
        try:
            for a in json.load(open(ACC)):
                if a.get("ok") and a.get("apikey"):
                    k = a["apikey"]
                    if k not in d:
                        d[k] = {"email": a.get("email", ""), "credits": a.get("credits"),
                                "added": time.strftime("%Y-%m-%d %H:%M:%S"), "used": 0}
                        added += 1
                    else:
                        d[k]["credits"] = a.get("credits", d[k].get("credits"))
        except Exception:
            pass
    _save(d)
    return added, len(d)


def refresh():
    d = _load()
    dead = []
    for k in list(d):
        c = credits_of(k)
        if c is None:
            dead.append(k)
            continue
        d[k]["credits"] = c
    _save(d)
    return d


def refresh_and_clean():
    """refresh semua key; buang yang invalid (401) & habis (0cr). Return (kept, dropped)."""
    d = _load()
    dead = []
    for k in list(d):
        c = credits_of(k)
        if c is None or c <= 0:
            dead.append(k)
            del d[k]
        else:
            d[k]["credits"] = c
    _save(d)
    # pastikan bot_key.txt nunjuk ke key hidup
    bk = best_key()
    if bk:
        open(f"{ROOT}/bot_key.txt", "w").write(bk)
    return len(d), dead


def best_key(exclude=None):
    d = _load()
    ex = set(exclude or [])
    live = [(k, v.get("credits") or 0) for k, v in d.items() if k not in ex]
    live = [x for x in live if x[1] and x[1] > 0]
    if not live:
        return None
    live.sort(key=lambda x: -x[1])
    return live[0][0]


def add_key(key, email=""):
    """tambah key baru ke DB (dari user / farm)."""
    d = _load()
    if key in d:
        d[key]["credits"] = credits_of(key)
        _save(d)
        return False
    d[key] = {"email": email or "manual", "credits": credits_of(key),
              "added": time.strftime("%Y-%m-%d %H:%M:%S"), "used": 0}
    _save(d)
    return True


def drop_key(key):
    d = _load()
    if key in d:
        del d[key]
        _save(d)
        return True
    return False


def rotate_key(dead_key):
    """buang key habis, pindah ke key berikutnya dari pool. Return key baru / None."""
    drop_key(dead_key)
    k = best_key()
    if k:
        open(f"{ROOT}/bot_key.txt", "w").write(k)
    return k


def mark_used(key):
    d = _load()
    if key in d:
        d[key]["used"] = (d[key].get("used") or 0) + 1
        _save(d)


def sync_bot_key():
    """tulis key terbaik ke bot_key.txt Shopee."""
    k = best_key()
    if not k:
        return None
    open(f"{ROOT}/bot_key.txt", "w").write(k)
    return k


def total_credits():
    d = _load()
    return sum(v.get("credits") or 0 for v in d.values()), len(d)


def list_keys():
    d = _load()
    return [{"key": k, **v} for k, v in d.items()]


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if cmd == "sync":
        a, t = sync_from_farm()
        print(f"synced: +{a} baru, total {t}")
    elif cmd == "refresh":
        d = refresh()
        print(f"refreshed {len(d)} keys")
        for k, v in d.items():
            print(f"  {k}  {v.get('credits')}cr  {v.get('email')}")
    elif cmd == "best":
        print(best_key() or "NO KEY")
    elif cmd == "syncbot":
        print(sync_bot_key() or "NO KEY")
    elif cmd == "total":
        t, n = total_credits()
        print(f"total {t} credits / {n} keys")
    elif cmd == "list":
        for k in list_keys():
            print(f"{k['key']}  {k.get('credits')}cr  {k.get('email')}")
