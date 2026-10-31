#!/usr/bin/env python3
"""Shopee CAPTCHA SOLVER v6 — 3 tipe (puzzle / image-drag / image-crawl).

Replika PERSIS ekstensi resmi SadCaptcha (github.com/gbiz123/shopee-captcha-solver-chrome-extension).
Baca skill 'shopee-captcha-solver' utk dokumentasi lengkap.

Perbedaan krusial vs attempt lama:
  - Pakai page.mouse (CDP trusted) — BUKAN dispatch PointerEvent sintetik.
  - Identifikasi TIPE captcha dulu (selectors), baru pilih mekanik.
  - IMAGE_DRAG: drag ELEMEN PIECE (img) ke koordinat prop*bbox, lalu KLIK VERIFY.
  - PUZZLE: slide_bar_width = lebar IMAGE puzzle (bukan track-grip).

Usage:
  xvfb-run -a python shopee_v6.py <PHONE> <API_KEY> <PROXY_URL> [wa|sms]
"""
import sys, os, time, json, base64, math, random, re
import requests
from playwright.sync_api import sync_playwright

ROOT = "/root/shopee-farm"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
API = "https://www.sadcaptcha.com/api/v1"

# ---- selectors (dari chrome-ext resmi) ----
IC_PUZZLE = "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false]"
IC_PIECE  = "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true], #puzzleContainer > #puzzleImgComponent"
IC_BUTTON = "div:has(> svg + svg)"
IC_RESET  = "#NEW_CAPTCHA svg[viewBox='0 0 16 16'], aside svg[viewBox='0 0 16 16']"

PZ_BUTTON = 'aside[aria-modal=true] div[style="width: 40px; height: 40px; transform: translateX(0px);"]'
PZ_PUZZLE = "aside[aria-modal=true] div[aria-hidden=true] > div > div > img[draggable=false]"
PZ_PIECE  = "aside[aria-modal=true] div[aria-hidden=true] > div > div > img[draggable=true]"

ID_VERIFY = ".rb6XLo, #NEW_CAPTCHA button:not(:has(*)), aside button:not(:has(*))"
ID_PUZZLE = "#NEW_CAPTCHA canvas, aside canvas"
ID_PIECE  = "#NEW_CAPTCHA img, aside img"

JS_PRESENT = """(sels)=>{for(const s of sels){try{if(document.querySelector(s))return s;}catch(e){}}return null;}"""
JS_STATE = """()=>{const b=document.body.innerText||'';
  if(/Masukkan Kode OTP|Kode OTP telah dikirim|kirim ulang/i.test(b))return 'OTP';
  if(/kirim kode otp via|Kirim ke WhatsApp/i.test(b))return 'OTP_MODAL';
  if(/kode verifikasi|Kirim Kode/i.test(b))return 'OTP';
  if(/Simak Ketentuan Akun/i.test(b))return 'TOS';
  if(/Buat password|Penuhi persyaratan sandi|cocokkan kata sandi/i.test(b))return 'PASSWORD';
  if(/telah terjadi kesalahan|Terjadi kesalahan|Coba Lagi/i.test(b))return 'ERROR';
  if(/Geser untuk|Verifikasi untuk|Memuat/i.test(b))return 'CAPTCHA';
  return '?';}"""


def state(p): return p.evaluate(JS_STATE)


def dataurl(p, sel):
    """elementToDataUrl: canvas.toDataURL() atau img.src -> base64 murni."""
    return p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;
      if(e.tagName==='CANVAS')return e.toDataURL('image/png').split(',')[1];
      if(e.tagName==='IMG'){const u=e.src||'';return u.includes(',')?u.split(',')[1]:null;}return null;}""", sel)


def rect(p, sel):
    return p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();
      return {x:r.x,y:r.y,w:r.width,h:r.height};}""", sel)


def api_post(path, body, key):
    try:
        r = requests.post(f"{API}{path}?licenseKey={key}", json=body, timeout=40)
        if r.status_code != 200:
            return None, f"{r.status_code}:{r.text[:100]}"
        return r.json(), None
    except Exception as e:
        return None, str(e)[:100]


