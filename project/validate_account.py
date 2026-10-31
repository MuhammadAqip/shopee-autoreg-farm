#!/usr/bin/env python3
"""validate_account.py — cek akun Shopee masih aktif (login test via cookie).

Pakai cookie akun → hit /api/v4/account/basic/get_account_info tanpa browser.
Kalau 200 + ada data user → AKTIF. Kalau 401/login → DEAD.

Usage:
  validate_account.py '<cookie_string>'
"""
import sys, json, requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def validate(cookie_str):
    if not cookie_str:
        return {"ok": False, "reason": "no cookie"}
    h = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
        "Referer": "https://shopee.co.id/",
        "x-api-source": "pc",
        "x-requested-with": "XMLHttpRequest",
        "Cookie": cookie_str,
    }
    try:
        r = requests.get("https://shopee.co.id/api/v4/account/basic/get_account_info",
                         headers=h, timeout=20)
        if r.status_code == 200:
            j = r.json()
            if j.get("error") == 0 and j.get("data"):
                d = j["data"]
                return {"ok": True,
                        "username": d.get("username", ""),
                        "userid": str(d.get("userid", d.get("userid", "")) or ""),
                        "phone": d.get("phone", ""),
                        "email": d.get("email", "")}
            return {"ok": False, "reason": f"error={j.get('error')}", "raw": str(j)[:120]}
        return {"ok": False, "reason": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:100]}


def validate_phone_cookie(cookie_str):
    """Alias."""
    return validate(cookie_str)


if __name__ == "__main__":
    ck = sys.argv[1] if len(sys.argv) > 1 else ""
    print(json.dumps(validate(ck), indent=1, ensure_ascii=False))
