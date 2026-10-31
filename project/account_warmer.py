#!/usr/bin/env python3
"""account_warmer.py — #5: jaga akun tetap "hidup" + validasi berkala.

Untuk tiap akun (account_result.json):
  1. ping /api/v4/account/basic/get_account_info (validasi)
  2. warm: kunjungi home + trigger subcart (aktivitas ringan, biar ga di-flag)
  3. update status → accounts_health.json

Usage: account_warmer.py [--proxy] [--limit N] [--warm]
"""
import sys, os, json, time
import requests

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
USE_PROXY = "--proxy" in sys.argv
WARM = "--warm" in sys.argv
LIMIT = 100
for a in sys.argv:
    if a.startswith("--limit="): LIMIT = int(a.split("=", 1)[1])
PROXY = None
if USE_PROXY:
    try:
        PROXY = open(f"{ROOT}/proxies_best.txt").readline().strip()
    except Exception:
        PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()


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
        seen.add(key); out.append(d)
    return out


def sess_for(acc):
    ck = {p.split("=", 1)[0]: p.split("=", 1)[1] for p in acc["cookie"].split("; ") if "=" in p}
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "accept": "application/json",
                      "x-api-source": "pc", "x-requested-with": "XMLHttpRequest",
                      "x-shopee-language": "id", "referer": "https://shopee.co.id/",
                      "x-csrftoken": ck.get("csrftoken", "")})
    for k, v in ck.items():
        try: s.cookies.set(k, v, domain=".shopee.co.id")
        except Exception: pass
    if PROXY: s.proxies = {"http": PROXY, "https": PROXY}
    return s


def check_and_warm(acc):
    s = sess_for(acc)
    rec = {"phone": acc.get("phone"), "user_id": acc.get("user_id")}
    try:
        r = s.get("https://shopee.co.id/api/v4/account/basic/get_account_info", timeout=25)
        j = r.json()
        if isinstance(j, dict) and j.get("error") == 0 and j.get("data"):
            rec["status"] = "ALIVE"
            rec["username"] = j["data"].get("username")
            rec["phone_verified"] = j["data"].get("phone_verified")
        else:
            rec["status"] = "DEAD"; rec["error"] = (j or {}).get("error")
    except Exception as e:
        rec["status"] = "ERR"; rec["err"] = str(e)[:80]
        return rec
    if WARM and rec["status"] == "ALIVE":
        try:
            s.get("https://shopee.co.id/", timeout=20)
            time.sleep(0.5)
            s.post("https://shopee.co.id/api/v4/web/subcart", json={}, timeout=20)
            rec["warmed"] = True
        except Exception as e:
            rec["warmed"] = False; rec["warm_err"] = str(e)[:50]
    return rec


if __name__ == "__main__":
    accs = load_accounts()[:LIMIT]
    print(f"[warmer] {len(accs)} akun (proxy={'on' if PROXY else 'off'} warm={WARM})")
    rows, ok_n = [], 0
    for a in accs:
        rec = check_and_warm(a)
        rows.append(rec)
        if rec["status"] == "ALIVE": ok_n += 1
        print(f"  {rec.get('phone'):>14} {rec['status']:5} {rec.get('username','')} {'warmed' if rec.get('warmed') else ''}")
        time.sleep(0.4)
    json.dump(rows, open(f"{ROOT}/accounts_health.json", "w"), indent=1)
    print(f"[warmer] ALIVE={ok_n}/{len(rows)} → accounts_health.json")
