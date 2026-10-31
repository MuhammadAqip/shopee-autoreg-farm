#!/usr/bin/env python3
"""SHOPEE AUTO-REGISTER — API-only solver (NO extension). Bot-ready.

Deliverable untuk Maker: solver mandiri memakai SadCaptcha REST API.
Tidak butuh Chrome extension — cocok untuk headless bot.

Alur:
  1. Buka signup Shopee (+proxy ID)
  2. Dismiss modal bahasa, fill nomor, submit
  3. TOS "Setuju" bila muncul
  4. LOOP CAPTCHA (canvas):
     a. extract puzzle (canvas.EkGpDI) + piece (canvas._0N0-Dn) -> B64
     b. POST sadcaptcha /puzzle -> slideXProportion
     c. drag grip -> prop * (track_w - grip_w)
     d. ulangi sampai lolos (<=6 attempt)
  5. Modal OTP WhatsApp -> klik "Kirim ke WhatsApp"
  6. tunggu field OTP / submit

Usage:
  xvfb-run -a python shopee_solver.py <PHONE> <API_KEY> [PROXY_PORT]
Env:
  SADCAPTCHA_KEY, SHOPEE_PROXY_PORT
"""
import os, sys, time, json, base64, math, random, re as _re
import requests
from playwright.sync_api import sync_playwright

# ---- config ----
PHONE   = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PHONE", "87876125616")
API_KEY = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("SADCAPTCHA_KEY", "")
PORT    = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("SHOPEE_PROXY_PORT", "10000")
PROXY_BASE = os.environ.get("SHOPEE_PROXY", "gb.vsproxy.org")
PROXY_USER = os.environ.get("SHOPEE_PROXY_USER", "8108c95881d0c4b2f18e__cr.id;sessttl.5")
PROXY_PASS = os.environ.get("SHOPEE_PROXY_PASS", "7dfd03c5eb868991")
API_BASE   = "https://www.sadcaptcha.com/api/v1"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ---- selector (Shopee ID, canvas-based) ----
PUZZLE_SEL = "aside[aria-modal=true] canvas.EkGpDI"
PIECE_SEL  = "aside[aria-modal=true] canvas._0N0-Dn"
GRIP_SEL   = "aside[aria-modal=true] div.dExCsf"
TRACK_SEL  = "aside[aria-modal=true] div.FVDNdI"

JS_STATE = """() => { const b=document.body.innerText||'';
    if(/kirim kode otp via|Kirim ke WhatsApp/i.test(b)) return 'OTP_MODAL';
    if(/kode verifikasi|Kirim Kode/i.test(b)) return 'OTP';
    if(/Simak Ketentuan Akun/i.test(b)) return 'TOS';
    if(/telah terjadi kesalahan|Terjadi kesalahan|Coba lagi/i.test(b)) return 'ERROR';
    if(/Geser untuk/i.test(b)) return 'CAPTCHA';
    return '?'; }"""


def state(p):
    return p.evaluate(JS_STATE)


def find_btn(p, pattern):
    return p.evaluate("""(pat) => { let f=null; const re=new RegExp(pat,'i');
        document.querySelectorAll('button,div,span,a').forEach(e=>{
            const t=(e.childElementCount===0?(e.textContent||''):'').trim();
            if(!f && re.test(t)){ const r=e.getBoundingClientRect();
                if(r.width>0&&r.height>0) f={x:r.x+r.width/2,y:r.y+r.height/2,tag:e.tagName}; }});
        return f; }""", pattern)


def canvas_b64(p, sel):
    return p.evaluate("""(sel) => { const c=document.querySelector(sel);
        return c ? c.toDataURL('image/png').split(',')[1] : null; }""", sel)


def api_puzzle(pz, pc):
    r = requests.post(f"{API_BASE}/puzzle?licenseKey={API_KEY}",
                      json={"puzzleImageB64": pz, "pieceImageB64": pc}, timeout=40)
    if r.status_code != 200:
        return None
    return r.json().get("slideXProportion")


