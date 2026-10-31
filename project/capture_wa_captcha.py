#!/usr/bin/env python3
"""capture_wa_captcha.py — buka signup, isi nomor, klik sampai captcha/WA muncul.
Semua request lewat mitm (8888) → kestrap di capture/*.jsonl.
Tujuan: liat endpoint + payload anti_fraud/captcha + otp saat scene=signup.
"""
import sys, time, json
from playwright.sync_api import sync_playwright

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6287876125616"
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

    def on_resp(r):
        u = r.url
        if any(k in u for k in ("otp", "vcode", "captcha", "anti_fraud", "shpsec", "settings")):
            print(f"[NET] {r.request.method} {r.status} {u.split('?')[0][:100]}", flush=True)
            try:
                if r.request.method == "POST":
                    print("      REQ:", (r.request.post_data or "")[:280], flush=True)
                print("      RES:", (r.text() or "")[:280], flush=True)
            except Exception:
                pass
    p.on("response", on_resp)

    print("[*] goto signup", flush=True)
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    try:
        inp = p.locator("input[type='tel'], input[type='text']").first
        inp.click(); inp.type(PHONE, delay=50)
        print("[*] nomor diisi:", PHONE, flush=True)
    except Exception as e:
        print("fill err", str(e)[:120], flush=True)
    time.sleep(2)
    # klik tombol lanjut
    for label in ("BERIKUTNYA", "Berikutnya", "Lanjut", "Beli", "Buat Akun", "Daftar", "Login"):
        try:
            p.locator(f"button:has-text('{label}')").first.click(timeout=1800, force=True)
            print(f"[*] klik {label}", flush=True); time.sleep(4); break
        except Exception:
            pass
    time.sleep(5)
    body = p.evaluate("()=>document.body.innerText||''")
    print("[PAGE1]", body[:400].replace("\n", " | "), flush=True)
    # handle captcha kalau muncul 'geser' — biarin manual / tunggu
    for _ in range(10):
        time.sleep(2)
        body = p.evaluate("()=>document.body.innerText||''")
        if "whatsapp" in body.lower() or "kirim ke" in body.lower() or "otp" in body.lower():
            print("[PAGE-WA]", body[:400].replace("\n", " | "), flush=True)
            break
    # coba klik 'Kirim ke WhatsApp' / 'Metode Lain'
    for label in ("Kirim ke WhatsApp", "Metode Lain", "Lanjut"):
        try:
            p.locator(f"button:has-text('{label}'), div:has-text('{label}')").first.click(timeout=2000, force=True)
            print(f"[*] klik '{label}'", flush=True); time.sleep(4)
        except Exception:
            pass
    time.sleep(8)
    p.screenshot(path="/root/shopee-farm/shots/wa_captcha.png")
    print("[*] selesai — cek capture + shot", flush=True)
    time.sleep(3)
    b.close()