def bezier(start, end, steps):
    c1 = {"x": start[0] + (end[0]-start[0])*(0.2+random.random()*0.2),
          "y": start[1] + (random.random()*15-5)}
    c2 = {"x": start[0] + (end[0]-start[0])*(0.6+random.random()*0.2),
          "y": end[1] + (random.random()*10-5)}
    out = []
    for i in range(steps+1):
        t = i/steps
        x = (1-t)**3*start[0] + 3*(1-t)**2*t*c1["x"] + 3*(1-t)*t**2*c2["x"] + t**3*end[0]
        y = (1-t)**3*start[1] + 3*(1-t)**2*t*c1["y"] + 3*(1-t)*t**2*c2["y"] + t**3*end[1]
        out.append((x, y))
    return out


def approach(p, x, y):
    sx = x - 80 - random.random()*40
    sy = y + 40 + random.random()*30
    for (px, py) in bezier((sx, sy), (x, y), 8+int(random.random()*4)):
        p.mouse.move(px, py); time.sleep(0.015+random.random()*0.025)


# ---------- PUZZLE ----------
def solve_puzzle_slide(p, key):
    # cari elemen puzzle & piece (canvas ATAU img) + button/grip
    def first_present(sels):
        for s in sels:
            r = rect(p, s)
            if r and r["w"] > 5: return s, r
        return None, None
    pz_sel, pzr = first_present([PZ_PUZZLE, IC_PUZZLE])
    pc_sel, pcr = first_present([PZ_PIECE, IC_PIECE])
    btn_sel, gb = first_present([PZ_BUTTON, IC_BUTTON])
    if not pzr or not pcr:
        return {"err": "no puzzle elems"}
    # tunggu gambar puzzle STABIL (2x hash sama) sebelum extract
    prev = None
    for _ in range(15):
        cur = dataurl(p, pz_sel)
        if cur and cur == prev:
            break
        prev = cur
        time.sleep(0.6)
    # cari grip/slider button: elemen 40x40 di bawah puzzle, atau IC_BUTTON
    if not gb:
        gb = p.evaluate("""()=>{let f=null;document.querySelectorAll('div,button,span').forEach(e=>{
          const r=e.getBoundingClientRect();if(r.width>=28&&r.width<=56&&r.height>=28&&r.height<=56&&r.top>200){
          if(!f||r.top<f.y)f={x:r.x+r.width/2,y:r.y+r.height/2,w:r.width};}});return f;}""")
    if not gb: return {"err": "no grip"}
    sx, sy = gb["x"], gb["y"]
    p.mouse.move(sx, sy); time.sleep(0.1); p.mouse.down()
    for i in range(10):
        p.mouse.move(sx+10, sy+math.log(1+i)); time.sleep(0.02)
    pz = dataurl(p, pz_sel); pc = dataurl(p, pc_sel)
    if not pz or not pc:
        p.mouse.up(); return {"err": "no b64"}
    j, err = api_post("/puzzle", {"puzzleImageB64": pz, "pieceImageB64": pc}, key)
    if not j: p.mouse.up(); return {"err": err}
    prop = j.get("slideXProportion")
    if prop is None: p.mouse.up(); return {"err": "no prop", "raw": j}
    bar_w = pzr["w"]                                   # lebar IMAGE puzzle
    dist = int(prop * bar_w)
    moved = 0
    for px in range(10, dist):
        _x = sx + px; _y = sy + math.log(1+px)
        p.mouse.move(_x, _y); time.sleep(0.012)
        moved = px
    time.sleep(0.134)
    p.mouse.move(sx+dist, sy); time.sleep(0.134)
    p.mouse.up()
    return {"type": "puzzle", "prop": round(prop, 4), "dist": dist, "bar_w": round(bar_w)}

