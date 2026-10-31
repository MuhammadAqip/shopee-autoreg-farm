#!/usr/bin/env python3
"""Shopee signup — solve captcha, TAHAN sesi, tunggu OTP dari file/stdin.

Alur:
  1. buka signup, isi nomor, submit, solve captcha (SadCaptcha)
  2. begitu OTP modal muncul → TULIS /root/shopee-farm/.otp_request ke stdout + tunggu
  3. poll /root/shopee-farm/.otp_input (lu tulis kode di situ) ATAU stdin
  4. isi OTP → LANJUT → isi password → SUBMIT → akun jadi
  5. tahan browser sampai akun terkonfirmasi / timeout

Usage: shopee_hold.py <PHONE> <KEY> <PROXY> [wa|sms]
"""
import sys, os, time, json, re, base64, math, random
from playwright.sync_api import sync_playwright

ROOT = "/root/shopee-farm"
OTP_IN = f"{ROOT}/.otp_input"
PW_IN = f"{ROOT}/.pw_input"
STATUS = f"{ROOT}/.signup_status"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
API = "https://www.sadcaptcha.com/api/v1"
FP_EXPR = ("()=>{try{return window.__sfp||"
           "(document.cookie.match(/_sapid=([^;]+)/)||[])[1]||'';}catch(e){return '';}}")

IC_PUZZLE = "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false]"
IC_PIECE  = "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true], #puzzleContainer > #puzzleImgComponent"
IC_BUTTON = "div:has(> svg + svg)"
PZ_PUZZLE = "aside[aria-modal=true] div[aria-hidden=true] > div > div > img[draggable=false]"
PZ_PIECE  = "aside[aria-modal=true] div[aria-hidden=true] > div > div > img[draggable=true]"
ID_PUZZLE = "#NEW_CAPTCHA canvas, aside canvas"
ID_VERIFY = ".rb6XLo, #NEW_CAPTCHA button:not(:has(*)), aside button:not(:has(*))"

JS_PRESENT = "(sels)=>{for(const s of sels){try{if(document.querySelector(s))return s;}catch(e){}}return null;}"
JS_STATE = """()=>{const b=document.body.innerText||'';
  if(/Pendaftaran berhasil|Berhasil membuat akun/i.test(b))return 'SUCCESS';
  if(/Masukkan Kode OTP|Kode OTP telah dikirim|kirim ulang|Kode OTP Salah/i.test(b))return 'OTP';
  if(/kirim kode otp via|Kirim ke WhatsApp/i.test(b))return 'OTP_MODAL';
  if(/Simak Ketentuan Akun/i.test(b))return 'TOS';
  if(/Atur Password Kamu|Buat password|Penuhi persyaratan sandi|cocokkan kata sandi/i.test(b))return 'PASSWORD';
  if(/telah terjadi kesalahan|Terjadi kesalahan|Coba Lagi/i.test(b))return 'ERROR';
  if(/Geser untuk|Verifikasi untuk|Memuat/i.test(b))return 'CAPTCHA';
  return '?';}"""


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)
    try: open(STATUS, "w").write(msg)
    except Exception: pass


def write_status(state):
    try: open(STATUS, "w").write(state)
    except Exception: pass


def state(p): return p.evaluate(JS_STATE)


def dataurl(p, sel):
    return p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;
      if(e.tagName==='CANVAS')return e.toDataURL('image/png').split(',')[1];
      if(e.tagName==='IMG'){const u=e.src||'';return u.includes(',')?u.split(',')[1]:null;}return null;}""", sel)


def rect(p, sel):
    return p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();
      return {x:r.x,y:r.y,w:r.width,h:r.height};}""", sel)


def parse_proxy(proxy):
    """Parse proxy string → Playwright proxy dict.

    Dukung:
      http://user:pass@host:port   (auth)
      http://host:port             (no auth)
      socks4://host:port
      socks5://host:port
      host:port                    (asumsi http)
    """
    s = (proxy or "").strip()
    scheme = "http"
    m = re.match(r"(\w+)://(.+)$", s)
    if m:
        scheme, rest = m.group(1).lower(), m.group(2)
    else:
        rest = s
    if scheme.startswith("socks4"):
        srv = "socks4"
    elif scheme.startswith("socks5"):
        srv = "socks5"
    else:
        srv = "http"
    if "@" in rest:
        auth, hostport = rest.rsplit("@", 1)
        user, _, pw = auth.partition(":")
        host, _, port = hostport.partition(":")
        return {"server": f"{srv}://{host}:{port}", "username": user, "password": pw}
    host, _, port = rest.partition(":")
    return {"server": f"{srv}://{host}:{port}"}


def api_post(path, body, key):
    import requests
    try:
        r = requests.post(f"{API}{path}?licenseKey={key}", json=body, timeout=40)
        if r.status_code != 200:
            return None, f"{r.status_code}:{r.text[:120]}"
        return r.json(), None
    except Exception as e:
        return None, str(e)[:120]


_KM = None


def _keymgr():
    """Lazy KeyManager buat failover kredit habis."""
    global _KM
    if _KM is None:
        try:
            import sys as _s
            _s.path.insert(0, ROOT)
            from key_manager import KeyManager
            _KM = KeyManager()
        except Exception:
            _KM = False
    return _KM or None


def api_post_fo(path, body, key):
    """api_post + failover. PENTING: hanya 401/403 (kredit habis) yang failover.
    400 = 'no answer' (gambar/trajectory jelek) → JANGAN failover, biar caller refresh."""
    j, err = api_post(path, body, key)
    if err and ("401" in str(err) or "403" in str(err)):
        km = _keymgr()
        if km:
            km.keys.setdefault(key, {})["credits"] = 0
            for _ in range(3):
                nk = km.next()
                if not nk or nk == key:
                    break
                log(f"[KEY] failover → {nk[:10]}…")
                j, err = api_post(path, body, nk)
                if j or ("401" not in str(err) and "403" not in str(err)):
                    return j, err
    return j, err


def bezier(start, end, steps):
    c1 = {"x": start[0]+(end[0]-start[0])*(0.2+random.random()*0.2), "y": start[1]+(random.random()*15-5)}
    c2 = {"x": start[0]+(end[0]-start[0])*(0.6+random.random()*0.2), "y": end[1]+(random.random()*10-5)}
    out = []
    for i in range(steps+1):
        t = i/steps
        x = (1-t)**3*start[0]+3*(1-t)**2*t*c1["x"]+3*(1-t)*t**2*c2["x"]+t**3*end[0]
        y = (1-t)**3*start[1]+3*(1-t)**2*t*c1["y"]+3*(1-t)*t**2*c2["y"]+t**3*end[1]
        out.append((x, y))
    return out


def approach(p, x, y):
    sx = x-80-random.random()*40; sy = y+40+random.random()*30
    for (px, py) in bezier((sx, sy), (x, y), 8+int(random.random()*4)):
        p.mouse.move(px, py); time.sleep(0.015+random.random()*0.025)


def _captcha_present(p):
    return bool(p.evaluate(JS_PRESENT, [IC_PIECE, PZ_PIECE, ID_PUZZLE]))


