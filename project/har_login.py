#!/usr/bin/env python3
"""har_login.py — HAR capture via Playwright record_har_path (dump terbaik).
Output: HAR penuh (req+resp bodies) → buat derive API.
Gunakan untuk capture SATU kali, lalu derive dari HAR tanpa browser lagi.
"""
import sys, time, json
from playwright.sync_api import sync_playwright

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6289601416330"
PROXY = open("/root/shopee-farm/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]
USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
HAR = "/root/shopee-farm/capture/shopee_%s.har" % time.strftime("%Y%m%d_%H%M%S")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False,
                           args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    c = b.new_context(
        user_agent=UA, locale="id-ID",
        proxy={"server": "http://" + HOST, "username": USER, "password": PASS},
        ignore_https_errors=True, viewport={"width": 1280, "height": 900},
        record_har_path=HAR, record_har_mode="full", record_har_content="embed")
    c.add_cookies([{"name": "shopee_webLanguage", "value": "id",
                    "domain": ".shopee.co.id", "path": "/"}])
    p = c.new_page()
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(20)
    # dismiss modal bahasa
    try:
        btn = p.locator("button.shopee-button-outline").first
        if btn.count():
            btn.click(timeout=3000, force=True); print("[*] modal ditutup", flush=True)
            time.sleep(3)
    except Exception: pass
    n = p.evaluate("()=>document.querySelectorAll('input').length")
    print("[inputs]", n, flush=True)
    try:
        inp = p.locator("input[name='phone']").first
        inp.click(timeout=3000); inp.type(PHONE, delay=45)
        print("[*] nomor diisi:", PHONE, flush=True)
    except Exception as e:
        print("fill err", str(e)[:90], flush=True)
    time.sleep(3)
    for lbl in ("BERIKUTNYA", "Berikutnya", "Lanjut"):
        try:
            p.locator(f"button:has-text('{lbl}')").first.click(timeout=2500, force=True)
            print(f"[*] klik {lbl}", flush=True); break
        except Exception: pass
    time.sleep(18)
    body = p.evaluate("()=>document.body.innerText||''")
    print("[PAGE]", body[:300].replace("\n", " | "), flush=True)
    p.screenshot(path="/root/shopee-farm/shots/har_capture.png", full_page=True)
    c.close()
    b.close()
print("[HAR]", HAR, flush=True)
json.dump({"har": HAR}, open("/root/shopee-farm/last_har.json", "w"))
