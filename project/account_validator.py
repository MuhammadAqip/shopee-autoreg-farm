#!/usr/bin/env python3
"""account_validator.py — #B: VALIDATOR AKUN (quality gate sebelum jual).

Bedain 3 status akun:
  ✅ READY   — cookie punya SPC_U + SPC_ST + API balik user_id (siap jual)
  🟡 REPAIR  — ada cookie tapi SPC_U/SPC_ST kosong (bisa dicoba login-repair)
  🔴 DEAD    — cookie kosong / registrasi gagal (buang)

Output: accounts_status.json + ringkasan per-status.

Usage:
  account_validator.py [--file account_result.json] [--proxy]
"""
import json
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
ACC = os.path.join(ROOT, "account_result.json")
OUT = os.path.join(ROOT, "accounts_status.json")
UA = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

USE_PROXY = "--proxy" in sys.argv
PROXY = None
if USE_PROXY:
    try:
        P = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
        PROXY = {"http": P, "https": P}
    except Exception:
        pass


def has_session(cookie):
    return bool(re.search(r"SPC_U=\d", cookie)) and bool(re.search(r"SPC_ST=", cookie))


def api_check(cookie):
    """Cek via API. Return (ok, user_id, reason)."""
    h = {"User-Agent": UA, "Accept": "application/json", "Cookie": cookie,
         "Referer": "https://shopee.co.id/", "x-api-source": "pc",
         "x-requested-with": "XMLHttpRequest", "Affiliate-Id": "0"}
    try:
        r = requests.get("https://shopee.co.id/api/v4/account/basic/get_account_info",
                         headers=h, timeout=20, proxies=PROXY)
        j = r.json()
        if r.status_code == 200 and j.get("error") == 0 and j.get("data"):
            d = j["data"]
            return True, str(d.get("userid", "")), "AKTIF"
        return False, "", f"error={j.get('error')}: {str(j.get('error_msg',''))[:40]}"
    except Exception as e:
        return False, "", f"{type(e).__name__}: {str(e)[:50]}"


def classify(acc):
    ck = acc.get("cookie", "")
    if not ck:
        return "dead", "no cookie"
    if not has_session(ck):
        # cookie ada tapi tanpa session → registrasi gagal
        return "dead", "no SPC_U/SPC_ST (registrasi gagal)"
    ok, uid, reason = api_check(ck)
    if ok:
        acc["user_id"] = uid or acc.get("user_id", "")
        return "ready", "AKTIF"
    if "error=19" in reason:
        return "repair", "session ada tapi auth gagal (coba login-repair)"
    return "dead", reason


def main():
    f = ACC
    for a in sys.argv:
        if a.startswith("--file="):
            f = a.split("=", 1)[1]
    accs = []
    for l in open(f):
        l = l.strip()
        if not l:
            continue
        try:
            accs.append(json.loads(l))
        except Exception:
            pass
    print(f"[validator] {len(accs)} akun")
    summary = {"ready": 0, "repair": 0, "dead": 0}
    results = []
    for a in accs:
        st, msg = classify(a)
        a["status"] = st
        a["status_msg"] = msg
        summary[st] += 1
        results.append({"phone": a.get("phone"), "user_id": a.get("user_id", ""),
                        "status": st, "msg": msg})
        print(f"  {'✅' if st=='ready' else '🟡' if st=='repair' else '🔴'} {a.get('phone')} → {st} ({msg[:45]})")
    json.dump({"summary": summary, "results": results,
               "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")},
              open(OUT, "w"), indent=2, ensure_ascii=False)
    # simpan balik yg updated (user_id)
    with open(f, "w") as fo:
        for a in accs:
            fo.write(json.dumps(a, ensure_ascii=False) + "\n")
    print(f"\n[validator] ✅READY {summary['ready']} | 🟡REPAIR {summary['repair']} | 🔴DEAD {summary['dead']}")
    print(f"[validator] → {OUT}")


if __name__ == "__main__":
    main()
