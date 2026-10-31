#!/usr/bin/env python3
"""prewarm_cache.py — #5: bangun cache puzzle captcha offline (tanpa daftar).

Buka captcha, ambil puzzle+piece, klik RESET (refresh) → hash puzzle → simpan.
Loop N kali. Cache ini dipakai saat registrasi (puzzle sama = skip SadCaptcha = hemat kredit).
TIDAK butuh nomor fresh/OTP — cukup captcha ter-render.

Usage: prewarm_cache.py [ROUNDS] [--headless]
"""
import sys, time, json, hashlib
from playwright.sync_api import sync_playwright

ROOT = "/root/shopee-farm"
ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 30
HEADLESS = "--headless" in sys.argv
PHONE = "6285602999999"  # dummy format-valid (nggak akan didaftarkan)
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
IC_PUZZLE = "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false], div:not(#puzzleContainer) > img"
IC_PIECE = "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true], #puzzleContainer > #puzzleImgComponent"


def dataurl(p, sel):
    return p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;
      if(e.tagName==='CANVAS'){try{return e.toDataURL('image/png').split(',')[1];}catch(x){return null;}}
      const src=e.getAttribute('src')||e.src||'';return src.split(',')[1]||null;}""", sel)


def click_reset(p):
    return p.evaluate("""()=>{const s=document.querySelector("#NEW_CAPTCHA svg[viewBox='0 0 16 16'], aside svg[viewBox='0 0 16 16']");
      if(s){const r=s.getBoundingClientRect();s.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:r.x+r.width/2,clientY:r.y+r.height/2}));return true;}return false;}""")


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", "--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://" + HOST, "username": USER, "password": PASS},
                      ignore_https_errors=True, viewport={"width": 1280, "height": 900})
    c.add_cookies([{"name": "shopee_webLanguage", "value": "id", "domain": ".shopee.co.id", "path": "/"}])
    p = c.new_page()
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    p.wait_for_selector("input[name='phone']", timeout=45000); time.sleep(4)
    try:
        mb = p.locator("button.shopee-button-outline").first
        if mb.count() and mb.is_visible(): mb.click(timeout=2500, force=True); time.sleep(3)
    except Exception: pass
    inp = p.locator("input[name='phone']").first; inp.click(timeout=5000); inp.type(PHONE, delay=45); time.sleep(4)
    for lbl in ("BERIKUTNYA", "Berikutnya"):
        try: p.locator(f"button:has-text('{lbl}')").first.click(timeout=3000, force=True); break
        except Exception: pass
    time.sleep(3)
    for i in range(8):
        ok = p.evaluate("""()=>{const t=[...document.querySelectorAll('button,a,div')].reverse().find(e=>{const x=(e.innerText||'').trim();return x==='Setuju'||x==='SETUJU';});if(t){t.click();return true;}return false;}""")
        if ok: time.sleep(3); break
        time.sleep(2)
    # tunggu captcha
    for i in range(50):
        time.sleep(1.5)
        if p.evaluate("()=>!!document.querySelector('#NEW_CAPTCHA, #captchaMask, #puzzleImgComponent')"): break

    from captcha_cache import CaptchaCache
    cc = CaptchaCache()
    got = 0
    for rnd in range(ROUNDS):
        # tunggu render
        for w in range(10):
            if "Memuat" not in p.evaluate("()=>document.body.innerText||''"): break
            time.sleep(1)
        pz = dataurl(p, IC_PUZZLE); pc = dataurl(p, IC_PIECE)
        if pz and pc and len(pz) > 200:
            h = hashlib.sha256((pz or "").encode()).hexdigest()
            have = cc.lookup(pz, pc)
            got += 1
            print(f"[{rnd}] puzzle #{got} hash={h[:12]} cached={'YES' if have is not None else 'no'}", flush=True)
            # simpan placeholder prop (0) supaya hash terdaftar; prop asli diisi saat solve nyata
            if have is None:
                try: cc.record(pz, pc, 0.0)
                except Exception: pass
        # refresh
        if not click_reset(p):
            print(f"[{rnd}] tombol reset tak ketemu, stop"); break
        time.sleep(2.5)
    print(f"[prewarm] total puzzle dilihat={got}")
    b.close()
