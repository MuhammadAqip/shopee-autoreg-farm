#!/usr/bin/env python3
"""capture_wa_flow.py — buka signup via mitm, isi nomor, tunggu/dump semua API OTP.
Tujuan: liat endpoint + params PERSIS saat 'Kirim ke WhatsApp' diklik.
"""
import sys, time, json
from playwright.sync_api import sync_playwright

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6285849156988"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://127.0.0.1:8888"},  # via mitm
                      ignore_https_errors=True,
                      viewport={"width": 1280, "height": 900})
    p = c.new_page()

    # log semua API OTP yang lewat (di browser juga)
    def on_resp(r):
        u = r.url
        if "otp" in u or "send_vcode" in u or "settings" in u or "vcode" in u:
            print(f"[NET] {r.request.method} {r.status} {u[:110]}", flush=True)
            try:
                if r.request.method == "POST":
                    print("      REQ:", (r.request.post_data or "")[:250], flush=True)
                print("      RES:", (r.text() or "")[:250], flush=True)
            except Exception:
                pass
    p.on("response", on_resp)

    print("[*] goto signup", flush=True)
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    # isi nomor
    try:
        inp = p.locator("input[type='tel'], input[type='text']").first
        inp.click(); inp.type(PHONE, delay=50)
        print("[*] nomor diisi", flush=True)
    except Exception as e:
        print("fill err", str(e)[:120], flush=True)
    time.sleep(2)
    # klik Lanjut / Beli
    for label in ("Lanjut", "Beli", "Buat Akun", "Daftar", "Login"):
        try:
            p.locator(f"button:has-text('{label}')").first.click(timeout=1500, force=True)
            print(f"[*] klik {label}", flush=True); time.sleep(3); break
        except Exception:
            pass
    # tunggu dialog & klik 'Kirim ke WhatsApp'
    time.sleep(4)
    body = p.evaluate("()=>document.body.innerText||''")
    print("[PAGE]", body[:300].replace("\n", " | "), flush=True)
    for label in ("Kirim ke WhatsApp", "Metode Lain", "Lanjut", "Verifikasi"):
        try:
            p.locator(f"button:has-text('{label}'), div:has-text('{label}')").first.click(timeout=2000, force=True)
            print(f"[*] klik '{label}'", flush=True); time.sleep(3)
        except Exception:
            pass
    time.sleep(6)
    print("[*] state akhir — cek mitm capture", flush=True)
    p.screenshot(path="/root/shopee-farm/shots/wa_flow.png")
    time.sleep(3)
    b.close()
