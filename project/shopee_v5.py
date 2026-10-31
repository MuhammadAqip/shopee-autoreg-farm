#!/usr/bin/env python3
"""Shopee solver v5 FINAL — replikasi dragWithPreciseMonitoring + break condition.

Pola dari script.ts ekstensi SadCaptcha (fungsi solvePuzzleV2 + dragWithPreciseMonitoring):
  1. puzzle/piece img -> API /puzzle -> slideXProportion
  2. distance = puzzleWidth * prop - 3
  3. drag BERTAHAP dengan:
     - natural approach (cubic bezier dari kiri-bawah)
     - mousedown + dragstart
     - waypoints (3-6 segmen) yang melengkung
     - BREAK CONDITION: pantau piece translateX >= distance -> stop
     - final micro-adjustments
     - HOLD di posisi akhir (0-1000ms)
     - mouseup + dragend
  4. checkCaptchaSuccess: cari text "Verification complete" / modal OTP hilang

selectors Shopee ID (canvas):
  PUZZLE  = aside[aria-modal=true] canvas.EkGpDI        (width ~280)
  PIECE   = aside[aria-modal=true] div._7Sd2jx           (translateX wrapper)
  GRIP    = aside[aria-modal=true] div.dExCsf            (drag button, 40x40)

Usage: xvfb-run -a python shopee_v5.py <PHONE> <KEY> [PORT]
"""
import os, sys, time, json, base64, math, random, re
import requests
from playwright.sync_api import sync_playwright

PHONE = sys.argv[1] if len(sys.argv) > 1 else ""
API_KEY = sys.argv[2] if len(sys.argv) > 2 else ""
PORT = sys.argv[3] if len(sys.argv) > 3 else "10000"
PROXY_BASE = "gb.vsproxy.org"
PROXY_USER = "8108c95881d0c4b2f18e__cr.id;sessttl.5"
PROXY_PASS = "7dfd03c5eb868991"
API_BASE = "https://www.sadcaptcha.com/api/v1"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

PUZ = "aside[aria-modal=true] canvas.EkGpDI"
PIECE_WRAP = "aside[aria-modal=true] div._7Sd2jx"
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
        if p.evaluate("()=>!/Memuat/i.test(document.body.innerText||''"): return True
        time.sleep(1)
    return False

def piece_tx(p):
    """amb-il translateX piece wrapper (px)."""
    return p.evaluate("""()=>{const e=document.querySelector('aside[aria-modal=true] div._7Sd2jx');
        if(!e) return -1;
        const m=(e.getAttribute('style')||'').match(/translateX\\(([-0-9.]+)px\\)/);
        return m?parseFloat(m[1]):0;}""")

def bezier_curve(sx, sy, ex, ey, steps):
    cp = {"x": sx + (ex-sx)*(0.3+random.random()*0.4), "y": sy + (random.random()*12-6)}
    pts = []
    for i in range(steps+1):
        t = i/steps
        x = (1-t)**2*sx + 2*(1-t)*t*cp["x"] + t**2*ex
        y = (1-t)**2*sy + 2*(1-t)*t*cp["y"] + t**2*ey
        pts.append((x, y))
    return pts

