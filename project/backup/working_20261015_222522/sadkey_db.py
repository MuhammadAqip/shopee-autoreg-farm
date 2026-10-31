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
    for k in d:
        d[k]["credits"] = credits_of(k)
    _save(d)
    return d


def best_key():
    d = _load()
    live = [(k, v.get("credits") or 0) for k, v in d.items()]
    live = [x for x in live if x[1] and x[1] > 0]
    if not live:
        return None
    live.sort(key=lambda x: -x[1])
    return live[0][0]


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