# ---------- IMAGE_DRAG ----------
def solve_image_drag(p, key):
    pr = rect(p, ID_PIECE)
    pz_rect = rect(p, ID_PUZZLE)
    if not pr or not pz_rect: return None
    pz = dataurl(p, ID_PUZZLE); pc = dataurl(p, ID_PIECE)
    if not pz or not pc: return {"err": "no img"}
    j, err = api_post("/shopee-image-drag", {"puzzleImageB64": pz, "pieceImageB64": pc}, key)
    if not j: return {"err": err}
    pts = j.get("proportionalPoints") or []
    if not pts: return {"err": "no points", "raw": j}
    ax = pz_rect["x"] + pts[0]["proportionX"] * pz_rect["w"]
    ay = pz_rect["y"] + pts[0]["proportionY"] * pz_rect["h"]
    sx, sy = pr["x"]+pr["w"]/2, pr["y"]+pr["h"]/2
    approach(p, sx, sy)
    time.sleep(0.15+random.random()*0.2)
    p.mouse.move(sx, sy); p.mouse.down()
    for (px, py) in bezier((sx, sy), (ax, ay), 20):
        p.mouse.move(px, py); time.sleep(0.010+random.random()*0.02)
    time.sleep(0.15+random.random()*0.2)
    p.mouse.up()
    time.sleep(0.2)
    # klik VERIFY
    vb = p.evaluate("""()=>{let f=null;document.querySelectorAll('button,div,span,a').forEach(e=>{
        const t=(e.childElementCount===0?(e.textContent||''):'').trim();
        if(!f&&/^(verify|verifikasi|lanjut|submit)$/i.test(t)){const r=e.getBoundingClientRect();
        if(r.width>0&&r.height>0)f={x:r.x+r.width/2,y:r.y+r.height/2};}});return f;}""")
    if not vb:
        try:
            el = p.locator(ID_VERIFY).first
            if el.count():
                bb = el.bounding_box()
                if bb: vb = {"x": bb["x"]+bb["width"]/2, "y": bb["y"]+bb["height"]/2}
        except Exception: pass
    if vb:
        p.mouse.move(vb["x"], vb["y"]); time.sleep(0.05)
        p.mouse.down(); time.sleep(0.05); p.mouse.up()
    return {"type": "image_drag", "points": len(pts), "answer": [round(ax), round(ay)]}