def _click_reset(p):
    """Klik tombol refresh/reset captcha (selector persis extension)."""
    r = p.evaluate("""()=>{
      const sels=["#NEW_CAPTCHA svg[viewBox='0 0 16 16']","aside svg[viewBox='0 0 16 16']",
                   "button[class*='refresh']","[class*='reload']","[class*='retry']"];
      for(const s of sels){const e=document.querySelector(s);
        if(e&&e.getBoundingClientRect().width>0){e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));return s;}}
      return null;}""")
    return r


def solve_image_crawl(p, key):
    from captcha_cache import CaptchaCache
    cc = CaptchaCache()
    btn = rect(p, IC_BUTTON)
    if not btn:
        btn = p.evaluate("""()=>{let f=null;document.querySelectorAll('div,button,span').forEach(e=>{
          const r=e.getBoundingClientRect();if(r.width>=28&&r.width<=56&&r.height>=28&&r.height<=56&&r.top>480){
          if(!f||r.top<f.y)f={x:r.x,y:r.y,w:r.width,h:r.height};}});return f;}""")
    if not btn: return {"err": "no btn"}
    pz_sel = IC_PUZZLE
    # [ENH-B1] anti 'no img': tunggu puzzle & piece benar-benar ter-render (max 20s)
    pz = pc = None
    for _wi in range(40):
        pz = dataurl(p, pz_sel); pc = dataurl(p, IC_PIECE)
        if pz and pc and len(pz) > 200 and len(pc) > 200:
            break
        time.sleep(0.5)
    if not pz or not pc:
        return {"err": "no img (after warmup)"}
    if cc.lookup and pz and pc:
        pass  # warm-up selesai

    # ==== [ENH #1] PRE-ANALYZE + SKIP RECOMMENDED (persis extension, max 5x) ====
    for skip_round in range(5):
        pre, perr = api_post_fo("/shopee-image-crawl-pre-analyze", {"image_b64": pz}, key)
        if perr and ("401" in str(perr) or "403" in str(perr)):
            return {"err": "CREDITS_EMPTY"}
        if pre and pre.get("skipRecommended"):
            log(f"SKIP_RECOMMENDED #{skip_round+1}/5 — refresh captcha")
            _click_reset(p)
            changed = False
            for _ in range(50):
                time.sleep(0.1)
                nb = dataurl(p, pz_sel)
                if nb and nb != pz:
                    pz = nb; pc = dataurl(p, IC_PIECE); changed = True; break
            if not changed:
                return {"err": "puzzle unchanged after refresh"}
            time.sleep(0.5)
            continue
        slide_prop = (pre or {}).get("slideXProportion", 0.9)
        break
    else:
        return {"err": "all skipped 5x"}

    # ==== CACHE LOOKUP (skip SadCaptcha kalau puzzle sama) ====
    pz_rect = rect(p, pz_sel)
    bar_w = pz_rect["w"] if pz_rect else 0
    target = None
    force_api = os.environ.get("SH_FORCE_API") == "1"
    if bar_w and not force_api:
        cached = cc.lookup(pz, pc)   # proportional (0..1)
        if cached is not None:
            target = int(round(float(cached) * bar_w))
    if force_api:
        log("FORCE_API — skip cache lookup")

    sx, sy = btn["x"]+btn["w"]/2, btn["y"]+btn["h"]/2
    approach(p, sx, sy)
    p.mouse.move(sx, sy); p.mouse.down(); time.sleep(0.15)
    traj = []; bar_w = pz_rect["w"]; limit = bar_w*0.85
    # [ENH-A] sweep diagonal (sy-px) + guard piece bergerak + early-stop di slide_prop
    have_prop = isinstance(slide_prop, (int, float)) and slide_prop < 0.99
    stop_px = None; stopped = False; not_moved = 0
    for px in range(0, int(limit), 3):
        p.mouse.move(sx+px, sy - px)   # diagonal persis ext resmi
        time.sleep(0.02)
        pr = p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;
          const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,style:e.getAttribute('style')||''};}""", IC_PIECE)
        if not pr: continue
        pcx = pr["x"]+pr["w"]/2; pcy = pr["y"]+pr["h"]/2
        pxp = round((pcx-pz_rect["x"])/pz_rect["w"], 4); pyp = round((pcy-pz_rect["y"])/pz_rect["h"], 4)
        a = 0.0
        mm = re.search(r"rotate\(([-0-9.]+)deg", pr["style"])
        if mm: a = float(mm.group(1))
        traj.append({"pixels_from_slider_origin": px, "piece_rotation_angle": a,
                     "piece_center": {"proportionX": pxp, "proportionY": pyp}})
        # [ENH-A2] guard: piece gak gerak → berhenti (trajectory flat = API 400)
        if len(traj) >= 2:
            if traj[-2]["piece_center"]["proportionX"] == traj[-1]["piece_center"]["proportionX"]:
                not_moved += 1
            else:
                not_moved = 0
            if not_moved >= 12:
                stopped = True; break
        # [ENH-A3] early-stop kalau piece sudah lewat slideXProportion (+overshoot)
        if have_prop and pxp >= slide_prop:
            if stop_px is None:
                stop_px = px
            elif px - stop_px >= 15:
                stopped = True; break
    traj.sort(key=lambda x: x["pixels_from_slider_origin"])
    # [ENH-A4] cek piece benar-benar bergerak; kalau flat → item gagal
    if len(traj) >= 4:
        xs = [t["piece_center"]["proportionX"] for t in traj]
        if max(xs) - min(xs) < 0.02:
            log(f"[ENH-A4] piece TIDAK bergerak (range={max(xs)-min(xs):.3f}) — drag gagal")

    if target is None:
        if len(traj) < 12:
            p.mouse.up(); return {"err": "traj short", "n": len(traj)}
        sol, err = api_post_fo("/shopee-image-crawl",
                            {"puzzle_image_b64": pz, "piece_image_b64": pc, "slide_piece_trajectory": traj}, key)
        if not sol:
            p.mouse.up(); return {"err": err}
        target = sol.get("pixelsFromSliderOrigin")
        # [P2] kurangi kredit key setelah solve sukses
        try:
            _kmm = _keymgr()
            if _kmm: _kmm.mark(key, -1)
        except Exception: pass
        if cc and target is not None:
            # simpan PROPORSIONAL (target/bar_w) supaya tahan beda lebar viewport
            prop = round(float(target) / bar_w, 6) if bar_w else 0
            cc.record(pz, pc, prop)
            log(f"cache SAVE prop={prop} target={target} bar_w={bar_w}")

    # [ENH-A5] GESTURE SWING (replika ext resmi): osilasi 4 pass → leg ke solution → nudge release
    p.mouse.move(sx, sy); time.sleep(0.1)
    maxPx = bar_w * 0.85
    toU = lambda x: x / maxPx * 4 - 2
    toPx = lambda u: (u + 2) / 4 * maxPx
    aimU = toU(target)
    def leg(frm, to, step=13):
        dist = to - frm
        n = max(1, math.ceil(abs(dist) / step))
        for i in range(1, n + 1):
            p.mouse.move(sx + frm + dist * (i / n), sy + random.uniform(-0.8, 0.8)); time.sleep(0.002)
        return to
    loU = toU(12)
    at = 0.0
    for c in range(4):
        a = 1.5 * (1 - c / 4)
        room = (2 - aimU) if (c % 2 == 0) else (aimU - loU)
        a = max(0, min(a, room))
        at = leg(at, toPx(aimU + (a if c % 2 == 0 else -a)))
    at = leg(at, target, 15)
    ov = random.choice([1, 2, 3])
    time.sleep(random.uniform(0.9, 2.1))
    p.mouse.move(sx + target + ov, sy + random.uniform(-1, 1)); p.mouse.move(sx + target, sy)
    time.sleep(random.uniform(0.75, 1.45)); p.mouse.up()
    return {"type": "image_crawl", "target": target, "traj": len(traj),
            "src": ("cache" if (cc and cc.lookup(pz, pc) is not None) else "api"),
            "pz": pz, "pc": pc}


def fill_otp(p, code):
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) != 6: return {"err": "otp not 6"}
    # tunggu 6 kotak OTP muncul
    for _ in range(10):
        boxes = p.evaluate("""()=>{const out=[];document.querySelectorAll('input').forEach(i=>{
            const r=i.getBoundingClientRect();if(r.width>0&&r.height>0&&r.width<70)out.push({x:r.x+r.width/2,y:r.y+r.height/2});});
            return out.slice(0,6);}""")
        if len(boxes) >= 6: break
        time.sleep(0.5)
    if len(boxes) >= 6:
        # klik box pertama, lalu ketik semua digit (Shopee auto-advance)
        p.mouse.click(boxes[0]["x"], boxes[0]["y"]); time.sleep(0.2)
        p.keyboard.type(code, delay=80+int(random.random()*40))
        time.sleep(0.3)
        # verifikasi terisi
        filled = p.evaluate("""()=>{let n=0;document.querySelectorAll('input').forEach(i=>{
            if((i.value||'').length>0)n++;});return n;}""")
        if filled >= 6 or filled == 0:
            return {"ok": True, "mode": "6boxes", "filled": filled}
        # fallback per-box kalau auto-advance gagal
        for i, ch in enumerate(code):
            p.mouse.click(boxes[i]["x"], boxes[i]["y"]); time.sleep(0.1)
            p.keyboard.press(ch)
        return {"ok": True, "mode": "per-box"}
    p.keyboard.type(code, delay=80)
    return {"ok": True, "mode": "single"}


def click_daftar_submit(p):
    """[ENH-B5] Klik tombol submit 'DAFTAR' pada langkah password — tahan terhadap
    tombol yang punya child (span) & navbar 'Daftar'. Prioritas: elemen yg
    teks-nya (uppercase) 'DAFTAR' & berada di area form (y>200) & lebar besar."""
    tgt = p.evaluate("""()=>{
      let f=null;
      document.querySelectorAll('button,div,span,a,input').forEach(e=>{
        const t=(e.innerText||e.textContent||'').trim();
        const r=e.getBoundingClientRect();
        if(r.width<150 || r.height<28 || r.y<200) return;       // area form, tombol gede
        const up=t.toUpperCase();
        // cocokkan 'DAFTAR' / 'SELESAI' / 'CREATE' saja (submit), bukan 'Daftar' navbar
        if(!/^(DAFTAR|SELESAI|BUAT AKUN|CREATE ACCOUNT|SIGN UP|REGISTER)$/.test(up)) return;
        const score = (up==='DAFTAR'?5000:1000) + r.width + r.y; // prefer DAFTAR & lebar
        if(!f || score>f.score) f={x:r.x+r.width/2,y:r.y+r.height/2,t,score};
      });
      return f;
    }""")
    if tgt:
        p.mouse.move(tgt["x"], tgt["y"]); time.sleep(0.2)
        p.mouse.down(); time.sleep(0.1); p.mouse.up()
        # fallback: klik via JS langsung ke elemen (kalau mouse kena overlay)
        time.sleep(0.3)
        p.evaluate("""()=>{
          const b=[...document.querySelectorAll('button,div,span,a')].find(e=>{
            const t=(e.innerText||'').trim().toUpperCase();
            const r=e.getBoundingClientRect();
            return /^(DAFTAR|SELESAI)$/.test(t) && r.width>150 && r.y>200;});
          if(b){['mousedown','mouseup','click'].forEach(ev=>b.dispatchEvent(new MouseEvent(ev,{bubbles:true,clientX:0,clientY:0})));}
        }""")
    return tgt


def click_btn(p, labels=r"lanjut|verifikasi|daftar|confirm|kirim|next"):
    """Klik tombol — prioritas tombol BESAR (submit form), bukan link navbar."""
    tgt = p.evaluate("""(pat)=>{let f=null;const re=new RegExp('^('+pat+')$','i');
        document.querySelectorAll('button,div,span,a').forEach(e=>{
        const t=(e.childElementCount===0?(e.textContent||''):'').trim();
        const r=e.getBoundingClientRect();
        if(re.test(t) && r.width>0 && r.height>0){
          // skip navbar/header (top < 120px = logo area)
          if(r.y < 120) return;
          // prioritas tombol besar (width > 200)
          const score = (r.width > 200 ? 1000 : 0) + r.y;
          if(!f || score > f.score) f={x:r.x+r.width/2,y:r.y+r.height/2,t,score};
        }});return f;}""", labels)
    if tgt:
        p.mouse.move(tgt["x"], tgt["y"]); time.sleep(0.15)
        p.mouse.down(); time.sleep(0.08); p.mouse.up()
    return tgt


def norm_password(pw, strict=False):
    """Pastikan password penuhi rule Shopee: min 1 lowercase, min 1 UPPERCASE, 8-16 char.
    strict=True → pakai apa adanya (untuk user yang minta lowercase-only)."""
    pw = pw or "PASS_REDACTED"
    if strict:
        return pw
    if not any(c.islower() for c in pw):
        pw = "a" + pw
    if not any(c.isupper() for c in pw):
        # kapitalkan huruf pertama
        pw = pw[0].upper() + pw[1:]
    if len(pw) > 16:
        pw = pw[:16]
    if len(pw) < 8:
        pw = pw + "A1234"
    return pw


def activate_and_extract(p, phone, pw, fingerprint=""):
    """AKTIVASI + EKSTRAK via browser context langsung (cookie auto-attached).

    1. Tunggu halaman settle (masih di /buyer/signup success)
    2. Panggil get_account_info DARI BROWSER — cookie otomatis dikirim
    3. Kalau dapat userid → login beneran; baca semua cookie
    """
    user_id = ""
    # 1) panggil API dari browser (cookie auto)
    try:
        info = p.evaluate("""async ()=>{
          try{
            const r=await fetch('https://shopee.co.id/api/v4/account/basic/get_account_info',
              {headers:{'x-api-source':'pc','x-requested-with':'XMLHttpRequest','af-ac-enc-dat':''},credentials:'include'});
            const j=await r.json(); return j;
          }catch(e){return {err:String(e)};}
        }""")
        if isinstance(info, dict) and info.get("data"):
            user_id = str(info["data"].get("userid", "") or info["data"].get("username", ""))
            log(f"API account_info: userid={user_id}")
    except Exception as e:
        log(f"api err {e}")

    # 2) kalau belum dapat userid, coba goto homepage lalu retry
    if not user_id:
        try:
            p.goto("https://shopee.co.id/", wait_until="domcontentloaded", timeout=45000)
            time.sleep(6)
            info2 = p.evaluate("""async ()=>{
              try{const r=await fetch('/api/v4/account/basic/get_account_info',
                {headers:{'x-api-source':'pc','x-requested-with':'XMLHttpRequest'},credentials:'include'});
                return await r.json();}catch(e){return {err:String(e)};}}""")
            if isinstance(info2, dict) and info2.get("data"):
                user_id = str(info2["data"].get("userid", "") or info2["data"].get("username", ""))
                log(f"API(2) userid={user_id}")
        except Exception as e:
            log(f"api2 err {e}")

    # 3) baca cookie: ambil SEMUA cookie shopee (dari context)
    try:
        allc = p.context.cookies()
    except Exception:
        allc = []
    seen = {}
    for c in allc:
        dom = (c.get("domain") or "").lower()
        nm = c.get("name", "")
        if "shopee" in dom or nm.startswith(("SPC", "_sapid", "csrftoken", "REC", "ssr-tz",
                                              "shopee", "_QPW", "language", "ds", "sense", "_ga", "_gcl", "_fbp", "fr")):
            seen[nm] = c["value"]
    cookie_str = "; ".join(f"{k}={v}" for k, v in seen.items())

    device_id = seen.get("SPC_CLIENTID", "") or seen.get("SPC_CDS", "")
    fp = fingerprint or seen.get("_sapid", "")

    return {
        "phone": phone,
        "username": user_id or phone,
        "password": pw,
        "user_id": user_id,
        "fingerprint": fp,
        "device_id": device_id,
        "cookie": cookie_str,
    }


def extract_account(p, phone, pw, fingerprint=""):
    """Wrapper lama → pakai activate_and_extract."""
    return activate_and_extract(p, phone, pw, fingerprint)


def write_account(acc):
    """Simpan hasil akun ke file teks + json."""
    try:
        with open(f"{ROOT}/account_result.json", "a") as f:
            f.write(json.dumps(acc, ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        with open(f"{ROOT}/accounts_success.txt", "a") as f:
            f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(f"Username  : {acc['username']}\n")
            f.write(f"Password  : {acc['password']}\n")
            f.write(f"Nomor     : {acc['phone']}\n")
            f.write(f"UserId    : {acc['user_id']}\n")
            f.write(f"Fingerprnt: {acc['fingerprint']}\n")
            f.write(f"DeviceID  : {acc['device_id']}\n")
            f.write(f"Cookie    : {acc['cookie']}\n")
    except Exception:
        pass


def fill_password(p, pw, strict=False):
    pw = norm_password(pw, strict=strict)
    fields = p.evaluate("""()=>{const o=[];document.querySelectorAll('input[type=password],input').forEach(i=>{
        const r=i.getBoundingClientRect();if(r.width>0&&r.height>0&&r.width>120)o.push({x:r.x+r.width/2,y:r.y+r.height/2});});return o;}""")
    if not fields: return {"err": "no pw field"}
    for i in range(min(2, len(fields))):
        p.mouse.click(fields[i]["x"], fields[i]["y"]); time.sleep(0.15+random.random()*0.1)
        p.keyboard.type(pw, delay=70+int(random.random()*60))
    return {"ok": True, "n": min(2, len(fields)), "pw": pw}


def force_submit_password(p, pw):
    """Bypass validasi frontend Shopee: inject value native, buang rule error,
    enable tombol DAFTAR, klik paksa. Return status."""
    pw = norm_password(pw, strict=True)
    r = p.evaluate("""(pw)=>{
      const res={injected:0, clicked:false, btnFound:false};
      // 1) cari field password (visible, lebar)
      const fields=[...document.querySelectorAll('input[type=password],input')].filter(i=>{
        const b=i.getBoundingClientRect(); return b.width>120 && b.height>0;
      });
      const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
      fields.forEach(i=>{
        i.focus();
        setter.call(i, pw);
        i.dispatchEvent(new Event('input',{bubbles:true}));
        i.dispatchEvent(new Event('change',{bubbles:true}));
        i.dispatchEvent(new KeyboardEvent('keyup',{bubbles:true}));
        res.injected++;
      });
      // 2) hapus / sembunyikan pesan error huruf besar (biar ga blok)
      document.querySelectorAll('*').forEach(e=>{
        const t=(e.textContent||'');
        if(/huruf besar/i.test(t) && (e.children.length===0)){
          e.style.color='green';
          e.textContent='Min. satu karakter huruf besar \\u2713';
        }
      });
      return res;
    }""", pw)
    time.sleep(0.4)
    # 3) force-enable + klik tombol DAFTAR
    r2 = p.evaluate("""()=>{
      const out={btnFound:false, enabled:false, clicked:false};
      const btns=[...document.querySelectorAll('button')].filter(b=>/DAFTAR/i.test(b.innerText));
      const big=btns.sort((a,b)=>b.getBoundingClientRect().width-a.getBoundingClientRect().width)[0];
      if(!big) return out;
      out.btnFound=true;
      big.removeAttribute('disabled');
      big.disabled=false;
      big.classList.remove('disabled','btn-disabled');
      out.enabled=!big.disabled;
      const rct=big.getBoundingClientRect();
      return Object.assign(out,{x:rct.x+rct.width/2, y:rct.y+rct.height/2});
    }""")
    if r2.get("btnFound"):
        try:
            p.mouse.click(r2["x"], r2["y"])
            r2["clicked"]=True
        except Exception as e:
            r2["err_click"]=str(e)[:60]
    return {"inject": r, "btn": r2}


LIMIT_KW = ["aktivitas tidak wajar", "terdeteksi aktivitas", "membacakan kode otp",
            "menghubungi no", "too many attempts", "terlalu sering", "coba lagi nanti",
            "batas", "limit"]
REGIS_LIMIT_KW = ["diperlukan identifikasi tambahan", "informasi kontakmu",
                  "identifikasi tambahan"]


def detect_limit(p):
    """[ENH #5] Deteksi limit kirim OTP. Return keyword atau None."""
    try:
        t = (p.evaluate("()=>document.body?document.body.innerText:''") or "").lower()
    except Exception:
        return None
    for kw in LIMIT_KW:
        if kw in t:
            return kw
    return None


def detect_limit_regis(p):
    """[ENH #6] Deteksi limit registrasi (butuh CS)."""
    try:
        t = (p.evaluate("()=>document.body?document.body.innerText:''") or "").lower()
    except Exception:
        return None
    for kw in REGIS_LIMIT_KW:
        if kw in t:
            return kw
    return None


def check_limit_modal(p):
    """[ENH-D2] Deteksi modal 'Diperlukan Identifikasi Tambahan' → nomor LIMIT/tak bisa register.
    Return True kalau modal ini ada (nomor di-flag Shopee)."""
    try:
        t = p.evaluate("()=>document.body?document.body.innerText:''") or ""
    except Exception:
        return False
    return ("Diperlukan Identifikasi Tambahan" in t) or ("membutuhkan informasi kontakmu" in t) \
        or ("CS Shopee membutuhkan" in t)


def detect_akun_sudah(p):
    """[ENH #7 / ENH-D1] Tangani dua interstitial Shopee:
    (a) 'Apakah ini akunmu?' → klik 'Buka, buat akun baru'
    (b) MODAL 'Diperlukan Identifikasi Tambahan' → klik 'Ya, Lanjutkan' (paksa lanjut buat akun)
    Return True kalau ada tombol yang ke-klik."""
    try:
        t = p.evaluate("()=>document.body?document.body.innerText:''") or ""
    except Exception:
        return False
    # (b) MODAL anti-fraud baru
    if "Diperlukan Identifikasi Tambahan" in t or "membutuhkan informasi kontakmu" in t:
        r = p.evaluate("""()=>{
          const els=[...document.querySelectorAll('button,div,a,span')];
          // prioritaskan 'Ya, Lanjutkan' (oranye) — paksa bikin akun
          let b=els.find(e=>{const x=(e.innerText||'').trim();return /^Ya,? Lanjutkan$/i.test(x) && e.children.length<=2;});
          if(!b) b=els.find(e=>{const x=(e.innerText||'').trim();return /Lanjutkan/i.test(x) && !/Batal/i.test(x) && e.children.length<=1;});
          if(b){b.click();return true;}
          return false;}""")
        if r:
            try: log("[ENH-D1] modal 'Identifikasi Tambahan' → klik 'Ya, Lanjutkan'")
            except Exception: pass
            return True
    # (a) versi lama
    if ("Apakah ini akunmu" in t) or ("sudah terdaftar" in t):
        r = p.evaluate("""()=>{
          const els=[...document.querySelectorAll('button,div,a,span')];
          const t=els.find(e=>{const x=(e.innerText||'').trim();
            return (x.startsWith('Buka') && x.includes('buat akun baru') && e.children.length<=1);});
          if(t){t.click();return true;}
          const t2=els.find(e=>{const x=(e.innerText||'').trim();
            return ((x.includes('buat akun baru')||x.includes('Bukan')) && e.children.length<=1);});
          if(t2){t2.click();return true;}
          return false;}""")
        return bool(r)
    return False


AUTH_KEYS = ("SPC_U", "SPC_CLIENTID", "SPC_ST")


def auth_cookie_ready(p):
    """[ENH #8] Cek cookie auth sudah lengkap (login benar-benar terjadi)."""
    try:
        cookies = {c["name"]: c["value"] for c in p.context.cookies()}
    except Exception:
        return False, []
    missing = [k for k in AUTH_KEYS if k not in cookies]
    return (len(missing) == 0), missing


def try_login_flow(p, phone, pw):
    """[ENH-SR] Login ulang dalam browser yg sama (session sudah punya fingerprint).

    Dipakai kalau registrasi selesai tapi auth cookie belum lengkap.
    Return True kalau auth cookie jadi lengkap.
    """
    import time as _t
    try:
        log(f"[ENH-SR] buka login page utk {phone}")
        p.goto("https://shopee.co.id/buyer/login", wait_until="domcontentloaded", timeout=45000)
        # tunggu input nomor
        for _ in range(20):
            if p.locator("input[type='text']").count():
                break
            _t.sleep(1)
        # isi nomor
        try:
            p.locator("input[type='text']").first.click(timeout=3000, force=True)
            p.locator("input[type='text']").first.fill(phone)
        except Exception:
            pass
        _t.sleep(0.6)
        # isi password
        try:
            p.locator("input[type='password']").first.click(timeout=3000, force=True)
            p.locator("input[type='password']").first.fill(pw)
        except Exception:
            pass
        _t.sleep(0.6)
        # klik Log in (force → JS fallback)
        clicked = False
        for sel in ["button:has-text('Log in')", "button:has-text('Log In')", "button[type='submit']"]:
            try:
                loc = p.locator(sel).first
                if loc.count():
                    loc.click(timeout=5000, force=True)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            try:
                p.evaluate("()=>{const b=[...document.querySelectorAll('button')].find(x=>/log ?in|masuk/i.test(x.innerText));if(b)b.click();}")
            except Exception:
                pass
        _t.sleep(6)
        # klik "Tetap Login" kalau muncul
        for sel in ["text=Tetap Login", "button:has-text('Tetap Login')", "text=Oke"]:
            try:
                if p.locator(sel).count():
                    p.locator(sel).first.click(timeout=3000, force=True)
                    _t.sleep(4)
                    break
            except Exception:
                pass
        # tunggu auth cookie jadi
        for _ in range(20):
            ready, _ = auth_cookie_ready(p)
            if ready:
                return True
            _t.sleep(1)
        # kunjungi home sekali lagi (pancing SPC_U/SPC_ST)
        try:
            p.goto("https://shopee.co.id/", wait_until="domcontentloaded", timeout=30000)
            _t.sleep(3)
        except Exception:
            pass
        ready, _ = auth_cookie_ready(p)
        return ready
    except Exception as e:
        log(f"[ENH-SR] login flow err {str(e)[:70]}")
        return False



def inject_fingerprint(context, page, custom_fp):
    """[ENH #4] Inject fingerprint shopee_webUnique_ccd (format part1|part2|part3|08|1)."""
    if not custom_fp:
        return False
    try:
        import urllib.parse as _up
        val = custom_fp if "%" in custom_fp else _up.quote(custom_fp, safe="")
        context.add_cookies([{
            "name": "shopee_webUnique_ccd", "value": val,
            "domain": ".shopee.co.id", "path": "/",
        }])
        page.add_init_script(
            "try{document.cookie='shopee_webUnique_ccd=%s; path=/; domain=.shopee.co.id';}catch(e){}" % val)
        log("[FP] ✅ custom fingerprint di-inject (shopee_webUnique_ccd)")
        return True
    except Exception as e:
        log(f"[FP] ⚠️ inject gagal: {e}")
        return False


def api_signup_by_otp(phone, password, otp_token, security_fp, session=None):
    """[ENH #11-12] Fallback signup via API. Password hash = sha256(md5(pw)).
    client_identifier.security_device_fingerprint = security_fp."""
    import hashlib, requests
    md5h = hashlib.md5(password.encode()).hexdigest()
    hashed = hashlib.sha256(md5h.encode()).hexdigest()
    payload = {
        "otp_token": otp_token,
        "password": hashed,
        "stay_logged_in": True,
        "client_identifier": {"security_device_fingerprint": security_fp},
    }
    s = session or requests.Session()
    try:
        r = s.post("https://shopee.co.id/api/v4/account/signup_by_otp", json=payload,
                   headers={"User-Agent": UA, "x-api-source": "pc",
                            "x-requested-with": "XMLHttpRequest",
                            "Origin": "https://shopee.co.id",
                            "Referer": "https://shopee.co.id/buyer/signup",
                            "Content-Type": "application/json"}, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": -1, "error_msg": str(e)[:120]}


def wait_for_otp():
    """Poll file .otp_input sampe ada isi. Window 15 menit (boss kirim manual)."""
    for _ in range(900):  # max 15 menit
        if os.path.exists(OTP_IN):
            code = open(OTP_IN).read().strip()
            if len(code) >= 4:
                os.remove(OTP_IN)
                return code
        time.sleep(1)
    return None


def main():
    # parse arg + option --retry=N --pw=CUSTOM --fp=FINGERPRINT
    retry_n = 8
    custom_pw = None
    custom_fp = None
    for a in sys.argv:
        if a.startswith("--retry="):
            try: retry_n = max(1, min(20, int(a.split("=", 1)[1])))
            except Exception: pass
        if a.startswith("--pw="):
            custom_pw = a.split("=", 1)[1]
        if a.startswith("--fp="):
            custom_fp = a.split("=", 1)[1].strip()
    argv = [a for a in sys.argv if not a.startswith("--")]
    phone = argv[1].lstrip("+0")
    if phone.startswith("62"): phone = phone[2:]
    # [ENH-B3] auto fingerprint dari fpgen (deterministik per nomor) kalau tak ada --fp
    if not custom_fp:
        try:
            import fpgen as _FP
            custom_fp = _FP.fp_shopee_ccd(phone)
            log(f"[FP] auto fingerprint (fpgen): {custom_fp[:32]}...")
        except Exception as _e:
            log(f"[FP] fpgen err {_e}")
    key = argv[2]
    # [P2] kalau key == "auto" → ambil dari KeyManager (rotasi + failover)
    if key in ("auto", "AUTO", ""):
        try:
            sys.path.insert(0, ROOT)
            from key_manager import KeyManager
            key = KeyManager().next() or key
            log(f"[KEY] auto-pick key {key[:10]}…")
        except Exception as _ke:
            log(f"[KEY] auto-pick err {_ke}")
    proxy = argv[3]
    channel = "wa"
    for a in argv[1:]:
        if a.lower() in ("wa", "sms"): channel = a.lower()
    pxy = parse_proxy(proxy)
    if proxy.strip().lower() in ("direct", "none", "-", ""):
        pxy = None   # no proxy — pakai IP host langsung
    # [CAPTURE] kalau --mitm: route browser lewat mitmproxy (127.0.0.1:8888)
    IGN_HTTPS = False
    if any(a == "--mitm" for a in sys.argv):
        pxy = {"server": "http://127.0.0.1:8888"}
        IGN_HTTPS = True
        log("[CAPTURE] browser → mitmproxy 127.0.0.1:8888 (capture mode)")
    # tulis custom password kalau ada
    if custom_pw:
        try: open(PW_IN, "w").write(custom_pw)
        except Exception: pass
    # bersihin file lama
    for f in (OTP_IN, PW_IN) if not custom_pw else (OTP_IN,):
        try: os.remove(f)
        except Exception: pass
    log(f"START phone={phone} retry={retry_n}")

    with sync_playwright() as pw:
        HEADLESS = any(a == "--headless" for a in sys.argv)   # B2: browser tipis (hemat RAM, no xvfb)
        _args = ["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        if HEADLESS:
            _args += ["--disable-dev-shm-usage", "--use-gl=swiftshader"]
            log("[B2] HEADLESS mode (browser tipis)")
        b = pw.chromium.launch(headless=HEADLESS, args=_args)
        c = b.new_context(user_agent=UA, locale="id-ID", proxy=pxy,
                          ignore_https_errors=IGN_HTTPS,
                          extra_http_headers={"Accept-Language": "id-ID,id;q=0.9,en;q=0.8"},
                          viewport={"width": 1280, "height": 900})
        c.add_cookies([{"name": "shopee_webLanguage", "value": "id", "domain": ".shopee.co.id", "path": "/"}])
        p = c.new_page()
        # [ENH-CAP] CDP network capture — rekam SEMUA request/response ke jsonl (maximal API capture)
        _capf = f"{ROOT}/capture/run_{phone}_{int(time.time())}.jsonl"
        _cap = open(_capf, "a")
        try:
            _cdp = c.new_cdp_session(p)
            _cdp.send("Network.enable", {"maxResourceBufferSize": 10_000_000, "maxTotalBufferSize": 50_000_000})
            _bodies = {}
            def _on_req(ev):
                try:
                    r = ev.get("request", {})
                    _bodies[ev["requestId"]] = {"url": r.get("url"), "method": r.get("method"),
                                                "headers": r.get("headers", {}), "postData": r.get("postData", "")}
                except Exception:
                    pass
            def _on_resp(ev):
                try:
                    rid = ev["requestId"]; resp = ev.get("response", {})
                    rec = _bodies.get(rid, {"url": resp.get("url")})
                    rec["status"] = resp.get("status")
                    rec["resp_headers"] = {k: v for k, v in (resp.get("headers") or {}).items()
                                           if k.lower() in ("content-type", "x-sap-ri", "x-sap-sec", "af-ac-enc-sz-token")}
                    if "/api/" in (rec.get("url") or "") or "signup" in (rec.get("url") or "") \
                            or "captcha" in (rec.get("url") or "") or "otp" in (rec.get("url") or ""):
                        _cap.write(json.dumps(rec) + "\n"); _cap.flush()
                except Exception:
                    pass
            _cdp.on("Network.requestWillBeSent", _on_req)
            _cdp.on("Network.responseReceived", _on_resp)
            log(f"[CAPTURE] CDP network → {_capf}")
        except Exception as _e:
            log(f"[CAPTURE] CDP err {str(_e)[:80]}")
        # [ENH #4] inject custom fingerprint SEBELUM buka signup
        if custom_fp:
            inject_fingerprint(c, p, custom_fp)
        try:
            p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
            time.sleep(3)
            for _ in range(40):
                t = p.evaluate("()=>document.body.innerText||''")
                if "Pilih bahasa" not in t and p.evaluate("()=>document.querySelectorAll('input').length")>0: break
                try: p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=1500, force=True)
                except Exception: pass
                time.sleep(1.2)
            from tools.signup_driver import fill_field
            fill_field(p, 0, phone); time.sleep(1.5)
            for sel in ["button:has-text('BERIKUTNYA')", "text=BERIKUTNYA", "button:has-text('Berikutnya')"]:
                try:
                    loc = p.locator(sel).first
                    if loc.count():
                        bb = loc.bounding_box()
                        if bb:
                            p.mouse.move(bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2); time.sleep(0.15)
                            p.mouse.down(); time.sleep(0.08); p.mouse.up(); break
                except Exception: continue
            time.sleep(1.8)
            # tunggu TOS → captcha
            st = "wait"
            for _ in range(45):
                time.sleep(2)
                # [ENH #6] LIMIT REGIS
                rl = detect_limit_regis(p)
                if rl:
                    log(f"LIMIT_REGIS: {rl}")
                    write_status("LIMIT_REGIS")
                    return
                # [ENH #5] LIMIT OTP
                lk = detect_limit(p)
                if lk:
                    log(f"LIMIT: {lk}")
                    write_status("LIMIT")
                    return
                # [ENH #7] 'Apakah ini akunmu?' → buat akun baru
                if detect_akun_sudah(p):
                    log("akun sudah terdaftar → klik 'Bukan, buat akun baru'")
                    time.sleep(2)
                st = state(p)
                if st == "TOS":
                    click_btn(p, r"setuju|agree")
                if st in ("CAPTCHA", "OTP", "OTP_MODAL", "ERROR"): break
            log(f"STATE={st}")
            # [FIX] STATE=? (halaman stuck/gagal render) → reload & coba lagi
            if st not in ("CAPTCHA", "OTP", "OTP_MODAL", "ERROR", "LIMIT", "LIMIT_REGIS", "SUCCESS"):
                for _rl in range(3):
                    log(f"STATE={st} → reload page (try {_rl+1}/3)")
                    from tools.signup_driver import fill_field as _ff
                    try:
                        p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
                    except Exception as _ge:
                        log(f"reload err {str(_ge)[:50]}")
                    time.sleep(4)
                    for _ in range(30):
                        t = p.evaluate("()=>document.body.innerText||''")
                        if "Pilih bahasa" not in t and p.evaluate("()=>document.querySelectorAll('input').length") > 0:
                            break
                        try: p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=1500, force=True)
                        except Exception: pass
                        time.sleep(1.2)
                    _ff(p, 0, phone); time.sleep(1.5)
                    for sel in ["button:has-text('BERIKUTNYA')", "text=BERIKUTNYA", "button:has-text('Berikutnya')"]:
                        try:
                            loc = p.locator(sel).first
                            if loc.count():
                                bb = loc.bounding_box()
                                if bb:
                                    p.mouse.move(bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2); time.sleep(0.15)
                                    p.mouse.down(); time.sleep(0.08); p.mouse.up(); break
                        except Exception: continue
                    for _ in range(25):
                        time.sleep(2)
                        if detect_limit_regis(p): log("LIMIT_REGIS"); write_status("LIMIT_REGIS"); return
                        if detect_limit(p): log("LIMIT"); write_status("LIMIT"); return
                        st = state(p)
                        if st == "TOS": click_btn(p, r"setuju|agree")
                        if st in ("CAPTCHA", "OTP", "OTP_MODAL", "ERROR"): break
                    log(f"STATE after reload={st}")
                    if st in ("CAPTCHA", "OTP", "OTP_MODAL", "ERROR"): break
            if st == "CAPTCHA":
                for _w in range(20):
                    if not p.evaluate("()=>/Memuat/i.test(document.body.innerText||'')"): break
                    time.sleep(1)
                time.sleep(2)
                locked = None
                for attempt in range(retry_n):
                    if locked is None:
                        if p.evaluate(JS_PRESENT, [IC_PIECE]): locked = "image_crawl"
                        elif p.evaluate(JS_PRESENT, [PZ_PIECE]): locked = "puzzle"
                        elif p.evaluate(JS_PRESENT, [ID_PUZZLE, ID_VERIFY]): locked = "image_drag"
                        else: locked = "image_crawl"
                    info = solve_image_crawl(p, key) if locked == "image_crawl" else {"err": "type " + str(locked)}
                    log(f"attempt {attempt+1}: {info}")
                    # [FIX] 400 'no answer' → captcha jelek; refresh & coba lagi
                    if isinstance(info, dict) and str(info.get("err", "")).startswith("400"):
                        log("400 no-answer → refresh captcha")
                        try: _click_reset(p)
                        except Exception: pass
                        time.sleep(2)
                        try:
                            # tunggu puzzle baru ke-render
                            for _ in range(30):
                                if dataurl(p, IC_PUZZLE): break
                                time.sleep(0.3)
                        except Exception: pass
                    time.sleep(3)
                    st2 = state(p)
                    # tandai hasil ke cache (hit/miss) berdasarkan transisi state
                    try:
                        if isinstance(info, dict) and info.get("pz") and info.get("pc"):
                            from captcha_cache import CaptchaCache
                            _cc = CaptchaCache()
                            if st2 in ("OTP", "OTP_MODAL", "PASSWORD", "SUCCESS"):
                                _cc.mark_result(info["pz"], info["pc"], True)
                            elif st2 == "CAPTCHA":
                                _cc.mark_result(info["pz"], info["pc"], False)
                    except Exception:
                        pass
                    if st2 in ("OTP", "OTP_MODAL"): st = st2; break
                    if st2 != "CAPTCHA": st = st2; break
            if st in ("OTP", "OTP_MODAL"):
                # klik kirim WA kalau ada
                click_btn(p, r"kirim ke whatsapp|kirim kode|kirim otp|kirim")
                log("OTP_REQUESTED — tulis kode ke .otp_input")
                write_status("WAITING_OTP")
                code = wait_for_otp()
                if code:
                    log(f"OTP received: {code}")
                    r_otp = fill_otp(p, code)
                    log(f"fill_otp: {r_otp}")
                    time.sleep(0.5)
                    # klik LANJUT — coba multi-cara
                    lj = click_btn(p, r"lanjut|verifikasi|confirm|kirim|next")
                    log(f"click LANJUT: {lj}")
                    if not lj:
                        # fallback 1: Enter
                        try: p.keyboard.press("Enter"); log("pressed Enter")
                        except Exception: pass
                        # fallback 2: klik tombol disabled-orange besar
                        time.sleep(0.5)
                        lj2 = p.evaluate("""()=>{let f=null;document.querySelectorAll('button').forEach(e=>{
                            const t=(e.textContent||'').trim().toUpperCase();
                            if(!f && (t==='LANJUT'||t==='VERIFIKASI')){const r=e.getBoundingClientRect();
                            if(r.width>0)f={x:r.x+r.width/2,y:r.y+r.height/2,t};}});return f;}""")
                        if lj2:
                            p.mouse.move(lj2["x"], lj2["y"]); time.sleep(0.1)
                            p.mouse.down(); time.sleep(0.08); p.mouse.up()
                            log(f"click btn2: {lj2}")
                    time.sleep(5)
                    st = state(p)
                    log(f"STATE after OTP: {st}")
                    # [DEBUG] dump halaman setelah OTP
                    try:
                        _txt = (p.evaluate("()=>document.body?document.body.innerText:''") or "")[:400].replace("\n", " | ")
                        log(f"[PAGE] {_txt}")
                        p.screenshot(path=f"{ROOT}/shots/otp_after_{phone}.png")
                    except Exception:
                        pass
                    # [ENH-D2] modal 'Identifikasi Tambahan' muncul → nomor LIMIT (report, jangan paksa)
                    if check_limit_modal(p):
                        log("[ENH-D2] ⛔ MODAL 'Diperlukan Identifikasi Tambahan' → NOMOR LIMIT / tak bisa register")
                        write_status("LIMIT_MODAL")
                        p.screenshot(path=f"{ROOT}/shots/hold_{phone}_LIMIT.png")
                        try:
                            open(f"{ROOT}/limited_numbers.txt", "a").write(phone + "\n")
                        except Exception: pass
                        # lanjut ekstrak (kalau ada cookie) lalu tandai
                    # [ENH #7-B / ENH-D1] interstitial: 'Apakah ini akunmu?' ATAU modal 'Identifikasi
                    # Tambahan' → klik lanjut & PUSH terus sampai state maju (max 5x)
                    for _ii in range(5):
                        _handled = detect_akun_sudah(p)
                        if _handled:
                            time.sleep(3); st = state(p)
                            log(f"[ENH-D1] interstitial handled #{_ii+1} → STATE: {st}")
                            if st not in ("?", "OTP", "OTP_MODAL"):
                                break
                        else:
                            break
                    # kalau masih buntu di '?' → coba refresh & ulang deteksi
                    if st == "?":
                        try:
                            log("[ENH-D1] state '?' → tunggu/refresh")
                            time.sleep(3)
                            for _ii in range(3):
                                if detect_akun_sudah(p):
                                    time.sleep(3); st = state(p)
                                    log(f"[ENH-D1] retry handled → STATE: {st}")
                                    if st not in ("?",): break
                                else:
                                    time.sleep(2)
                        except Exception: pass
                    # kalau OTP masih OTP (belum lanjut) → klik LANJUT lagi
                    if st in ("OTP", "OTP_MODAL") and "Salah" not in p.evaluate("()=>document.body.innerText||''"):
                        log("masih OTP — klik LANJUT ulang")
                        try: p.keyboard.press("Enter")
                        except Exception: pass
                        time.sleep(0.5)
                        click_btn(p, r"lanjut|verifikasi|confirm")
                        time.sleep(5); st = state(p)
                        log(f"STATE after retry-LANJUT: {st}")
                    # kalau OTP salah → minta ulang
                    if "Salah" in p.evaluate("()=>document.body.innerText||''"):
                        log("OTP SALAH — reset, tulis ulang ke .otp_input")
                        write_status("OTP_WRONG")
                        code = wait_for_otp()
                        if code:
                            r_otp = fill_otp(p, code)
                            log(f"retry fill_otp: {r_otp}")
                            time.sleep(0.5)
                            try: p.keyboard.press("Enter")
                            except Exception: pass
                            click_btn(p, r"lanjut|verifikasi|confirm")
                            time.sleep(5); st = state(p)
                            log(f"STATE after OTP-retry: {st}")
                    if st == "PASSWORD":
                        pw = open(PW_IN).read().strip() if os.path.exists(PW_IN) else "PASS_REDACTED"
                        _strict = bool(custom_pw)
                        r_pw = fill_password(p, pw, strict=_strict)
                        log(f"fill_password: {r_pw} (strict={_strict})")
                        time.sleep(0.8)
                        # [ENH-B4] SELALU jalankan force_submit (bypass validasi huruf besar) —
                        # sebelumnya hanya saat _strict, bikin gagal kalau --pw tak dipass.
                        try:
                            fr = force_submit_password(p, pw)
                            log(f"force_submit: {fr}")
                        except Exception as _e:
                            log(f"force_submit err {str(_e)[:80]}")
                        time.sleep(1)
                        # cek validator + submit normal sebagai fallback
                        for _try in range(3):
                            tgt = click_daftar_submit(p)
                            log(f"click DAFTAR submit try{_try+1}: {tgt}")
                            time.sleep(4)
                            st = state(p)
                            if st != "PASSWORD": break
                            # masih PASSWORD → perbaiki password
                            r_pw = fill_password(p, pw, strict=_strict)
                            log(f"retry fill_password: {r_pw}")
                            time.sleep(0.8)
                        time.sleep(3)
                        st = state(p)
                        log(f"STATE final: {st}")
                        # [ENH-C1] #12: kalau UI DAFTAR gagal (masih PASSWORD) → fallback signup_by_otp via page fetch
                        if st == "PASSWORD" and not _strict:
                            try:
                                import pure_signup as _PS
                                _fp2 = p.evaluate(FP_EXPR) or ""
                                _res = _PS.signup_by_otp_page(p, pw, "", _fp2)
                                log(f"[ENH-C1] pure signup_by_otp (page) → {str(_res)[:140]}")
                                time.sleep(3)
                                st = state(p)
                                log(f"[ENH-C1] STATE after pure signup: {st}")
                            except Exception as _e:
                                log(f"[ENH-C1] pure signup err {str(_e)[:80]}")
                        # [ENH #8] tunggu auth cookie (SPC_U/SPC_CLIENTID/SPC_ST) sampai 45s
                        _auth_ok = False
                        for _aw in range(45):
                            ready, miss = auth_cookie_ready(p)
                            if ready:
                                log("[AUTH] cookie auth LENGKAP (SPC_U/SPC_CLIENTID/SPC_ST)")
                                _auth_ok = True; break
                            if detect_akun_sudah(p):
                                log("[AUTH] 'Apakah ini akunmu?' → buat akun baru")
                            # [ENH-B2] tiap 10s: kunjungi home agar SPC_ST/SPC_U ter-set
                            if _aw in (10, 25):
                                try:
                                    p.goto("https://shopee.co.id/", wait_until="domcontentloaded", timeout=30000)
                                    time.sleep(2)
                                except Exception: pass
                            time.sleep(1)
                        if not _auth_ok:
                            _r, _m = auth_cookie_ready(p)
                            log(f"[AUTH] ⚠️ cookie auth belum lengkap, missing={_m}")
                            # [ENH-B2] paksa settle & ulang sekali
                            try:
                                p.goto("https://shopee.co.id/", wait_until="domcontentloaded", timeout=30000)
                                time.sleep(4)
                                _r, _m = auth_cookie_ready(p)
                                log(f"[AUTH] retry2 → ready={_r} missing={_m}")
                            except Exception: pass
                    write_status(f"DONE_{st}")
                    p.screenshot(path=f"{ROOT}/shots/hold_{phone}_final_{st}.png")
                    # ===== EKSTRAK DATA AKUN =====
                    if st in ("SUCCESS", "PASSWORD") or "berhasil" in p.evaluate("()=>document.body.innerText||''").lower():
                        try:
                            # --- AKTIVASI + EKSTRAK (browser-context, cookie auto) ---
                            _fp = p.evaluate(FP_EXPR) or ""
                            _pw = norm_password(pw if 'pw' in dir() else 'PASS_REDACTED', strict=bool(custom_pw))
                            # [ENH-SR] SEBELUM ekstrak: pastikan auth cookie ada.
                            # Kalau belum → coba LOGIN ULANG dgn browser yg sama (session fresh).
                            try:
                                _ready, _miss = auth_cookie_ready(p)
                                if not _ready:
                                    log(f"[ENH-SR] auth belum lengkap ({_miss}) → coba LOGIN ULANG")
                                    login_ok = try_login_flow(p, phone, _pw)
                                    log(f"[ENH-SR] login ulang: {login_ok}")
                                    _ready2, _miss2 = auth_cookie_ready(p)
                                    log(f"[ENH-SR] auth setelah login: ready={_ready2} miss={_miss2}")
                            except Exception as _le:
                                log(f"[ENH-SR] login-ulang err {str(_le)[:80]}")
                            acc = extract_account(p, phone, _pw, _fp)
                            vok, vmsg = True, "skip"
                            try:
                                import validate_account as _VA
                                vr = _VA.validate(acc["cookie"])
                                vok = bool(vr.get("ok"))
                                vmsg = "AKTIF" if vok else str(vr.get("reason", "?"))[:40]
                                if vok and not acc["user_id"]:
                                    acc["user_id"] = str(vr.get("userid", ""))
                                    acc["username"] = acc["user_id"] or acc["username"]
                                acc["validated"] = vok; acc["validate_msg"] = vmsg
                                log(f"VALIDATE: {vmsg} user_id={acc['user_id']}")
                            except Exception as _ve:
                                log(f"validate err: {_ve}")
                            write_account(acc)
                            write_status("SUCCESS_VALID" if vok else f"SUCCESS_UNVALID:{vmsg}")
                            log(f"ACCOUNT_SAVED user_id={acc['user_id']} device={acc['device_id'][:12]} valid={vok}")
                        except Exception as _e:
                            log(f"extract err: {_e}")
                else:
                    log("OTP timeout")
                    write_status("OTP_TIMEOUT")
            else:
                write_status(f"NOT_OTP_{st}")
                p.screenshot(path=f"{ROOT}/shots/hold_{phone}_{st}.png")
            # tahan 30s biar bisa screenshot
            time.sleep(10)
        except Exception as e:
            log(f"ERR: {e.__class__.__name__}: {e}")
        finally:
            b.close()
            log("CLOSED")


if __name__ == "__main__":
    main()
