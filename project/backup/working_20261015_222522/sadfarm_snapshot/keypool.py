#!/usr/bin/env python3
"""keypool.py — kelola pool API key SadCaptcha hasil farm.

Fitur:
  - list key + credits
  - pilih key terbaik (credits terbanyak)
  - sync ke bot_key.txt (Shopee bot auto-pakai)
  - refresh credits semua key
  - cek key mati/habis

Usage:
  keypool.py list
  keypool.py refresh
  keypool.py best            # print key terbaik
  keypool.py sync            # set bot_key.txt = key terbaik
  keypool.py add <key>
  keypool.py total           # total credits semua key
"""
import sys, json, os, requests

ROOT = "/root/sadfarm"
POOL = f"{ROOT}/keypool.json"
BOT_KEY = "/root/shopee-farm/bot_key.txt"
ACC = f"{ROOT}/accounts.json"


def _load():
    if os.path.exists(POOL):
        try:
            return json.load(open(POOL))
        except Exception:
            return {}
    return {}


def _save(d):
    json.dump(d, open(POOL, "w"), indent=1)


def import_from_accounts():
    """tarik semua apikey dari accounts.json ke pool."""
    p = _load()
    if os.path.exists(ACC):
        try:
            for a in json.load(open(ACC)):
                if a.get("ok") and a.get("apikey"):
                    p.setdefault(a["apikey"], {"email": a.get("email", ""),
                                               "credits": a.get("credits"),
                                               "created": a.get("created", "")})
        except Exception:
            pass
    _save(p)
    return p


def credits_of(key):
    try:
        r = requests.get("https://www.sadcaptcha.com/api/v1/license/credits",
                         params={"licenseKey": key}, timeout=15).json()
        return r.get("credits")
    except Exception:
        return None


def refresh():
    p = import_from_accounts()
    total = 0
    for k in p:
        c = credits_of(k)
        p[k]["credits"] = c
        if c:
            total += c
    _save(p)
    return p, total


def best():
    p = import_from_accounts()
    live = [(k, v.get("credits") or 0) for k, v in p.items()]
    live = [x for x in live if x[1] and x[1] > 0]
    if not live:
        return None
    live.sort(key=lambda x: -x[1])
    return live[0][0]


def sync_bot():
    k = best()
    if not k:
        return None
    open(BOT_KEY, "w").write(k)
    return k


def cmd_list():
    p = import_from_accounts()
    if not p:
        print("(pool kosong)")
        return
    for k, v in p.items():
        print(f"{k}  credits={v.get('credits')}  {v.get('email','')}")


def cmd_total():
    p, total = refresh()
    n = sum(1 for v in p.values() if (v.get("credits") or 0) > 0)
    print(f"total credits: {total}  |  key aktif: {n}/{len(p)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        cmd_list()
    elif cmd == "refresh":
        p, total = refresh()
        print(f"refreshed {len(p)} keys, total {total} credits")
        cmd_list()
    elif cmd == "best":
        print(best() or "NO KEY")
    elif cmd == "sync":
        k = sync_bot()
        print(f"bot_key.txt -> {k}" if k else "NO KEY")
    elif cmd == "add":
        if len(sys.argv) > 2:
            p = import_from_accounts()
            p[sys.argv[2]] = {"email": "", "credits": credits_of(sys.argv[2]), "created": ""}
            _save(p)
            print("added")
    elif cmd == "total":
        cmd_total()
    else:
        print(__doc__)
