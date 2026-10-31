#!/usr/bin/env python3
"""tokengrab.py — buka signup di browser, intercept riskToken dari shpsec report,
lalu inject ke API session buat send_vcode WA.
Hybrid: browser HANYA generate riskToken (otomatis, ~5s), sisanya API.
"""
import sys, time, json, re
from playwright.sync_api import sync_playwright
import requests, uuid, hashlib, urllib3
urllib3.disable_warnings()

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6287876125616"
MODE = sys.argv[2] if len(sys.argv) > 2 else "send"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
RISK = {"token": "", "cookies": {}}

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False,
                           args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://127.0.0.1:8888"},
                      ignore_https_errors=True,
                      viewport={"width": 1280, "height": 900})
    p = c.new_page()

    def on_resp(r):
        if "shpsec/web/report" in r.url:
            try:
                j = r.json()
                tok = ((j.get("data") or {}).get("riskToken")) or ""
                if tok:
                    RISK["token"] = tok
                    print("[GRAB] riskToken:", tok[:60], flush=True)
            except Exception:
                pass
        if "get_settings_v2" in r.url or "send_vcode" in r.url:
            print(f"[NET] {r.request.method} {r.status} {r.url.split('?')[0][-40:]}", flush=True)
    p.on("response", on_resp)

    print("[*] buka signup (generate shpsec riskToken otomatis)", flush=True)
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    # tunggu riskToken muncul (beacon shpsec otomatis saat load)
    for _ in range(20):
        time.sleep(1.5)
        if RISK["token"]:
            break
    # isi nomor biar beacon tambahan keluar
    try:
        inp = p.locator("input[type='tel'], input[type='text']").first
        inp.click(); inp.type(PHONE, delay=40)
        print("[*] nomor diisi", flush=True)
        time.sleep(3)
        for label in ("BERIKUTNYA", "Berikutnya", "Lanjut"):
            try:
                p.locator(f"button:has-text('{label}')").first.click(timeout=1500, force=True)
                print(f"[*] klik {label}", flush=True); time.sleep(5); break
            except Exception: pass
    except Exception as e:
        print("fill err", str(e)[:100], flush=True)
    for _ in range(10):
        time.sleep(1.5)
        if RISK["token"]: break
    # ambil cookies browser
    RISK["cookies"] = {ck["name"]: ck["value"] for ck in c.cookies()}
    print("[*] cookies:", list(RISK["cookies"].keys()), flush=True)
    p.screenshot(path="/root/shopee-farm/shots/tokengrab.png")
    b.close()

json.dump(RISK, open("/root/shopee-farm/risk_token.json", "w"))
print("[SAVED] /root/shopee-farm/risk_token.json", flush=True)
print("RISK TOKEN:", RISK["token"][:80], flush=True)