def solve_captcha(p):
    """pola PERSIS ekstensi SadCaptcha solvePuzzle(). return prop."""
    time.sleep(1.0)
    gb = p.locator(GRIP_SEL).first.bounding_box()
    if not gb:
        return None
    cx = gb["x"] + gb["width"] / 2
    cy = gb["y"] + gb["height"] / 2
    p.mouse.move(cx, cy); time.sleep(0.13)
    p.mouse.down(); time.sleep(0.13)
    pre = 10
    for i in range(1, pre):
        p.mouse.move(cx + i, cy - math.log(i) + random.random() * 3)
        time.sleep(random.random() * 0.005 + 0.01)
    pz = canvas_b64(p, PUZZLE_SEL)
    pc = canvas_b64(p, PIECE_SEL)
    if pz:
        open(f"/root/shopee-farm/shots/apz_{p.url[-6:]}_{random.randint(0,999)}.png", "wb").write(base64.b64decode(pz))
    if not pz or not pc:
        p.mouse.up(); return None
    prop = api_puzzle(pz, pc)
    if prop is None:
        p.mouse.up(); return None
    # distance = PUZZLE WIDTH * prop  (pola ekstensi)
    pw = p.evaluate("""()=>{const c=document.querySelector('canvas.EkGpDI');
        return c?c.getBoundingClientRect().width:280;}""")
    distance = pw * prop
    i = 1.0
    while i < distance - pre:
        x = cx + i + pre
        y = cy - math.log(i) + random.random() * 3
        p.mouse.move(x, y)
        time.sleep(random.random() * 0.005 + 0.01)
        i += random.random() * 5
    time.sleep(0.134)
    p.mouse.move(cx + distance, cy)
    time.sleep(0.134)
    p.mouse.up()
    time.sleep(3.0)
    return prop


def dismiss_lang(p):
    for _ in range(12):
        if not p.evaluate("()=>/Pilih bahasa Anda/i.test(document.body.innerText||'')"):
            return
        try:
            loc = p.locator("button:has-text('Bahasa Indonesia')").first
            if loc.count() and loc.is_visible():
                loc.click(timeout=2000)
        except Exception:
            pass
        time.sleep(1.5)


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=False,
                               args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(
            user_agent=UA, locale="id-ID",
            proxy={"server": f"http://{PROXY_BASE}:{PORT}",
                   "username": PROXY_USER, "password": PROXY_PASS},
            extra_http_headers={"Accept-Language": "id-ID,id;q=0.9,en;q=0.8"},
            viewport={"width": 1280, "height": 900})
        ctx.add_cookies([{"name": "shopee_webLanguage", "value": "id",
                          "domain": ".shopee.co.id", "path": "/"}])
        p = ctx.new_page()
        p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
        try: p.wait_for_load_state("networkidle", timeout=18000)
        except Exception: pass
        time.sleep(3)
        dismiss_lang(p)
        for _ in range(10):
            if p.evaluate("()=>document.querySelectorAll('input').length") > 0:
                break
            time.sleep(1)
        # fill nomor
        p.evaluate("""(ph)=>{const inp=document.querySelector('input:not([type=checkbox])');
            if(!inp)return; const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            set.call(inp, ph); inp.dispatchEvent(new Event('input',{bubbles:true}));
            inp.dispatchEvent(new Event('change',{bubbles:true}));}""", PHONE)
        time.sleep(1)
        # submit
        btn = find_btn(p, r"^berikutnya$|^next$")
        if btn:
            p.mouse.click(btn["x"], btn["y"])
        else:
            p.keyboard.press("Enter")
        time.sleep(3)

        # loop utama
        result = {"phone": PHONE, "stage": None, "attempts": 0}
        for i in range(90):
            time.sleep(2)
            st = state(p)
            if st == "TOS":
                t = find_btn(p, r"^setuju$|^saya setuju$")
                if t: p.mouse.click(t["x"], t["y"])
            elif st == "CAPTCHA":
                # tunggu "Memuat..." hilang (captcha siap)
                for _w in range(20):
                    if p.evaluate("()=>!/Memuat/i.test(document.body.innerText||'')"):
                        break
                    time.sleep(1)
                time.sleep(3)  # jeda ekstra (pola ekstensi sleep 3000)
                result["attempts"] += 1
                prop = solve_captcha(p)
                print(f"  captcha attempt {result['attempts']}: prop={prop}")
                if result["attempts"] >= 6:
                    break
            elif st == "OTP_MODAL":
                print("  >>> OTP MODAL: klik Kirim ke WhatsApp")
                t = find_btn(p, r"kirim ke whatsapp|kirim kode|kirim otp|kirim")
                if t:
                    p.mouse.click(t["x"], t["y"])
                    time.sleep(4)
                result["stage"] = "otp_modal_sent"
            elif st == "OTP":
                print("  >>> OTP FIELD muncul")
                result["stage"] = "otp"
                break
            elif st == "ERROR":
                result["stage"] = "error"
                break
        if result["stage"] is None:
            result["stage"] = state(p)
        p.screenshot(path=f"/root/shopee-farm/shots/bot_{PHONE}_{result['stage']}.png")
        print(json.dumps(result))


if __name__ == "__main__":
    main()