def precise_drag(p, target_distance):
    """replikasi dragWithPreciseMonitoring (versi ringkas tapi setia)."""
    gb = p.locator(GRIP).first.bounding_box()
    if not gb: return False
    sx = gb["x"] + gb["width"]/2
    sy = gb["y"] + gb["height"]/2
    endX = sx + target_distance
    # 1. natural approach (dari kiri-bawah)
    apx = sx - 80 - random.random()*40
    apy = sy + 40 + random.random()*30
    for (x, y) in bezier_curve(apx, apy, sx, sy, 8+int(random.random()*4)):
        p.mouse.move(x, y); time.sleep(0.015+random.random()*0.025)
    time.sleep(0.2+random.random()*0.15)
    p.mouse.move(sx+random.random()*1.5-0.75, sy+random.random()*1.5-0.75)
    time.sleep(0.35+random.random()*0.2)
    # 2. mousedown
    p.mouse.move(sx, sy); p.mouse.down()
    time.sleep(0.18+random.random()*0.12)
    ix = sx + 2 + random.random()*1.5
    p.mouse.move(ix, sy+random.random()*1-0.5)
    time.sleep(0.12+random.random()*0.08)
    # 3. waypoints
    nseg = 3 + int(random.random()*3)
    wps = []
    for i in range(1, nseg+1):
        tx = sx + target_distance*(i/nseg)*(0.85+random.random()*0.3)
        ty = sy + math.sin(i/nseg*math.pi)*(random.random()*4-2)
        wps.append((tx, ty))
    wps.append((endX, sy+random.random()*1.2-0.6))
    lastx, lasty = ix, sy
    for i, (px, py) in enumerate(wps):
        if piece_tx(p) >= target_distance - 3:
            break
        for (cx, cy) in bezier_curve(lastx, lasty, px, py, 10+int(random.random()*8)):
            if piece_tx(p) >= target_distance - 3:
                break
            p.mouse.move(cx+random.random()*0.6-0.3, cy+random.random()*0.6-0.3)
            slowdown = i >= len(wps)-2
            time.sleep((0.020 if slowdown else 0.008) + random.random()*(0.015 if slowdown else 0.008))
        if random.random() < 0.3 and i < len(wps)-1:
            time.sleep(0.08+random.random()*0.12)
        lastx, lasty = px, py
    # 4. final micro-adjust
    for i in range(4+int(random.random()*3)):
        if piece_tx(p) >= target_distance - 3: break
        prec = 1 - i/(4+int(random.random()*3))
        lastx += (random.random()*1.0-0.5)*prec*0.8
        lasty += (random.random()*0.8-0.4)*prec*0.8
        p.mouse.move(lastx, lasty)
        time.sleep(0.12+random.random()*0.18)
    # 5. hold
    time.sleep(random.random()*1.0)
    p.mouse.move(lastx+random.random()*0.3-0.15, lasty+random.random()*0.3-0.15)
    time.sleep(0.05+random.random()*0.03)
    p.mouse.up()
    return piece_tx(p) >= target_distance - 5

def solve_once(p):
    time.sleep(0.8)
    pz = cap(p, PUZ)
    pc = cap(p, "aside[aria-modal=true] canvas._0N0-Dn")
    if not pz or not pc: return None
    r = requests.post(f"{API_BASE}/puzzle?licenseKey={API_KEY}",
                      json={"puzzleImageB64": pz, "pieceImageB64": pc}, timeout=40)
    if r.status_code != 200:
        return {"err": r.status_code, "txt": r.text[:150]}
    prop = r.json().get("slideXProportion")
    # distance = puzzleWidth * prop - 3  (pola ekstensi)
    pw = p.evaluate("()=>{const c=document.querySelector('aside[aria-modal=true] canvas.EkGpDI');return c?c.getBoundingClientRect().width:280;}")
    distance = pw * prop - 3
    ok = precise_drag(p, distance)
    time.sleep(3.0)
    return {"prop": prop, "dist": round(distance,1), "piece_reached": ok}

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
        time.sleep(5)
        # dismiss language modal (agresif + konfirmasi hilang)
        for _ in range(25):
            has = p.evaluate("()=>/Pilih bahasa Anda/i.test(document.body.innerText||'')")
            if not has:
                break
            try:
                loc = p.locator("button:has-text('Bahasa Indonesia')").first
                if loc.count():
                    loc.click(timeout=2500, force=True)
                    print("  dismissed lang modal")
            except Exception:
                try:
                    loc = p.locator("text=Bahasa Indonesia").first
                    loc.click(timeout=2000, force=True)
                except Exception: pass
            time.sleep(1.5)
        # tunggu modal benar-benar hilang
        for _ in range(15):
            if not p.evaluate("()=>/Pilih bahasa Anda/i.test(document.body.innerText||'')"): break
            time.sleep(1)
        print("  lang modal gone:", not p.evaluate("()=>/Pilih bahasa Anda/i.test(document.body.innerText||'')"))
        for _ in range(10):
            if p.evaluate("()=>document.querySelectorAll('input').length")>0: break
            time.sleep(1)
        # fill + submit pakai driver terbukti
        try:
            from tools.signup_driver import fill_field, click_submit
            fill_field(p, "phone", PHONE); time.sleep(1); click_submit(p)
        except Exception as e:
            print("driver err:", e)
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
                info = solve_once(p)
                print(f"  attempt {res['attempts']}: {info}")
                if res["attempts"] >= 4: break
            elif st == "OTP_MODAL":
                print("  >>> OTP MODAL"); 
                t = find_btn(p, r"kirim ke whatsapp|kirim kode|kirim")
                if t: p.mouse.click(t["x"], t["y"]); time.sleep(4)
                res["stage"] = "otp_modal_sent"; break
            elif st == "OTP":
                res["stage"] = "otp"; break
            elif st == "ERROR":
                res["stage"] = "error"; break
        if res["stage"] is None: res["stage"] = state(p)
        p.screenshot(path=f"/root/shopee-farm/shots/v5_{PHONE}_{str(res['stage']).replace('?','_')}.png")
        print(json.dumps(res))

if __name__ == "__main__":
    main()
