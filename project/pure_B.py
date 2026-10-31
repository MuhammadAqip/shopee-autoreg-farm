#!/usr/bin/env python3
"""pure_B.py — B: uji jalur PURE-API pakai security_data (hasil verify_v2) yang di-capture.

Alur API:
  1. get_settings_v2 {operation:8, phone, supported_channels, client_identifier:{security_device_fingerprint}}
     → expected: need_captcha:true, captcha_scene:"signup", available_channels
  2. send_vcode {channel:3, operation:8, m_token:<verify security_data>, phone}
     → kalau 200 error:0 → WA terkirim PURE API (no browser!)

Catatan: security_data kemungkinan per-session/nomor. Kita uji empiris.
"""
import sys, json, time
import requests

ROOT = "/root/shopee-farm"
PHONE = sys.argv[1] if len(sys.argv) > 1 else "85602884239"
# tarik security_data + cookies dari capture/session terakhir
sec = None
for l in open(f"{ROOT}/capture/captcha_wa_flow.jsonl"):
    try:
        d = json.loads(l)
    except Exception:
        continue
    if "verify_v2" in d.get("u", "") and d.get("s") == 200:
        try:
            sec = json.loads(d["r"])["security_data"]
        except Exception:
            pass

st = json.load(open(f"{ROOT}/captcha_wa_state.json")) if __import__("os").path.exists(f"{ROOT}/captcha_wa_state.json") else {}
cookies = st.get("cookies", {})
print("security_data:", (sec or "")[:60])
print("cookies:", list(cookies.keys())[:8])

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
s = requests.Session()
s.headers.update({
    "User-Agent": UA, "accept": "application/json",
    "content-type": "application/json", "x-api-source": "pc",
    "x-requested-with": "XMLHttpRequest", "x-shopee-language": "id",
    "referer": "https://shopee.co.id/buyer/signup",
    "af-ac-enc-sz-token": cookies.get("af-ac-enc-sz-token", ""),
    "x-csrftoken": cookies.get("csrftoken", ""),
})
for k, v in cookies.items():
    try:
        s.cookies.set(k, v, domain=".shopee.co.id")
    except Exception:
        pass
try:
    px = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
    s.proxies = {"http": px, "https": px}
    print("proxy:", px.split("@")[-1])
except Exception:
    pass

BASE = "https://shopee.co.id/api/v4/otp"
fp = cookies.get("_sapid", "")

# 1) get_settings_v2
body1 = {
    "operation": 8, "phone": PHONE,
    "supported_channels": [1, 2, 3, 6, 0, 5],
    "support_session": True,
    "client_identifier": {"security_device_fingerprint": fp},
}
r1 = s.post(f"{BASE}/get_settings_v2", json=body1, timeout=30)
print("\n[1] get_settings_v2", r1.status_code, "→", r1.text[:300])

# 2) send_vcode ch3 op8 dengan m_token = security_data
body2 = {
    "channel": 3, "operation": 8, "phone": PHONE,
    "m_token": sec or "",
    "supported_channels": [1, 2, 3, 6, 0, 5],
    "client_identifier": {"security_device_fingerprint": fp},
}
r2 = s.post(f"{BASE}/send_vcode", json=body2, timeout=30)
print("[2] send_vcode ch3 op8", r2.status_code, "→", r2.text[:300])
