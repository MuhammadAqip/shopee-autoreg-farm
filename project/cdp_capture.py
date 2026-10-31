#!/usr/bin/env python3
"""cdp_capture.py — capture request/response body via Playwright CDP (tanpa mitm).
Browser pakai VS proxy langsung (SPA render OK), Playwright dump semua /api + otp + captcha.
"""
import sys, time, json, os
from playwright.sync_api import sync_playwright

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6289601416330"
PROXY = open("/root/shopee-farm/proxies_id_vs.txt").readline().strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
OUT = "/root/shopee-farm/capture/cdp_%s.jsonl" % time.strftime("%Y%m%d_%H%M%S")
os.makedirs("/root/shopee-farm/capture", exist_ok=True)
F = open(OUT, "w")

def save(rec):
    try:
        F.write(json.dumps(rec, ensure_ascii=False) + "\n"); F.flush()
    except Exception: pass

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False,
                           args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    c = b.new_context(user_agent=UA, locale="id-ID", proxy={
        "server": "http://" + PROXY.split("@")[-1],
        "username": PROXY.split("//")[1].split(":")[0],
        "password": PROXY.split("//")[1].split("@")[0].split(":", 1)[1],
    }, ignore_https_errors=True, viewport={"width": 1280, "height": 900})
    p = c.new_page()

    reqs = {}

    def on_req(r):
        u = r.url
        if any(k in u for k in ("/api/", "otp", "captcha", "anti_fraud", "shpsec", "vcode")):
            reqs[r] = {"method": r.method, "url": u, "headers": dict(r.headers),
                       "body": (r.post_data or "")}

    def on_resp(r):
        if r.request in reqs:
            rec = dict(reqs[r.request])
            rec["status"] = r.status
            try:
                rec["resp"] = (r.text() or "")[:5000]
            except Exception:
                rec["resp"] = ""
            save(rec)
            print(f"[CAP] {rec['method']} {rec['status']} {rec['url'].split('?')[0][-45:]}", flush=True)
            if rec["body"]:
                print("      REQ:", rec["body"][:200], flush=True)
            if rec["resp"]:
                print("      RES:", rec["resp"][:200], flush=True)

    p.on("request", on_req)
    p.on("response", on_resp)

    print("[*] goto signup (direct VS proxy)", flush=True)
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(20)
    # dismiss modal 'Pilih bahasa Anda'
    try:
        btn = p.locator("button.shopee-button-outline").first
        if btn.count():
            btn.click(timeout=3000, force=True)
            print("[*] dismiss modal: Bahasa Indonesia", flush=True)
            time.sleep(4)
    except Exception as e:
        print("modal err", str(e)[:80], flush=True)
    time.sleep(2)
    n = p.evaluate("()=>document.querySelectorAll('input').length")
    print("[inputs]", n, flush=True)
    # isi nomor ke input[name=phone]
    try:
        inp = p.locator("input[name='phone']").first
        inp.click(timeout=3000)
        inp.type(PHONE, delay=45)
        print("[*] nomor diisi:", PHONE, flush=True)
    except Exception as e:
        print("fill err", str(e)[:100], flush=True)
    time.sleep(3)
    for label in ("BERIKUTNYA", "Berikutnya", "Lanjut"):
        try:
            p.locator(f"button:has-text('{label}')").first.click(timeout=2000, force=True)
            print(f"[*] klik {label}", flush=True); break
        except Exception: pass
    time.sleep(10)
    body = p.evaluate("()=>document.body.innerText||''")
    print("[PAGE]", body[:350].replace("\n", " | "), flush=True)
    p.screenshot(path="/root/shopee-farm/shots/cdp_capture.png", full_page=True)
    F.close()
    json.dump({"cdp_file": OUT}, open("/root/shopee-farm/last_cdp.json", "w"))
    print("[SAVED]", OUT, flush=True)
    time.sleep(2)
    b.close()
