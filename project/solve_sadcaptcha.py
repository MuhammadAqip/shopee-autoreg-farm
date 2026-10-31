"""Shopee solver v3 — SadCaptcha API + canvas extraction + multi-attempt.

Struktur DOM Shopee ID (confirmed):
  PUZZLE: canvas.EkGpDI (280x150) | PIECE: canvas._0N0-Dn (44x44) | GRIP: div.dExCsf

Alur per attempt (pola SadCaptcha playwrightsolver.py):
  1. grip bbox -> center = start; mouse.down()
  2. prep-drag 10px (log curve)
  3. canvas puzzle/piece -> toDataURL -> b64
  4. POST /puzzle {puzzleImageB64, pieceImageB64} -> slideXProportion
  5. dist = prop * bar_width (bar_width = puzzle canvas width)
  6. drag start_x..dist (y=log), overshoot+back, up
  7. cek state; ulang <=5 (multi-attempt)
"""
import sys, time, json, base64, math, random, re as _re
sys.path.insert(0, '/root/shopee-farm')
import requests
from playwright.sync_api import sync_playwright
from tools.signup_driver import fill_field, click_submit

PHONE  = sys.argv[1] if len(sys.argv) > 1 else "87876125616"
PORT   = sys.argv[2] if len(sys.argv) > 2 else "10008"
API_KEY = sys.argv[3] if len(sys.argv) > 3 else "f231e3e4ea6ae4a5806fcfbc68513bfd"
PX = f'http://8108c95881d0c4b2f18e__cr.id;sessttl.5:7dfd03c5eb868991@gb.vsproxy.org:{PORT}'
cred, host = PX.split('@'); user = cred.split('://')[1].split(':')[0]; pwd = cred.split(':')[-1]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

PUZZLE_SEL = "aside[aria-modal=true] canvas.EkGpDI"
PIECE_SEL  = "aside[aria-modal=true] canvas._0N0-Dn"
GRIP_SEL   = "aside[aria-modal=true] div.dExCsf"


def canvas_b64(page, sel):
    return page.evaluate("""(sel) => { const c=document.querySelector(sel);
        return c ? c.toDataURL('image/png').split(',')[1] : null; }""", sel)


def state(p):
    return p.evaluate("""() => { const b=document.body.innerText||'';
        if(/Simak Ketentuan Akun/i.test(b)) return 'TOS';
        if(/kode verifikasi|Kirim Kode/i.test(b)) return 'OTP';
        if(/telah terjadi kesalahan|Terjadi kesalahan|Coba lagi/i.test(b)) return 'ERROR';
        if(/Geser untuk/i.test(b)) return 'CAPTCHA';
        return '?'; }""")


def solve_cycle(p, api_key, tag=""):
    """satu siklus solve. return (prop, state)."""
    gb = p.locator(GRIP_SEL).first.bounding_box()
    if not gb:
        return None, None
    start_x = gb["x"] + gb["width"] / 2
    start_y = gb["y"] + gb["height"] / 2
    p.mouse.move(start_x, start_y); p.mouse.down()
    for pixel in range(10):
        p.mouse.move(start_x + 10, start_y + math.log(1 + pixel)); time.sleep(0.02)
    time.sleep(0.3)
    pz = canvas_b64(p, PUZZLE_SEL); pc = canvas_b64(p, PIECE_SEL)
    if not pz or not pc:
        p.mouse.up(); return None, None
    open(f"/root/shopee-farm/shots/sad3_puzzle_{PHONE}{tag}.png", "wb").write(base64.b64decode(pz))
    open(f"/root/shopee-farm/shots/sad3_piece_{PHONE}{tag}.png", "wb").write(base64.b64decode(pc))
    url = f"https://www.sadcaptcha.com/api/v1/puzzle?licenseKey={api_key}"
    r = requests.post(url, json={"puzzleImageB64": pz, "pieceImageB64": pc}, timeout=30)
    prop = r.json().get("slideXProportion")
    if prop is None:
        p.mouse.up(); return None, None
    bar_w = p.evaluate("""()=>{const c=document.querySelector('canvas.EkGpDI');
        return c?c.getBoundingClientRect().width:280;}""")
    grip_w = p.evaluate("""()=>{const g=document.querySelector('div.dExCsf');
        return g?g.getBoundingClientRect().width:40;}""")
    travel = bar_w - grip_w
    dist = int(prop * travel)
    print(f"  prop={prop} travel={travel} dist={dist}")
    for pixel in range(10, dist):
        p.mouse.move(start_x + pixel, start_y + math.log(1 + pixel)); time.sleep(0.008)
    ov = random.choice([1, 2, 3])
    p.mouse.move(start_x + dist + ov, start_y + ov, steps=15)
    p.mouse.move(start_x + dist, start_y, steps=10)
    time.sleep(0.2); p.mouse.up(); time.sleep(3.5)
    return prop, state(p)


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=False, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        c = b.new_context(user_agent=UA, locale="id-ID",
                          proxy={"server": "http://" + host, "username": user, "password": pwd},
                          extra_http_headers={"Accept-Language": "id-ID,id;q=0.9,en;q=0.8"},
                          viewport={"width": 1280, "height": 900})
        c.add_cookies([{"name": "shopee_webLanguage", "value": "id", "domain": ".shopee.co.id", "path": "/"}])
        p = c.new_page()
        p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
        try: p.wait_for_load_state("networkidle", timeout=18000)
        except: pass
        time.sleep(3)
        for _ in range(12):
            if not p.evaluate("()=>/Pilih bahasa Anda/i.test(document.body.innerText||'')"): break
            try:
                loc = p.locator("button:has-text('Bahasa Indonesia')").first
                if loc.count() and loc.is_visible(): loc.click(timeout=2000)
            except: pass
            time.sleep(1.5)
        for _ in range(10):
            if p.evaluate("()=>document.querySelectorAll('input').length") > 0: break
            time.sleep(1)
        fill_field(p, 0, PHONE); time.sleep(1)
        click_submit(p); time.sleep(3)
        st = "wait"
        for _i in range(15):
            time.sleep(2); st = state(p)
            if st == "TOS":
                btn = p.evaluate("""()=>{let f=null;document.querySelectorAll('*').forEach(e=>{const t=(e.childElementCount===0?(e.textContent||''):'').trim();if(!f&&/^setuju$/i.test(t)){const r=e.getBoundingClientRect();f={x:r.x+r.width/2,y:r.y+r.height/2};}});return f;}""")
                if btn: p.mouse.click(btn["x"], btn["y"])
            if st in ("CAPTCHA", "ERROR"): break
        print("STATE:", st)
        if st != "CAPTCHA":
            p.screenshot(path=f"/root/shopee-farm/shots/sad3_{PHONE}_{_re.sub(r'[^A-Za-z0-9]','_',st)}.png")
            b.close(); return
        time.sleep(3)
        st2 = None
        for att in range(5):
            prop, st2 = solve_cycle(p, API_KEY, tag=f"_a{att}")
            print(f"  attempt {att+1}: prop={prop} -> {st2}")
            if st2 in ("OTP", "ERROR") or prop is None:
                break
            time.sleep(2)
        safe = _re.sub(r'[^A-Za-z0-9]', '_', str(st2))
        p.screenshot(path=f"/root/shopee-farm/shots/sad3_{PHONE}_{safe}.png")
        print("FINAL:", st2)
        b.close()


main()
