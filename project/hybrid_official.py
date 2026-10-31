#!/usr/bin/env python3
"""hybrid_official.py — pipeline resmi: browser tipis (headless opsional) → SadCaptcha official API → capture.

Alur:
  signup → setuju TOS → captcha IMAGE_CRAWL
  → sadcaptcha_official.solve_image_crawl (pre-analyze → sweep traj → image-crawl → swing)
  → halaman auto-lanjut ke OTP_MODAL (WA)
Capture semua request ke capture/hybrid_flow.jsonl.
Usage: hybrid_official.py <PHONE> [--headless]
"""
import sys, time, json
from playwright.sync_api import sync_playwright
import sadcaptcha_official as SAD

ROOT = "/root/shopee-farm"
PHONE = sys.argv[1] if len(sys.argv) > 1 else "85729884050"
HEADLESS = "--headless" in sys.argv
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
KEY = open(f"{ROOT}/bot_key.txt").read().strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
LOG = open(f"{ROOT}/capture/hybrid_flow.jsonl", "a")
def rec(d): LOG.write(json.dumps(d, ensure_ascii=False)+"\n"); LOG.flush()

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=HEADLESS, args=["--no-sandbox",
        "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage",
        "--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server":"http://"+HOST,"username":USER,"password":PASS},
                      ignore_https_errors=True, viewport={"width":1280,"height":900})
    c.add_cookies([{"name":"shopee_webLanguage","value":"id","domain":".shopee.co.id","path":"/"}])
    p = c.new_page()
    held = {}
    def on_req(r):
        u = r.url
        if any(k in u for k in ("captcha","anti_fraud","otp","vcode")):
            held[r] = {"m":r.method,"u":u,"b":r.post_data or ""}
    def on_resp(r):
        if r.request in held:
            e = dict(held[r.request]); e["s"] = r.status
            try: e["r"] = (r.text() or "")[:2000]
            except Exception: e["r"] = ""
            rec(e)
    p.on("request", on_req); p.on("response", on_resp)

    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    p.wait_for_selector("input[name='phone']", timeout=45000); time.sleep(4)
    try:
        mb = p.locator("button.shopee-button-outline").first
        if mb.count() and mb.is_visible(): mb.click(timeout=2500, force=True); time.sleep(3)
    except Exception: pass
    inp = p.locator("input[name='phone']").first; inp.click(timeout=5000); inp.type(PHONE, delay=45)
    time.sleep(4)
    for lbl in ("BERIKUTNYA","Berikutnya"):
        try: p.locator(f"button:has-text('{lbl}')").first.click(timeout=3000, force=True); break
        except Exception: pass
    time.sleep(3)
    for i in range(8):
        ok = p.evaluate("""()=>{const t=[...document.querySelectorAll('button,a,div')].reverse().find(e=>{const x=(e.innerText||'').trim();return x==='Setuju'||x==='SETUJU';});if(t){t.click();return true;}return false;}""")
        if ok: time.sleep(3); break
        time.sleep(2)
    # tunggu captcha (presence #NEW_CAPTCHA / #captchaMask)
    got = False
    for i in range(60):
        time.sleep(1.5)
        if p.evaluate("""()=>!!document.querySelector('#NEW_CAPTCHA, #captchaMask, #puzzleImgComponent')"""):
            got = True; print("[hyb] captcha presence terdeteksi", flush=True); break
    if not got:
        print("[hyb] captcha tidak muncul; body:", p.evaluate("()=>document.body.innerText||''")[:150].replace(chr(10)," | "), flush=True)
    for w in range(16):
        if "Memuat" not in p.evaluate("()=>document.body.innerText||''"): break
        time.sleep(1.5)

    def refresh():
        try:
            p.evaluate("""()=>{const s=document.querySelector("#NEW_CAPTCHA svg[viewBox='0 0 16 16'], aside svg[viewBox='0 0 16 16']");if(s){const r=s.getBoundingClientRect();s.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:r.x+r.width/2,clientY:r.y+r.height/2}));}}""")
        except Exception: pass
        time.sleep(3)

    sol = SAD.solve_image_crawl(p, KEY, refresh_fn=refresh)
    print("[hyb] solution:", sol, flush=True)
    time.sleep(6)
    body = p.evaluate("()=>document.body.innerText||''")
    print("[hyb][PAGE]", body[:250].replace("\n", " | "), flush=True)
    p.screenshot(path=f"{ROOT}/shots/hybrid_official.png")
    print("[hyb] done. send_otp fired?", "send_otp" in "".join(str(k) for k in held), flush=True)
    time.sleep(2); c.close(); b.close()
