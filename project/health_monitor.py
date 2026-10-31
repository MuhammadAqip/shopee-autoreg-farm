#!/usr/bin/env python3
"""health_monitor.py — #9: cek kesehatan akun berkala (login ping) → tandai mati.

Baca account_result.json (semua akun), hit /api/v4/account/basic/get_account_info
dgn cookie masing-masing. Valid = error:0. Mati = error 19 / lainnya.
Output: accounts_health.json + ringkasan.
Usage: health_monitor.py [--proxy] [--limit N]
"""
import json, sys, time, requests

ROOT = "/root/shopee-farm"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
USE_PROXY = "--proxy" in sys.argv
LIMIT = 50
for a in sys.argv:
    if a.startswith("--limit="):
        LIMIT = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip() if USE_PROXY else None


def load_accounts():
    seen, out = set(), []
    for l in open(f"{ROOT}/account_result.json"):
        l = l.strip()
        if not l:
            continue
        try:
            d = json.loads(l)
        except Exception:
            continue
        key = (d.get("phone"), d.get("user_id"))
        if key in seen or not d.get("cookie"):
            continue
        seen.add(key)
        out.append(d)
    return out


def check(acc):
    ck = {p.split("=", 1)[0]: p.split("=", 1)[1] for p in acc["cookie"].split("; ") if "=" in p}
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "accept": "application/json",
                      "x-api-source": "pc", "x-requested-with": "XMLHttpRequest",
                      "x-shopee-language": "id", "referer": "https://shopee.co.id/",
                      "x-csrftoken": ck.get("csrftoken", "")})
    for k, v in ck.items():
        try:
            s.cookies.set(k, v, domain=".shopee.co.id")
        except Exception:
            pass
    if PROXY:
        s.proxies = {"http": PROXY, "https": PROXY}
    try:
        r = s.get("https://shopee.co.id/api/v4/account/basic/get_account_info", timeout=25)
        j = r.json()
        if isinstance(j, dict) and j.get("error") == 0 and j.get("data"):
            data = j["data"]
            return True, {"userid": data.get("userid"), "username": data.get("username"),
                          "phone": data.get("phone"), "phone_verified": data.get("phone_verified")}
        return False, {"error": (j or {}).get("error"), "http": r.status_code}
    except Exception as e:
        return None, {"err": str(e)[:80]}


if __name__ == "__main__":
    accs = load_accounts()[:LIMIT]
    print(f"[health] cek {len(accs)} akun (proxy={'on' if PROXY else 'off'})")
    rows, ok_n, dead_n, err_n = [], 0, 0, 0
    for a in accs:
        alive, info = check(a)
        status = "ALIVE" if alive else ("DEAD" if alive is False else "ERR")
        if alive: ok_n += 1
        elif alive is False: dead_n += 1
        else: err_n += 1
        rec = {"phone": a.get("phone"), "user_id": a.get("user_id"), "status": status,
               "info": info, "fp": a.get("fingerprint", "")[:16]}
        rows.append(rec)
        print(f"  {a.get('phone'):>14} {status:5} {info}")
        time.sleep(0.5)
    json.dump(rows, open(f"{ROOT}/accounts_health.json", "w"), indent=1)
    print(f"[health] ALIVE={ok_n} DEAD={dead_n} ERR={err_n} → accounts_health.json")
