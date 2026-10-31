#!/usr/bin/env python3
"""api_signup_test.py — tes endpoint signup OTP murni API (tanpa browser).
Cek apakah send_vcode / verify_vcode bisa dipanggil cuma pakai cookie + csrf.
"""
import requests, json, sys, re, time

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6285849156988"
PROXY_FILE = "/root/shopee-farm/proxies_id_vs.txt"
PROXY = open(PROXY_FILE).readline().strip()

S = requests.Session()
S.proxies = {"http": PROXY, "https": PROXY}
S.verify = False
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Origin": "https://shopee.co.id",
    "Referer": "https://shopee.co.id/buyer/signup",
    "x-api-source": "pc",
    "x-requested-with": "XMLHttpRequest",
    "x-shopee-language": "id",
    "Content-Type": "application/json",
})

def log(*a): print(*a, flush=True)

# 1. warm up session — ambil cookie + csrf
log("[1] warmup: GET shopee.co.id")
r = S.get("https://shopee.co.id/buyer/signup", timeout=40)
log("   status", r.status_code, "cookies:", list(S.cookies.keys()))

# cari csrf token di cookie / page
csrf = S.cookies.get("csrftoken") or S.cookies.get("csrf_token") or ""
m = re.search(r'csrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)', r.text)
if m: csrf = m.group(1)
log("   csrf:", csrf[:30] if csrf else "(none)")
if csrf:
    S.headers["x-csrftoken"] = csrf

def call(name, method, path, body=None):
    url = f"https://shopee.co.id{path}"
    log(f"[*] {name}: {method} {path}")
    try:
        if method == "GET":
            r = S.get(url, timeout=40)
        else:
            r = S.post(url, json=body or {}, timeout=40)
        log(f"    -> {r.status_code} {r.text[:300]}")
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text[:300]
    except Exception as e:
        log("    ERR", str(e)[:150]); return None, None

# 2. cek nomor exist
call("check_phone_exist", "POST", "/api/v4/account/basic/check_phone_exist",
     {"phone": PHONE})

# 3. coba send_vcode (operation GENERAL=0/2?, channel 1=SMS)
for op in (0, 1, 2, 3):
    st, js = call(f"send_vcode op={op}", "POST", "/api/v4/otp/send_vcode",
                  {"phone": PHONE, "channel": 1, "operation": op,
                   "force_channel": False, "m_token": ""})
    if st == 200 and js and js.get("error") == 0:
        break
