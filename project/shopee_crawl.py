#!/usr/bin/env python3
"""Shopee solver v4 — IMAGE-CRAWL (trajectory) + PRE-ANALYZE.

Hipotesis: Shopee ID captcha = image-crawl (piece geser sepanjang jalur
melengkung), bukan puzzle-slide. Puppet:
  1. PRE-ANALYZE: POST /shopee-image-crawl-pre-analyze {image_b64} -> slideXProportion
  2. SWEEP: drag grip diagonal ke atas (rekam trajectory) -> release
  3. CRAWL: POST /shopee-image-crawl {puzzle_image_b64, piece_image_b64, slide_piece_trajectory}
     -> pixelsFromSliderOrigin
  4. DRAG horizontal ke pixelsFromSliderOrigin (dengan overshoot)

Pola dari ekstensi SadCaptcha script.js (solveImageCrawl / imageCrawl*ApiCall).

Usage:
  xvfb-run -a python shopee_solver.py <PHONE> <KEY> [PORT] --crawl
"""
import os, sys, time, json, base64, math, random
import requests
from playwright.sync_api import sync_playwright

PHONE   = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PHONE", "")
API_KEY = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("SADCAPTCHA_KEY", "")
PORT    = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("SHOPEE_PROXY_PORT", "10000")
PROXY_BASE = os.environ.get("SHOPEE_PROXY", "gb.vsproxy.org")
PROXY_USER = os.environ.get("SHOPEE_PROXY_USER", "8108c95881d0c4b2f18e__cr.id;sessttl.5")
PROXY_PASS = os.environ.get("SHOPEE_PROXY_PASS", "7dfd03c5eb868991")
API_BASE   = "https://www.sadcaptcha.com/api/v1"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

PUZ = "aside[aria-modal=true] canvas.EkGpDI"
PIE = "aside[aria-modal=true] canvas._0N0-Dn"
GRIP = "aside[aria-modal=true] div.dExCsf"

JS_STATE = """() => { const b=document.body.innerText||'';
    if(/kirim kode otp via|Kirim ke WhatsApp/i.test(b)) return 'OTP_MODAL';
    if(/kode verifikasi|Kirim Kode/i.test(b)) return 'OTP';
    if(/Simak Ketentuan Akun/i.test(b)) return 'TOS';
    if(/Geser untuk|Verifikasi untuk/i.test(b)) return 'CAPTCHA';
    if(/telah terjadi kesalahan|Terjadi kesalahan/i.test(b)) return 'ERROR';
    return '?'; }"""

def state(p): return p.evaluate(JS_STATE)

def find_btn(p, pat):
    return p.evaluate("""(pat)=>{let f=null;const re=new RegExp(pat,'i');
        document.querySelectorAll('button,div,span,a').forEach(e=>{const t=(e.childElementCount===0?(e.textContent||''):'').trim();
        if(!f&&re.test(t)){const r=e.getBoundingClientRect();if(r.width>0&&r.height>0)f={x:r.x+r.width/2,y:r.y+r.height/2};}});return f;}""", pat)

def cap(p, sel):
    return p.evaluate("(s)=>{const c=document.querySelector(s);return c?c.toDataURL('image/png').split(',')[1]:null;}", sel)

def wait_ready(p, timeout=25):
    for _ in range(timeout):
        if p.evaluate("()=>!/Memuat/i.test(document.body.innerText||'')"):
            return True
        time.sleep(1)
    return False

