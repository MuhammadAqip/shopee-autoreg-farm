"""Shopee IMAGE CRAWL solver — SadCaptcha /shopee-image-crawl.

Insight: Shopee signup captcha = "image crawl" (arced trajectory). Piece bergerak
melengkung. API butuh: puzzle b64, piece b64, DAN trajectory (sweep).

Alur (pola playwrightsolver.py::solve_image_crawl):
  1. grip center -> mouse.down()
  2. SWEEP: drag grip sepanjang bar (step 3px, diagonal -pixel), 
     tiap step catat {pixels_from_slider_origin, piece_center (ratio)} 
  3. Kirim ke /shopee-image-crawl -> pixelsFromSliderOrigin (target)
  4. drag horizontal sejauh target, overshoot+back, up
"""
import sys, time, json, base64, math, random, re as _re
sys.path.insert(0, '/root/shopee-farm')
import requests
from playwright.sync_api import sync_playwright
from tools.signup_driver import fill_field, click_submit

PHONE  = sys.argv[1] if len(sys.argv) > 1 else "87876125616"
PORT   = sys.argv[2] if len(sys.argv) > 2 else "10002"
API_KEY = sys.argv[3] if len(sys.argv) > 3 else "f231e3e4ea6ae4a5806fcfbc68513bfd"
PX = f'http://8108c95881d0c4b2f18e__cr.id;sessttl.5:7dfd03c5eb868991@gb.vsproxy.org:{PORT}'
cred, host = PX.split('@'); user = cred.split('://')[1].split(':')[0]; pwd = cred.split(':')[-1]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

PUZZLE_SEL = "aside[aria-modal=true] canvas.EkGpDI"
PIECE_SEL  = "aside[aria-modal=true] canvas._0N0-Dn"
GRIP_SEL   = "aside[aria-modal=true] div.dExCsf"
PIECE_WRAP = "aside[aria-modal=true] div._7Sd2jx"


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


def box(p, sel):
    b = p.locator(sel).first.bounding_box()
    return b


def solve_image_crawl(p, api_key):
    gb = box(p, GRIP_SEL)
    if not gb:
        return None, None
    start_x = gb["x"] + gb["width"] / 2
    start_y = gb["y"] + gb["height"] / 2
    p.mouse.move(start_x, start_y)
    p.mouse.down()

    pz = canvas_b64(p, PUZZLE_SEL)
    pc = canvas_b64(p, PIECE_SEL)
    open(f"/root/shopee-farm/shots/crawl_puzzle_{PHONE}.png", "wb").write(base64.b64decode(pz))
    open(f"/root/shopee-farm/shots/crawl_piece_{PHONE}.png", "wb").write(base64.b64decode(pc))

    pz_box = box(p, PUZZLE_SEL)
    bar_w = pz_box["width"] if pz_box else 280

    # --- SWEEP trajectory ---
    trajectory = []
    step = 3
    for px in range(0, int(bar_w), step):
        p.mouse.move(start_x + px, start_y - px)   # diagonal (pola SadCaptcha)
        time.sleep(0.01)
        pw = box(p, PIECE_WRAP)
        if not pw:
            continue
        cx = pw["x"] + pw["width"] / 2
        cy = pw["y"] + pw["height"] / 2
        trajectory.append({
            "pixelsFromSliderOrigin": px,
            "pieceCenter": {
                "proportionX": (cx - pz_box["x"]) / pz_box["width"],
                "proportionY": (cy - pz_box["y"]) / pz_box["height"],
            },
            "pieceRotationAngle": 0,
        })
    print(f"  trajectory len: {len(trajectory)}")

    url = f"https://www.sadcaptcha.com/api/v1/shopee-image-crawl?licenseKey={api_key}"
    payload = {
        "puzzle_image_b64": pz,
        "piece_image_b64": pc,
        "slide_piece_trajectory": trajectory,
    }
    r = requests.post(url, json=payload, timeout=40)
    print("  crawl API:", r.status_code, r.text[:150])
    if r.status_code != 200:
        p.mouse.up(); return None, "ERROR"
    target = r.json().get("pixelsFromSliderOrigin")
    print(f"  target px: {target}")

    if target is None:
        p.mouse.up(); return None, None
    # drag dari posisi sekarang (di bar_w) KEMBALI ke target
    # PENTING: kita sudah di ujung setelah sweep. SadCaptcha asumsikan sweep lalu drag dari origin.
    # Reset: lepas di target? — Kita gerakkan ke start+target relatif origin.
    # Karena kita sudah sweep, gunakan perilaku: tarik ke kiri dulu ke 0 lalu ke target.
    p.mouse.move(start_x, start_y, steps=30)     # kembali ke origin
    time.sleep(0.1)
    for i in range(1, int(target)):
        p.mouse.move(start_x + i, start_y); time.sleep(0.006)
    ov = random.choice([1, 2, 3])
    p.mouse.move(start_x + target + ov, start_y + ov, steps=15)
    p.mouse.move(start_x + target, start_y, steps=10)
    time.sleep(0.2)
    p.mouse.up()
    time.sleep(3.5)
    return target, state(p)


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
            p.screenshot(path=f"/root/shopee-farm/shots/crawl_{PHONE}_{_re.sub(r'[^A-Za-z0-9]','_',st)}.png")
            b.close(); return
        time.sleep(3)
        st2 = None
        for att in range(4):
            target, st2 = solve_image_crawl(p, API_KEY)
            print(f"  attempt {att+1}: target={target} -> {st2}")
            if st2 in ("OTP", "ERROR") or target is None:
                break
            time.sleep(2)
        safe = _re.sub(r'[^A-Za-z0-9]', '_', str(st2))
        p.screenshot(path=f"/root/shopee-farm/shots/crawl_{PHONE}_{safe}.png")
        print("FINAL:", st2)
        b.close()


main()