# ---------- IMAGE_CRAWL ----------
def solve_image_crawl(p, key, dry=False):
    pz_sel = IC_PUZZLE
    btn = rect(p, IC_BUTTON)
    if not btn:
        # fallback: reset icon svg viewBox 16x16, ATAU elemen 28-56px persegi di bawah puzzle
        btn = p.evaluate("""()=>{let f=null;
          document.querySelectorAll('div,button,span').forEach(e=>{
          const r=e.getBoundingClientRect();
          if(r.width>=28&&r.width<=56&&r.height>=28&&r.height<=56&&r.top>480){
          if(!f||r.top<f.y)f={x:r.x,y:r.y,w:r.width,h:r.height};}});return f;}""")
        print("  [crawl] IC_BUTTON fallback:", btn)
    if not btn: return None
    pz = dataurl(p, pz_sel)
    pc = dataurl(p, IC_PIECE)
    if not pz or not pc: return {"err": "no img"}
    # pre-analyze
    pre, err = api_post("/shopee-image-crawl-pre-analyze", {"image_b64": pz}, key)
    maxprop = None
    if pre:
        if pre.get("skipRecommended"):
            # skip = captcha refresh; tapi untuk bot, coba lanjut terus (jangan berhenti).
            print("    [crawl] pre-analyze skipRecommended → lanjut anyway")
            maxprop = pre.get("slideXProportion")
        else:
            maxprop = pre.get("slideXProportion")
    elif err and "401" in str(err):
        return {"err": "CREDITS_EMPTY", "detail": err}
    sx, sy = btn["x"]+btn["w"]/2, btn["y"]+btn["h"]/2
    pz_rect = rect(p, pz_sel)
    approach(p, sx, sy)
    p.mouse.move(sx, sy); p.mouse.down()
    time.sleep(0.15)
    traj = []
    bar_w = pz_rect["w"]
    limit = bar_w*0.85
    for px in range(0, int(limit), 3):
        p.mouse.move(sx+px, sy-px)      # diagonal!
        time.sleep(0.02)
        # rekam trajectory element
        pr = p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;
          const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,style:e.getAttribute('style')||''};}""", IC_PIECE)
        if not pr: continue
        pcx = pr["x"]+pr["w"]/2; pcy = pr["y"]+pr["h"]/2
        pxp = round((pcx-pz_rect["x"])/pz_rect["w"], 4)
        pyp = round((pcy-pz_rect["y"])/pz_rect["h"], 4)
        a = 0.0
        mm = re.search(r"rotate\(([-0-9.]+)deg", pr["style"])
        if mm: a = float(mm.group(1))
        traj.append({"pixels_from_slider_origin": px, "piece_rotation_angle": a,
                     "piece_center": {"proportionX": pxp, "proportionY": pyp}})
    traj.sort(key=lambda x: x["pixels_from_slider_origin"])
    if len(traj) < 12:
        p.mouse.up(); return {"err": "traj too short", "n": len(traj)}
    if dry:
        p.mouse.up()
        return {"type": "image_crawl_DRYRUN", "traj": len(traj), "puzzle_w": pz_rect["w"]}
    sol, err = api_post("/shopee-image-crawl",
                        {"puzzle_image_b64": pz, "piece_image_b64": pc,
                         "slide_piece_trajectory": traj}, key)
    if not sol:
        p.mouse.up(); return {"err": err}
    target = sol.get("pixelsFromSliderOrigin")
    # balik ke origin lalu drag ke target
    p.mouse.move(sx, sy); time.sleep(0.1)
    for i in range(0, int(target), 8):
        p.mouse.move(sx+i, sy); time.sleep(0.008)
    ov = random.choice([1, 2, 3])
    p.mouse.move(sx+target+ov, sy+ov); p.mouse.move(sx+target, sy)
    time.sleep(0.2); p.mouse.up()
    return {"type": "image_crawl", "target": target, "traj": len(traj)}


def fill_otp(p, code):
    """Isi 6 kotak OTP. Shopee pakai input terpisah ATAU satu input tersembunyi."""
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) != 6: return {"err": "otp not 6 digit"}
    # coba 1: satu input (ketik langsung)
    single = p.evaluate("""()=>{const ins=[...document.querySelectorAll('input')].filter(i=>{
        const r=i.getBoundingClientRect();return r.width>0&&r.height>0&&(i.maxLength===6||i.inputMode==='numeric'||i.type==='tel'||i.type==='text');});
        return ins.length;}""")
    # coba ketik via keyboard ke field pertama
    boxes = p.evaluate("""()=>{const out=[];document.querySelectorAll('input').forEach(i=>{
        const r=i.getBoundingClientRect();if(r.width>0&&r.height>0&&r.width<70)out.push({x:r.x+r.width/2,y:r.y+r.height/2});});
        return out.slice(0,6);}""")
    if len(boxes) >= 6:
        for i, ch in enumerate(code):
            p.mouse.click(boxes[i]["x"], boxes[i]["y"]); time.sleep(0.12+random.random()*0.1)
            p.keyboard.type(ch, delay=60+int(random.random()*50))
        return {"ok": True, "mode": "6boxes", "n": len(boxes)}
    # fallback: satu input, ketik semua
    for i in range(single or 1):
        try:
            p.keyboard.type(code, delay=70)
            return {"ok": True, "mode": "single_type"}
        except Exception:
            pass
    return {"err": "no otp field"}


def click_lanjut(p):
    tgt = p.evaluate("""()=>{let f=null;document.querySelectorAll('button,div,span,a').forEach(e=>{
        const t=(e.childElementCount===0?(e.textContent||''):'').trim();
        if(!f&&/^(lanjut|verifikasi|confirm|kirim|next)$/i.test(t)){const r=e.getBoundingClientRect();
        if(r.width>0&&r.height>0)f={x:r.x+r.width/2,y:r.y+r.height/2,t};}});return f;}""")
    if tgt:
        p.mouse.move(tgt["x"], tgt["y"]); time.sleep(0.15)
        p.mouse.down(); time.sleep(0.08); p.mouse.up()
    return tgt


def fill_password(p, pw):
    """Step 2: isi password + konfirmasi."""
    fields = p.evaluate("""()=>{const out=[];document.querySelectorAll('input[type=password],input').forEach(i=>{
        const r=i.getBoundingClientRect();if(r.width>0&&r.height>0&&r.width>120)out.push({x:r.x+r.width/2,y:r.y+r.height/2,type:i.type||''});});
        return out;}""")
    if not fields: return {"err": "no pw field"}
    # isi field pertama (password baru), kalau ada 2 -> isi dua (konfirmasi)
    n = min(2, len(fields))
    for i in range(n):
        p.mouse.click(fields[i]["x"], fields[i]["y"]); time.sleep(0.15+random.random()*0.1)
        p.keyboard.type(pw, delay=70+int(random.random()*60))
    return {"ok": True, "n": n}


def main():
    # usage: shopee_v6.py <PHONE> <KEY> <PROXY> [wa|sms] [--dry] [--otp=NNNNNN] [--pw=PASSWORD]
    argv = [a for a in sys.argv if not a.startswith("--")]
    phone = (argv[1] if len(argv) > 1 else "").lstrip("+0")
    if phone.startswith("62"): phone = phone[2:]
    key = argv[2] if len(argv) > 2 else os.environ.get("SADCAPTCHA_KEY", "")
    proxy = argv[3] if len(argv) > 3 else ""
    channel = "wa"
    dry_run = "--dry" in sys.argv
    otp_code = ""
    password = ""
    for a in sys.argv:
        if a.startswith("--otp="): otp_code = a.split("=", 1)[1].strip()
        elif a.startswith("--pw="): password = a.split("=", 1)[1]
    for a in argv[1:]:
        if a.lower() in ("wa", "sms"): channel = a.lower()
    # parse proxy http://user:pass@host:port
    pm = re.match(r"http://([^:]+):([^@]+)@([^:]+):(\d+)", proxy)
    if not pm:
        print("RESULT:", json.dumps({"stage": "bad_proxy"})); return
    pxy = {"server": f"http://{pm.group(3)}:{pm.group(4)}",
           "username": pm.group(1), "password": pm.group(2)}
    print(f"PHONE={phone} CHANNEL={channel} PROXY={pm.group(3)}:{pm.group(4)}")

    res = {"phone": phone, "stage": "init", "ok": False}
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=False,
                               args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        c = b.new_context(user_agent=UA, locale="id-ID", proxy=pxy,
                          extra_http_headers={"Accept-Language": "id-ID,id;q=0.9,en;q=0.8"},
                          viewport={"width": 1280, "height": 900})
        c.add_cookies([{"name": "shopee_webLanguage", "value": "id",
                        "domain": ".shopee.co.id", "path": "/"}])
        p = c.new_page()
        # ---- RSA HOOK (nangkep plaintext SEBELUM di-encrypt) ----
        RSA_HOOK = r"""
        (() => {
          window.__RSA_LOG = [];
          const _enc = window.TextEncoder ? new TextEncoder() : null;
          // hook WebCrypto encrypt
          if (window.crypto && window.crypto.subtle) {
            const oe = window.crypto.subtle.encrypt.bind(window.crypto.subtle);
            window.crypto.subtle.encrypt = function(algo, key, data) {
              try {
                const arr = data instanceof ArrayBuffer ? new Uint8Array(data)
                          : (ArrayBuffer.isView(data) ? new Uint8Array(data.buffer) : null);
                if (arr) {
                  let s = '';
                  for (let i=0;i<Math.min(arr.length,1200);i++) s += String.fromCharCode(arr[i]);
                  window.__RSA_LOG.push({src:'subtle', algo: JSON.stringify(algo).slice(0,120), plain: s});
                }
              } catch(e){}
              return oe(algo, key, data);
            };
          }
          // hook btoa (base64 output) — korelasi dgn payload encrypted_data
          const _btoa = window.btoa;
          window.btoa = function(s){
            try {
              if (typeof s === 'string' && s.length > 20 && s.length < 3000)
                window.__RSA_LOG.push({src:'btoa', plain: s.slice(0,800), out: _btoa(s).slice(0,60)});
            } catch(e){}
            return _btoa(s);
          };
          return true;
        })();
        """
        p.add_init_script(RSA_HOOK)
        # ---- FULL NETWORK CAPTURE (semua endpoint, buat replikasi pure-API) ----
        CAPT = {"phone": phone, "started": time.time(), "requests": [], "rsa_log": []}
        CAPT_DIR = f"{ROOT}/captures"
        os.makedirs(CAPT_DIR, exist_ok=True)

        def _on_request(req):
            if "/api/" not in req.url and "captcha" not in req.url.lower():
                return
            entry = {"t": round(time.time() - CAPT["started"], 2), "method": req.method,
                     "url": req.url, "post": (req.post_data or "")[:4000]}
            CAPT["requests"].append(entry)

        def _on_response(resp):
            try:
                ru = resp.url
                if "/api/" not in ru and "captcha" not in ru.lower():
                    return
                body = ""
                ct = resp.headers.get("content-type", "")
                if "json" in ct or "text" in ct:
                    try: body = resp.text()[:6000]
                    except Exception: body = "<unreadable>"
                # cari entry terakhir dgn url sama yg belum ada body
                for e in reversed(CAPT["requests"]):
                    if e["url"] == ru and "status" not in e:
                        e["status"] = resp.status
                        e["req_headers"] = dict(resp.request.headers)
                        e["body"] = body
                        break
            except Exception:
                pass

        p.on("request", _on_request)
        p.on("response", _on_response)
        try:
            p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
            time.sleep(3)
            # tunggu modal bahasa MUNCUL lalu dismiss (loop sampai bener-bener hilang)
            for _ in range(40):
                txt = p.evaluate("()=>document.body.innerText||''")
                if "Pilih bahasa" not in txt and "Choose your language" not in txt:
                    # sudah gak ada modal; pastikan input juga ada
                    if p.evaluate("()=>document.querySelectorAll('input').length") > 0:
                        break
                else:
                    clicked = False
                    for sel in ["button:has-text('Bahasa Indonesia')",
                                "text=Bahasa Indonesia",
                                "div:has-text('Bahasa Indonesia')"]:
                        try:
                            loc = p.locator(sel).first
                            if loc.count() and loc.is_visible():
                                loc.click(timeout=2000, force=True); clicked = True; break
                        except Exception:
                            continue
                    if not clicked:
                        try: p.keyboard.press("Escape"); p.mouse.click(8, 8)
                        except Exception: pass
                time.sleep(1.2)
            time.sleep(1)
            from tools.signup_driver import fill_field, click_submit
            fill_field(p, 0, phone); time.sleep(1.5)
            # trusted click (CDP) di koordinat tombol — bukan synthetic event
            sname = None
            for sel in ["button:has-text('BERIKUTNYA')", "text=BERIKUTNYA",
                        "button:has-text('Berikutnya')", "button:has-text('Daftar')",
                        "div:has-text('BERIKUTNYA')"]:
                try:
                    loc = p.locator(sel).first
                    if loc.count():
                        bb = loc.bounding_box()
                        if bb and bb["width"] > 2:
                            cx, cy = bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2
                            p.mouse.move(cx, cy); time.sleep(0.12+random.random()*0.15)
                            p.mouse.down(); time.sleep(0.08); p.mouse.up()
                            sname = f"trusted:{sel}@{int(cx)},{int(cy)}"; break
                except Exception: continue
            if not sname:
                sname = click_submit(p)
            print("SUBMIT:", sname)
            time.sleep(1.8)
            st = "wait"
            for _ in range(45):
                time.sleep(2)
                st = state(p)
                if st == "TOS":
                    btn = p.evaluate("""()=>{let f=null;document.querySelectorAll('button,div,span,a').forEach(e=>{
                      const t=(e.childElementCount===0?(e.textContent||''):'').trim();
                      if(!f&&/^setuju$/i.test(t)){const r=e.getBoundingClientRect();if(r.width>0)f={x:r.x+r.width/2,y:r.y+r.height/2};}});return f;}""")
                    if btn:
                        p.mouse.move(btn["x"], btn["y"]); time.sleep(0.15)
                        p.mouse.down(); time.sleep(0.08); p.mouse.up()
                        print("  TOS setuju clicked", btn)
                if st in ("CAPTCHA", "OTP", "ERROR", "OTP_MODAL"): break
            print("STATE:", st)
            if st == "CAPTCHA":
                # tunggu Memuat hilang
                for _w in range(20):
                    if not p.evaluate("()=>/Memuat/i.test(document.body.innerText||'')"): break
                    time.sleep(1)
                time.sleep(2)
                locked_type = None
                for attempt in range(8):
                    # deteksi tipe dari SELECTOR dulu (urutan skill: IC_PIECE → PZ_PIECE → ID_PUZZLE).
                    # Shopee ID: instruksi bertuliskan "Geser ... puzzle" TAPI piece canvas
                    # 44x44 draggable=true = IMAGE_CRAWL. Lock dari teks = salah endpoint = drag gagal.
                    itxt = p.evaluate("()=>(document.body.innerText||'')")
                    if locked_type is None:
                        if p.evaluate(JS_PRESENT, [IC_PIECE]):
                            locked_type = "image_crawl"
                        elif p.evaluate(JS_PRESENT, [PZ_PIECE]):
                            locked_type = "puzzle"
                        elif p.evaluate(JS_PRESENT, [ID_PUZZLE, ID_VERIFY]):
                            locked_type = "image_drag"
                        else:
                            locked_type = "puzzle"   # fallback terakhir
                    typ = locked_type
                    print(f"  attempt {attempt+1}: type={typ}{' [DRY]' if dry_run else ''}")
                    if typ == "puzzle": info = solve_puzzle_slide(p, key)
                    elif typ == "image_drag": info = solve_image_drag(p, key)
                    elif typ == "image_crawl": info = solve_image_crawl(p, key, dry=dry_run)
                    else: info = {"err": "no captcha type"}
                    print(f"    -> {info}")
                    time.sleep(3)
                    st2 = state(p)
                    if st2 in ("OTP", "OTP_MODAL"): st = st2; break
                    if st2 != "CAPTCHA": st = st2; break
            res["stage"] = st.lower() if st else "?"
            if st in ("OTP", "OTP_MODAL"):
                res["ok"] = True
                # klik kirim OTP
                if channel == "sms":
                    for pat in [r"^metode lain$", r"^sms$|via sms"]:
                        bt = p.evaluate("""(pat)=>{let f=null;const re=new RegExp(pat,'i');
                          document.querySelectorAll('button,div,span,a,label').forEach(e=>{
                          const t=(e.childElementCount===0?(e.textContent||''):'').trim();
                          if(!f&&re.test(t)){const r=e.getBoundingClientRect();if(r.width>0)f={x:r.x+r.width/2,y:r.y+r.height/2};}});return f;}""", pat)
                        if bt: p.mouse.click(bt["x"], bt["y"]); time.sleep(2)
                kb = p.evaluate("""()=>{let f=null;
                  document.querySelectorAll('button,div,span,a').forEach(e=>{
                  const t=(e.childElementCount===0?(e.textContent||''):'').trim();
                  if(!f&&/^kirim ke whatsapp$|^kirim kode$|^kirim otp$|^kirim$/i.test(t)){const r=e.getBoundingClientRect();
                  if(r.width>0)f={x:r.x+r.width/2,y:r.y+r.height/2};}});return f;}""")
                if kb: p.mouse.click(kb["x"], kb["y"]); print("  clicked kirim"); time.sleep(5)
            # ---- STEP: isi OTP kalau disediakan ----
            if otp_code and st in ("OTP", "OTP_MODAL"):
                time.sleep(2)
                r_otp = fill_otp(p, otp_code)
                print("  FILL OTP:", r_otp)
                time.sleep(0.8)
                lj = click_lanjut(p)
                print("  click LANJUT:", lj)
                time.sleep(5)
                st = state(p)
                print("STATE after OTP:", st)
                # ---- STEP: isi password kalau disediakan ----
                if password and st in ("PASSWORD", "?", "OTP"):
                    time.sleep(2)
                    r_pw = fill_password(p, password)
                    print("  FILL PW:", r_pw)
                    time.sleep(0.8)
                    sub = click_lanjut(p)
                    print("  click DAFTAR:", sub)
                    time.sleep(6)
                    st = state(p)
                    print("STATE after PW:", st)
                res["stage"] = st.lower() if st else "?"
                res["ok"] = st not in ("PASSWORD", "OTP", "OTP_MODAL", "ERROR", "?")
                p.screenshot(path=f"{ROOT}/shots/v6_{phone}_final_{st}.png")
            p.screenshot(path=f"{ROOT}/shots/v6_{phone}_{str(res['stage']).replace('?','_')}.png")
        except Exception as e:
            res["note"] = f"{e.__class__.__name__}: {e}"
        finally:
            try:
                # ambil RSA log dari page (kalau masih hidup)
                try:
                    CAPT["rsa_log"] = p.evaluate("()=>window.__RSA_LOG||[]")
                except Exception:
                    pass
                CAPT["ended"] = time.time()
                capt_path = f"{CAPT_DIR}/session_{phone}_{int(CAPT['started'])}.json"
                with open(capt_path, "w") as cf:
                    json.dump(CAPT, cf, indent=1, ensure_ascii=False)
                print("CAPTURE:", capt_path, "requests:", len(CAPT["requests"]), "rsa_log:", len(CAPT["rsa_log"]))
            except Exception as ce:
                print("capture write fail:", ce)
            b.close()
            print("RESULT:", json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
