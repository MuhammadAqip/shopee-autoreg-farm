#!/usr/bin/env python3
"""verify_C.py — C: buktikan akun hidup via API pakai cookie hasil signup.
   Hit account_info / get_user_info dengan cookie → harus balik userid & nama.
"""
import json, os
import requests

ROOT = "/root/shopee-farm"
LAST = None
for l in open(f"{ROOT}/account_result.json"):
    l = l.strip()
    if not l:
        continue
    try:
        d = json.loads(l)
    except Exception:
        continue
    if d.get("phone") == "85602884239":
        LAST = d
d = LAST
cookie = d["cookie"]
ck = {p.split("=", 1)[0]: p.split("=", 1)[1] for p in cookie.split("; ") if "=" in p}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
s = requests.Session()
s.headers.update({
    "User-Agent": UA, "accept": "application/json",
    "x-api-source": "pc", "x-requested-with": "XMLHttpRequest",
    "x-shopee-language": "id", "referer": "https://shopee.co.id/",
    "af-ac-enc-dat": "", "x-csrftoken": ck.get("csrftoken", ""),
})
for k, v in ck.items():
    s.cookies.set(k, v, domain=".shopee.co.id")

PROXY = None
try:
    px = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
    s.proxies = {"http": px, "https": px}
    PROXY = px.split("@")[-1]
except Exception:
    pass
print("proxy:", PROXY)

ENDPOINTS = [
    ("account_info", "https://shopee.co.id/api/v4/account/basic/get_account_info"),
    ("user_info", "https://shopee.co.id/api/v4/user/get_user_info"),
    ("buyer_profile", "https://shopee.co.id/api/v4/buyer/get"),
    ("cart", "https://shopee.co.id/api/v4/cart/get"),
]
for name, url in ENDPOINTS:
    try:
        r = s.get(url, timeout=25)
        body = r.text[:400]
        print(f"[{name}] {r.status_code} → {body}")
    except Exception as e:
        print(f"[{name}] ERR {e}")
