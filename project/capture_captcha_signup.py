#!/usr/bin/env python3
"""capture_captcha_signup.py — pakai nomor FRESH, jalan sampai captcha scene signup MUNCUL.
Dump: semua request anti_fraud/* + screenshot captcha + payload generate/verify.
"""
import sys, time, json
from playwright.sync_api import sync_playwright

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6285849156988"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False,
                           args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://127.0.0.1:8888"},
                      ignore_https_errors=True,
                      viewport={"width": 1280, "height": 900})
    p = c.new_page()
    SNAP = {"calls": []}

    def on_resp(r):
        u = r.url
        if any(k in u for k in ("captcha", "anti_fraud", "otp", "vcode", "shpsec")):
            e = {"m": r.request.method, "url": u.split("?")[0], "st": r.status}
            try:
                if r.request.method == "POST":
                    e["req"] = (r.request.post_data or "")[:400]
            except Exception: pass
            try:
                e["res"] = (r.text() or "")[:400]
            except Exception: pass
            SNAP["calls"].append(e)
            print(f"[NET] {e['m']} {e['st']} {e['url'][-50:]}", flush=True)
            if e.get("req"): print("      REQ:", e["req"][:250], flush=True)
            if e.get("res"): print("      RES:", e["res"][:250], flush=True)
    p.on("response", on_resp)

    print("[*] goto signup", flush=True)
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    try:
        inp = p.locator("input[type='tel'], input[type='text']").first
        inp.click(); inp.type(PHONE, delay=45)
        print("[*] diisi:", PHONE, flush=True)
    except Exception as e:
        print("fill err", str(e)[:100], flush=True)
    time.sleep(2)
    for label in ("BERIKUTNYA", "Berikutnya", "Lanjut"):
        try:
            p.locator(f"button:has-text('{label}')").first.click(timeout=1800, force=True)
            print(f"[*] klik {label}", flush=True); time.sleep(6); break
        except Exception: pass
    # tunggu captcha / WA dialog / dll
    for i in range(15):
        time.sleep(2)
        body = p.evaluate("()=>document.body.innerText||''")
        if any(k in body.lower() for k in ("geser", "whatsapp", "kirim ke", "verifikasi", "kode", "captcha", "puzzle")):
            print(f"[PAGE-{i}]", body[:350].replace("\n", " | "), flush=True)
            break
    p.screenshot(path="/root/shopee-farm/shots/captcha_signup.png", full_page=True)
    json.dump(SNAP, open("/root/shopee-farm/captcha_signup_calls.json", "w"), indent=1)
    print("[*] saved shots/captcha_signup.png + captcha_signup_calls.json", flush=True)
    time.sleep(30)   # biar sempet dilihat / manual solve
    b.close()