def crawl_solve(p):
    """image-crawl: pre-analyze -> sweep trajectory -> API -> drag."""
    time.sleep(0.8)
    gb = p.locator(GRIP).first.bounding_box()
    if not gb: return None
    cx = gb["x"]+gb["width"]/2; cy = gb["y"]+gb["height"]/2
    p.mouse.move(cx, cy); time.sleep(0.13)
    p.mouse.down(); time.sleep(0.13)
    # prep 10px
    for i in range(1, 10):
        p.mouse.move(cx+i, cy-math.log(i)); time.sleep(0.01)
    pz = cap(p, PUZ); pc = cap(p, PIE)
    if not pz or not pc:
        p.mouse.up(); return None
    # sweep trajectory (naik diagonal) + rekam sesuai schema TrajectoryElement
    traj = []
    for i in range(10, 100, 6):
        x = cx+i; y = cy - i*0.5 + random.random()*4
        p.mouse.move(x, y)
        traj.append({
            "pixels_from_slider_origin": int(i),
            "piece_rotation_angle": 0.0,
            "piece_center": {
                "proportionX": 0.5,
                "proportionY": 0.5,
            },
        })
        time.sleep(0.02)
    # POST image-crawl
    body = {"puzzle_image_b64": pz, "piece_image_b64": pc, "slide_piece_trajectory": traj}
    r = requests.post(f"{API_BASE}/shopee-image-crawl?licenseKey={API_KEY}", json=body, timeout=40)
    if r.status_code != 200:
        p.mouse.up(); return {"err": r.status_code, "txt": r.text[:200]}
    px = r.json().get("pixelsFromSliderOrigin")
    # balikin ke origin, lalu drag horizontal + overshoot
    p.mouse.move(cx, cy); time.sleep(0.1)
    if px:
        for i in range(0, int(px), 8):
            p.mouse.move(cx+i, cy); time.sleep(0.01)
        p.mouse.move(cx+px+3, cy); time.sleep(0.13)
        p.mouse.move(cx+px, cy); time.sleep(0.13)
    p.mouse.up(); time.sleep(3.0)
    return px

def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=False, args=["--no-sandbox","--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=UA, locale="id-ID",
            proxy={"server": f"http://{PROXY_BASE}:{PORT}", "username": PROXY_USER, "password": PROXY_PASS},
            extra_http_headers={"Accept-Language": "id-ID,id;q=0.9,en;q=0.8"},
            viewport={"width": 1280, "height": 900})
        ctx.add_cookies([{"name":"shopee_webLanguage","value":"id","domain":".shopee.co.id","path":"/"}])
        p = ctx.new_page()
        p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
        try: p.wait_for_load_state("networkidle", timeout=18000)
        except Exception: pass
        time.sleep(4)
        for _ in range(12):
            if not p.evaluate("()=>/Pilih bahasa Anda/i.test(document.body.innerText||'')"): break
            try:
                loc = p.locator("button:has-text('Bahasa Indonesia')").first
                if loc.count() and loc.is_visible(): loc.click(timeout=2000)
            except Exception: pass
            time.sleep(1.5)
        for _ in range(10):
            if p.evaluate("()=>document.querySelectorAll('input').length")>0: break
            time.sleep(1)
        p.evaluate("""(ph)=>{const inp=document.querySelector('input:not([type=checkbox])');if(!inp)return;
            const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            set.call(inp,ph);inp.dispatchEvent(new Event('input',{bubbles:true}));inp.dispatchEvent(new Event('change',{bubbles:true}));}""", PHONE)
        time.sleep(1)
        btn = find_btn(p, r"^berikutnya$|^next$")
        if btn: p.mouse.click(btn["x"], btn["y"])
        else: p.keyboard.press("Enter")
        time.sleep(3)
        res = {"phone": PHONE, "stage": None, "attempts": 0}
        for i in range(90):
            time.sleep(2)
            st = state(p)
            if st == "TOS":
                t = find_btn(p, r"^setuju$|^saya setuju$")
                if t: p.mouse.click(t["x"], t["y"])
            elif st == "CAPTCHA":
                wait_ready(p); time.sleep(3)
                res["attempts"] += 1
                px = crawl_solve(p)
                print(f"  crawl attempt {res['attempts']}: px={px}")
                if res["attempts"] >= 6: break
            elif st == "OTP_MODAL":
                print("  >>> OTP MODAL")
                t = find_btn(p, r"kirim ke whatsapp|kirim kode|kirim")
                if t: p.mouse.click(t["x"], t["y"]); time.sleep(4)
                res["stage"] = "otp_modal_sent"
            elif st == "OTP":
                res["stage"] = "otp"; break
            elif st == "ERROR":
                res["stage"] = "error"; break
        if res["stage"] is None: res["stage"] = state(p)
        p.screenshot(path=f"/root/shopee-farm/shots/cw_{PHONE}_{res['stage'].replace('?','_')}.png")
        print(json.dumps(res))

if __name__ == "__main__":
    main()
