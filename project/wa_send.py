#!/usr/bin/env python3
"""wa_send.py — pakai riskToken + cookies dari tokengrab.json buat send_vcode WA via API.
"""
import requests, json, sys, urllib3, uuid
urllib3.disable_warnings()

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6287876125616"
PROXY = "http://127.0.0.1:8888"

R = json.load(open("/root/shopee-farm/risk_token.json"))
RISK = R["token"]
CK = R.get("cookies", {})

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
s = requests.Session()
s.proxies = {"http": PROXY, "https": PROXY}
s.verify = False
s.headers.update({
    "User-Agent": UA, "Accept": "application/json",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Origin": "https://shopee.co.id", "Referer": "https://shopee.co.id/buyer/signup",
    "x-api-source": "pc", "x-requested-with": "XMLHttpRequest",
    "x-shopee-language": "id", "Content-Type": "application/json",
})
# pakai cookies browser
for k, v in CK.items():
    s.cookies.set(k, v, domain=".shopee.co.id")
if "csrftoken" in CK:
    s.headers["x-csrftoken"] = CK["csrftoken"]

print("cookies loaded:", len(CK), "| riskToken:", RISK[:40], flush=True)
print("PHONE:", PHONE, flush=True)

def jj(r):
    try: return r.json()
    except: return {"_raw": r.text[:200]}

# get_settings
r = s.post("https://shopee.co.id/api/v4/otp/get_settings_v2",
           json={"phone": PHONE, "operation": 8}, timeout=45)
print("[settings]", r.status_code, json.dumps(jj(r))[:200], flush=True)

# send_vcode WA dengan riskToken asli
r = s.post("https://shopee.co.id/api/v4/otp/send_vcode",
           json={"phone": PHONE, "channel": 3, "operation": 8,
                 "force_channel": True, "m_token": RISK}, timeout=45)
print("[send WA ch3]", r.status_code, json.dumps(jj(r))[:250], flush=True)

# fallback channel 1 (voice) kalau WA gagal
if jj(r).get("error") != 0:
    r = s.post("https://shopee.co.id/api/v4/otp/send_vcode",
               json={"phone": PHONE, "channel": 1, "operation": 8,
                     "force_channel": True, "m_token": RISK}, timeout=45)
    print("[send SMS ch1]", r.status_code, json.dumps(jj(r))[:250], flush=True)

json.dump({c.name: c.value for c in s.cookies}, open("/root/shopee-farm/wa_sess_cookies.json", "w"))
print("[session cookies saved]", flush=True)
