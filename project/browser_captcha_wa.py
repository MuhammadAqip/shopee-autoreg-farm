#!/usr/bin/env python3
"""browser_captcha_wa.py — A: browser solve captcha (reuse solver shopee_hold) → WA.
Capture SEMUA: get_settings/get_config/generate/verify_v2/send_vcode.
"""
import sys, time, json, random, importlib.util
from playwright.sync_api import sync_playwright

# import helper solver dari shopee_hold.py (tanpa jalanin main)
spec = importlib.util.spec_from_file_location("sh", "/root/shopee-farm/shopee_hold.py")
SH = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(SH)
except SystemExit:
    pass

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6285849159568"
KEY = open("/root/shopee-farm/bot_key.txt").read().strip()
PROXY = open("/root/shopee-farm/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]
USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
LOG = open("/root/shopee-farm/capture/captcha_wa_flow.jsonl", "a")

def rec(d):
    LOG.write(json.dumps(d, ensure_ascii=False) + "\n"); LOG.flush()

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False,
                           args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://" + HOST, "username": USER, "password": PASS},
                      ignore_https_errors=True, viewport={"width": 1280, "height": 900})
    c.add_cookies([{"name": "shopee_webLanguage", "value": "id",
                    "domain": ".shopee.co.id", "path": "/"}])
    p = c.new_page()

    held = {}
    def on_req(r):
        u = r.url
        if any(k in u for k in ("captcha", "anti_fraud", "otp", "vcode", "shpsec", "get_settings")):
            held[r] = {"method": r.method, "url": u, "body": r.post_data or ""}
    def on_resp(r):
        if r.request in held:
            e = dict(held[r.request]); e["status"] = r.status
            try: e["resp"] = (r.text() or "")[:4000]
            except Exception: e["resp"] = ""
            rec(e)
            print(f"[CAP] {e['method']} {e['status']} {e['url'].split('?')[0][-45:]}", flush=True)
            if "send_vcode" in e["url"] or "verify_v2" in e["url"]:
                print("   REQ:", e["body"][:150], flush=True)
                print("   RES:", e["resp"][:200], flush=True)
    p.on("request", on_req); p.on("response", on_resp)

    print("[1] goto signup", flush=True)
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    try:
        p.wait_for_selector("input[name='phone']", timeout=45000)
        print("[1b] input muncul", flush=True)
    except Exception as e:
        print("[1b] err", str(e)[:70], flush=True)
    time.sleep(4)
    try:
        mb = p.locator("button.shopee-button-outline").first
        if mb.count() and mb.is_visible():
            mb.click(timeout=2500, force=True); print("[1c] modal bahasa tutup", flush=True); time.sleep(3)
    except Exception: pass
    try:
        inp = p.locator("input[name='phone']").first
        inp.wait_for(state="visible", timeout=15000)
        inp.click(timeout=5000); inp.type(PHONE, delay=45); print("[2] nomor diisi", flush=True)
    except Exception as e:
        print("fill err", str(e)[:70], flush=True)
    time.sleep(4)
    for lbl in ("BERIKUTNYA", "Berikutnya", "Lanjut"):
        try:
            p.locator(f"button:has-text('{lbl}')").first.click(timeout=3000, force=True)
            print(f"[3] klik {lbl}", flush=True); break
        except Exception: pass
    time.sleep(3)
    for i in range(8):
        try:
            ok = p.evaluate("""()=>{const els=[...document.querySelectorAll('button,a,div')];
              const t=[...els].reverse().find(e=>{const x=(e.innerText||'').trim();return x==='Setuju'||x==='SETUJU';});
              if(t){t.click();return true;}return false;}""")
            if ok:
                print(f"[4] klik Setuju (try {i+1})", flush=True); time.sleep(3); break
        except Exception: pass
        time.sleep(2)

    print("[5] tunggu captcha...", flush=True)
    for i in range(45):
        time.sleep(1.5)
        cs = p.evaluate("()=>[...document.querySelectorAll('canvas')].map(c=>({w:c.width,h:c.height,d:c.getAttribute('draggable')}))")
        if cs:
            print(f"   [{i}] canvases={cs}", flush=True)
            for w in range(12):
                if "Memuat" not in (p.evaluate("()=>document.body.innerText||''")):
                    break
                time.sleep(1.5)
            print("   [5b] widget ready", flush=True)
            try:
                res = SH.solve_image_crawl(p, KEY)
                print(f"   [SOLVE] {res}", flush=True)
            except Exception as e:
                print(f"   [SOLVE] err {str(e)[:130]}", flush=True)
            break

    print("[6] tunggu hasil solve (verify/send auto)...", flush=True)
    for i in range(30):
        time.sleep(2)
        body = p.evaluate("()=>document.body.innerText||''")
        if any(k in body.lower() for k in ("whatsapp", "kirim ke", "kode", "verifikasi berhasil", "kirim otp", "masukkan kode")):
            print(f"   [{i}] PAGE: {body[:250]}", flush=True)
            break
    body = p.evaluate("()=>document.body.innerText||''")
    print("[6b] FINAL PAGE:", body[:400].replace("\n", " | "), flush=True)
    p.screenshot(path="/root/shopee-farm/shots/browser_captcha_wa.png", full_page=True)
    # kalau ada dialog WA → klik 'Kirim ke WhatsApp'
    try:
        ok = p.evaluate("""()=>{const els=[...document.querySelectorAll('button,div,a')];
          const t=els.find(e=>{const x=(e.innerText||'').trim();return x==='Kirim ke WhatsApp'||x.includes('Kirim ke WhatsApp')||x==='Kirim WhatsApp';});
          if(t){t.click();return true;}return false;}""")
        if ok:
            print("[7] klik 'Kirim ke WhatsApp'", flush=True); time.sleep(7)
    except Exception: pass
    time.sleep(6)
    CK = {ck["name"]: ck["value"] for ck in c.cookies()}
    json.dump({"phone": PHONE, "cookies": CK}, open("/root/shopee-farm/captcha_wa_state.json", "w"))
    p.screenshot(path="/root/shopee-farm/shots/wa_after_solve.png", full_page=True)
    print("[8] SAVED", flush=True)
    time.sleep(3)
    c.close(); b.close()
