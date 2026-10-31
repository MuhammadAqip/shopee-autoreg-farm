#!/usr/bin/env python3
"""Shopee slider captcha — ONE-SHOT solver (final).

Satu run: proxy + nomor -> signup -> captcha -> crop(canvas rect) -> gap detect
-> human drag -> verify -> tunggu OTP.

Aturan Shopee: tiap nomor HANYA diterima di percobaan PERTAMA. Jadi solver ini
dirancang jalan penuh dalam satu pass (tanpa retry nomor).

Pakai:
  xvfb-run -a --server-args="-screen 0 1280x900x24" \
    /root/sniffenv/bin/python solve_one.py <phone> [proxy]

  phone : 62-format tanpa 0/62 depan, mis. 89601416330
  proxy : http://user:pass@host:port (opsional; default acak dari proxies.txt)
"""
import sys, os, time, json, io, random
sys.path.insert(0, "/root/shopee-farm")
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
from tools.signup_driver import fill_field, click_submit, JS_CLICK_AGREE
from tools.captcha_flow import wait_captcha
from tools.captcha_hook import install_captcha_hook
from tools.ui_solver import human_drag

ROOT = "/root/shopee-farm"
_PROP_CACHE = {}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def parse_proxy(px):
    cred, host = px.split("@")
    return {"server": "http://" + host,
            "username": cred.split("://")[1].split(":")[0],
            "password": cred.split(":")[-1]}


def get_proxy(arg):
    if arg:
        return arg
    px = [l.strip() for l in open(f"{ROOT}/proxies.txt") if l.strip()]
    random.seed(int(time.time()))
    return random.choice(px)


def canvas_rect(p):
    return p.evaluate("""() => {
        const c=[...document.querySelectorAll('canvas')]
            .map(c=>c.getBoundingClientRect()).filter(r=>r.width>150);
        if(!c.length) return null; const r=c[0];
        return {x:r.x, y:r.y, w:r.width, h:r.height};
    }""")


def synth_drag(p, distance):
    """drag dgn dispatch synthetic PointerEvent/DragEvent KE GRIP ELEMENT
    (pola persis dragWithPreciseMonitoring di ekstensi SadCaptcha).
    Return True kalau piece translateX tercapai."""
    import math as _m
    gb = p.locator("aside[aria-modal=true] div.dExCsf").first.bounding_box()
    if not gb:
        return False
    sx = gb["x"] + gb["width"]/2
    sy = gb["y"] + gb["height"]/2
    # natural approach via mousemove dispatch
    apx = sx - 80 - random.random()*40
    apy = sy + 40 + random.random()*30
    def mv(x, y):
        p.evaluate("""(a)=>{const C=document.documentElement||document.body;
            C.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,view:window,clientX:a[0],clientY:a[1]}));}""", [x, y])
    def grip_ev(kind, x, y):
        p.evaluate("""(a)=>{const g=document.querySelector('aside[aria-modal=true] div.dExCsf');
            if(!g)return;
            g.dispatchEvent(new PointerEvent(a[0],{pointerType:'mouse',width:1,height:1,cancelable:true,bubbles:true,view:window,clientX:a[1],clientY:a[2]}));}""", [kind, x, y])
    def drag_ev(kind, x, y):
        p.evaluate("""(a)=>{const g=document.querySelector('aside[aria-modal=true] div.dExCsf');
            if(!g)return;
            g.dispatchEvent(new DragEvent(a[0],{cancelable:true,bubbles:true,view:window,clientX:a[1],clientY:a[2]}));}""", [kind, x, y])
    # approach
    for i in range(9):
        t = i/8
        mv(apx+(sx-apx)*t, apy+(sy-apy)*t)
        time.sleep(0.02)
    time.sleep(0.25)
    mv(sx, sy); time.sleep(0.35)
    grip_ev("mousedown", sx, sy); drag_ev("dragstart", sx, sy)
    time.sleep(0.18)
    ix = sx + 2 + random.random()*1.5
    mv(ix, sy); drag_ev("drag", ix, sy)
    time.sleep(0.12)
    def ptx():
        return p.evaluate("""()=>{const e=document.querySelector('aside[aria-modal=true] div._7Sd2jx');
            if(!e)return -99;const m=(e.getAttribute('style')||'').match(/translateX\\(([-0-9.]+)px\\)/);return m?parseFloat(m[1]):0;}""")
    nseg = 3 + int(random.random()*3)
    lastx, lasty = ix, sy
    for i in range(1, nseg+1):
        # segmen 0.85..1.0 (TIDAK overshoot); segmen terakhir PAS di target
        frac = (i/nseg) * (0.9 + random.random()*0.1) if i < nseg else 1.0
        tx = sx + distance*frac
        ty = sy + _m.sin(i/nseg*_m.pi)*(random.random()*4-2)
        for j in range(11):
            t = j/10
            cxz = lastx+(tx-lastx)*t; cyz = lasty+(ty-lasty)*t
            mv(cxz, cyz); drag_ev("drag", cxz, cyz)
            time.sleep(0.01+random.random()*0.006)
        lastx, lasty = tx, ty
    # final micro-adjust — clamp biar gak lompat lewat target
    for i in range(4):
        lastx += (random.random()-0.5)*0.6
        lasty += (random.random()-0.4)*0.5
        # jaga dekat target
        if lastx > sx + distance: lastx = sx + distance
        if lastx < sx + distance - 4: lastx = sx + distance - 4
        mv(lastx, lasty); drag_ev("drag", lastx, lasty)
        time.sleep(0.15)
    # snap ke target tepat
    mv(sx + distance, sy); drag_ev("drag", sx + distance, sy)
    time.sleep(0.2)
    time.sleep(0.3)
    grip_ev("mouseup", lastx, lasty); drag_ev("dragend", lastx, lasty)
    return ptx() >= distance - 5


def detect_gap(p, rect):
    """Crop puzzle via rect, deteksi CELAH (area gelap, gap_v5) -> offset."""
    png = p.screenshot(clip={"x": rect["x"], "y": rect["y"],
                             "width": rect["w"], "height": rect["h"]})
    tmp = f"{ROOT}/shots/_cur_puzzle.png"
    open(tmp, "wb").write(png)
    try:
        from tools.gap_v5 import detect as d5
        info = d5(tmp)
        offset = info["offset"]
        gap_pct = info["hole_pct"]
    except Exception:
        offset = int(rect["w"] * 0.45); gap_pct = 45.0
    return {"offset": offset, "gap_pct": gap_pct, "img_w": rect["w"]}


def main():
    phone = (sys.argv[1] if len(sys.argv) > 1 else "").lstrip("+0")
    if phone.startswith("62"):
        phone = phone[2:]
    # channel OTP: wa (default) | sms
    CHANNEL = "wa"
    for a in sys.argv[2:]:
        if a.lower() in ("wa", "sms", "--wa", "--sms"):
            CHANNEL = a.replace("--", "").lower()
    proxy = parse_proxy(get_proxy(sys.argv[2] if len(sys.argv) > 2 else None))
    print(f"PHONE={phone} CHANNEL={CHANNEL} PROXY={proxy['server']}")

    res = {"phone": phone, "stage": "init", "ok": False}
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=False,
                               args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        c = b.new_context(user_agent=UA, locale="id-ID", proxy=proxy,
                          extra_http_headers={"Accept-Language": "id-ID,id;q=0.9,en;q=0.8"},
                          viewport={"width": 1280, "height": 900})
        c.add_cookies([{"name": "shopee_webLanguage", "value": "id",
                        "domain": ".shopee.co.id", "path": "/"}])
        p = c.new_page()
        net = []
        p.on("response", lambda r: net.append((r.status, r.url.split("/api/")[-1][:50]))
             if ("get_settings_v2" in r.url or "anti_fraud" in r.url or "send_otp" in r.url) else None)

        try:
            p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
            try:
                p.wait_for_load_state("networkidle", timeout=18000)
            except Exception:
                pass
            time.sleep(3)
            install_captcha_hook(p)
            res["stage"] = "loaded"

            # dismiss modal bahasa (kuat: sampai benar-benar hilang + input muncul)
            for _ in range(12):
                still = p.evaluate("() => /Pilih bahasa Anda/i.test(document.body.innerText||'')")
                if not still:
                    break
                clicked = False
                for sel in ["button:has-text('Bahasa Indonesia')",
                            "text=Bahasa Indonesia",
                            "div:has-text('Bahasa Indonesia')"]:
                    try:
                        loc = p.locator(sel).first
                        if loc.count() and loc.is_visible():
                            loc.click(timeout=2500); clicked = True; break
                    except Exception:
                        continue
                if not clicked:
                    try:
                        p.keyboard.press("Escape"); time.sleep(0.8)
                        p.mouse.click(10, 10)
                    except Exception:
                        pass
                time.sleep(1.5)
            # tunggu input nomor benar-benar ada
            for _ in range(10):
                n = p.evaluate("() => document.querySelectorAll('input').length")
                if n > 0:
                    break
                time.sleep(1)

            # fill + submit, lalu POLL state (pola terbukti probe_dbg)
            fr = fill_field(p, 0, phone); print("fill:", fr)
            time.sleep(1.5)
            sr = click_submit(p); print("submit:", sr)

            st = "wait"
            for _i in range(45):
                time.sleep(2)
                st = p.evaluate("""() => { const b=document.body.innerText||'';
                    if(/Geser untuk|Verifikasi untuk/i.test(b)) return 'CAPTCHA';
                    if(/Simak Ketentuan Akun/i.test(b)) return 'TOS';
                    if(/telah terjadi kesalahan|Terjadi kesalahan/i.test(b)) return 'ERROR';
                    if(/kode verifikasi|Kirim Kode/i.test(b)) return 'OTP';
                    return 'wait'; }""")
                if st == "TOS":
                    btn = p.evaluate("""() => { let f=null;
                        document.querySelectorAll('button,div,span,a').forEach(e=>{
                          const t=(e.childElementCount===0?(e.textContent||''):'').trim();
                          if(!f && /^setuju$|^saya setuju$/i.test(t)){ const r=e.getBoundingClientRect();
                            if(r.width>0&&r.height>0) f={x:r.x+r.width/2, y:r.y+r.height/2}; }}); return f; }""")
                    if btn:
                        p.mouse.click(btn["x"], btn["y"]); print("  clicked Setuju")
                if st in ("CAPTCHA", "OTP", "ERROR"):
                    break
            print("STATE:", st, "| net:", net[-4:])

            if st == "OTP":
                res["stage"] = "otp"; res["ok"] = True
                p.screenshot(path=f"{ROOT}/shots/one_{phone}_OTP.png")
                return
            if st == "CAPTCHA":
                pass
            # ==== cek OTP MODAL (captcha mungkin sudah lolos) ====
            for _o in range(4):
                om = p.evaluate("""() => { const b=document.body.innerText||'';
                    return /Kirim ke WhatsApp|akan mengirim Kode OTP/i.test(b) ? 'OTP_MODAL' : null; }""")
                if om: break
                time.sleep(1)
            if om:
                print(">>> OTP MODAL DETECTED")
                if CHANNEL == "sms":
                    # klik "Metode Lain" utk ganti ke SMS
                    mb = p.evaluate("""() => { let f=null;
                        document.querySelectorAll('button,div,span,a').forEach(e=>{
                          const t=(e.childElementCount===0?(e.textContent||''):'').trim();
                          if(!f && /^metode lain$/i.test(t)){ const r=e.getBoundingClientRect();
                            if(r.width>0) f={x:r.x+r.width/2, y:r.y+r.height/2}; }}); return f; }""")
                    if mb:
                        p.mouse.click(mb["x"], mb["y"]); print("  clicked Metode Lain")
                        time.sleep(2)
                    # pilih SMS
                    sb = p.evaluate("""() => { let f=null;
                        document.querySelectorAll('button,div,span,a,label').forEach(e=>{
                          const t=(e.childElementCount===0?(e.textContent||''):'').trim();
                          if(!f && /^sms|kirim via sms|pesan singkat/i.test(t)){ const r=e.getBoundingClientRect();
                            if(r.width>0) f={x:r.x+r.width/2, y:r.y+r.height/2}; }}); return f; }""")
                    if sb:
                        p.mouse.click(sb["x"], sb["y"]); print("  clicked SMS")
                        time.sleep(2)
                # klik tombol kirim utama
                kb = p.evaluate("""() => { let f=null;
                    document.querySelectorAll('button,div,span,a').forEach(e=>{
                      const t=(e.childElementCount===0?(e.textContent||''):'').trim();
                      if(!f && /^kirim ke whatsapp$|^kirim kode$|^kirim otp$|^kirim$/i.test(t)){ const r=e.getBoundingClientRect();
                        if(r.width>0) f={x:r.x+r.width/2, y:r.y+r.height/2}; }}); return f; }""")
                if kb:
                    p.mouse.click(kb["x"], kb["y"]); print(f"  clicked kirim ({CHANNEL})")
                    time.sleep(5)
                    p.screenshot(path=f"{ROOT}/shots/otp_sent_{phone}.png")
                    res["stage"] = "otp_sent"; res["ok"] = True; res["channel"] = CHANNEL
                    print("RESULT_OTP:", json.dumps({"phone": phone, "stage": "otp_sent", "channel": CHANNEL}, ensure_ascii=False))
                    return
            if st != "CAPTCHA":
                res["stage"] = st.lower()
                res["note"] = "no captcha"
                p.screenshot(path=f"{ROOT}/shots/one_{phone}_reject.png")
                raise SystemExit(0)
            res["stage"] = "captcha"
            # tunggu captcha SELESAI load (isi "Memuat..." hilang + canvas ada)
            for _w in range(15):
                time.sleep(1)
                loaded = p.evaluate("""() => {
                    const b = document.body.innerText||'';
                    const hasLoad = /Memuat\\.\\.\\.|Loading/i.test(b);
                    const cvs = [...document.querySelectorAll('canvas')]
                        .filter(c=>c.getBoundingClientRect().width>150);
                    return (!hasLoad && cvs.length>0);
                }""")
                if loaded:
                    break
            time.sleep(1.5)

            rect = canvas_rect(p)
            res["rect"] = rect
            if not rect:
                res["note"] = "no canvas rect"
                return
            info = detect_gap(p, rect)
            res["gap"] = info
            print("GAP:", json.dumps(info))

            # drag (multi-attempt: deteksi celah ulang tiap refresh)
            for _a in range(8):
                r2 = canvas_rect(p)
                if not r2:
                    break
                info = detect_gap(p, r2)
                off = info["offset"]
                gx = r2["x"] + 22
                gy = r2["y"] + r2["h"] + 35
                # simpan crop puzzle utk analisis
                try:
                    _tmp = f"{ROOT}/shots/so_{phone}_puz{_a}.png"
                    p.screenshot(path=_tmp, clip={"x":r2["x"],"y":r2["y"],
                                                  "width":r2["w"],"height":r2["h"]})
                except Exception:
                    pass
                print(f"  attempt {_a+1}: offset={off}px (gap_pct={info['gap_pct']})")
                # --- SadCaptcha API + precise drag (break condition translateX) ---
                try:
                    pz = p.evaluate("""()=>{const c=document.querySelector('canvas.EkGpDI');
                        return c?c.toDataURL('image/png').split(',')[1]:null;}""")
                    pc = p.evaluate("""()=>{const c=document.querySelector('canvas._0N0-Dn');
                        return c?c.toDataURL('image/png').split(',')[1]:null;}""")
                    import requests as _rq, hashlib as _hl
                    _key = os.environ.get("SADCAPTCHA_KEY","")
                    prop = None
                    if pz and pc and _key:
                        _h = _hl.md5((pz[:2000]+pc[:800]).encode()).hexdigest()[:12]
                        if _h in _PROP_CACHE:
                            prop = _PROP_CACHE[_h]
                            print(f"    [cache HIT {_h}] prop={prop}")
                        else:
                            rr = _rq.post(f"https://www.sadcaptcha.com/api/v1/puzzle?licenseKey={_key}",
                                          json={"puzzleImageB64": pz, "pieceImageB64": pc}, timeout=40)
                            if rr.status_code == 200:
                                prop = rr.json().get("slideXProportion")
                                _PROP_CACHE[_h] = prop
                                print(f"    [API {_h}] prop={prop}")
                    if prop is not None:
                        # piece range = track_w - piece_w (44) = 236 (bukan 280)
                        _wr = p.evaluate("""()=>{const t=document.querySelector('aside[aria-modal=true] div.FVDNdI');
                            const pc=document.querySelector('aside[aria-modal=true] canvas._0N0-Dn');
                            const GC=document.querySelector('aside[aria-modal=true] div.dExCsf');
                            return {tw:t?t.getBoundingClientRect().width:280,
                                    pw:pc?pc.getBoundingClientRect().width:44,
                                    gw:GC?GC.getBoundingClientRect().width:40};}""")
                        travel = _wr["tw"] - _wr["gw"]
                        dist = travel * prop
                        _b = p.evaluate("""()=>{const e=document.querySelector('aside[aria-modal=true] div._7Sd2jx');
                            if(!e)return null;const m=(e.getAttribute('style')||'').match(/translateX\\(([-0-9.]+)px\\)/);return m?parseFloat(m[1]):0;}""")
                        print(f"    SADCAPTCHA prop={prop:.3f} travel={travel:.0f} dist={dist:.1f}px piece_before={_b}")
                        # dispatch synthetic pointer events KE GRIP ELEMENT (pola ekstensi)
                        ok = synth_drag(p, dist)
                        _a2 = p.evaluate("""()=>{const e=document.querySelector('aside[aria-modal=true] div._7Sd2jx');
                            if(!e)return null;const m=(e.getAttribute('style')||'').match(/translateX\\(([-0-9.]+)px\\)/);return m?parseFloat(m[1]):0;}""")
                        print(f"    piece_after={_a2} reached={ok}")
                    else:
                        human_drag(p, gx, gy, gx + off, gy)
                except Exception as _e:
                    print("    solver err:", _e)
                    human_drag(p, gx, gy, gx + off, gy)
                time.sleep(4)
                st = p.evaluate("""() => { const b=document.body.innerText||'';
                    if(/kode verifikasi|Kode Verifikasi|Kirim Kode/i.test(b)) return 'OTP';
                    if(/Geser untuk|puzzle/i.test(b)) return 'CAPTCHA';
                    if(/Terjadi kesalahan/i.test(b)) return 'ERROR';
                    return ''; }""")
                info = detect_gap(p, canvas_rect(p)) if st == "CAPTCHA" else info
                print(f"  attempt {_a+1}: after={st}")
                if st == "":
                    # captcha hilang / loading -> tunggu & cek OTP
                    time.sleep(3)
                    st = p.evaluate("""() => { const b=document.body.innerText||'';
                        if(/kode verifikasi|Kode Verifikasi|Kirim Kode/i.test(b)) return 'OTP';
                        if(/Geser untuk/i.test(b)) return 'CAPTCHA';
                        return ''; }""")
                    print(f"    recheck: {st}")
                if st in ("OTP", "ERROR"):
                    break
            res["after"] = st
            res["ok"] = (st == "OTP")
            p.screenshot(path=f"{ROOT}/shots/one_{phone}_{st}.png")
            vc = p.evaluate("() => { const s=window.__shcap||{}; return (s.verify||[]).length; }")
            res["verify_calls"] = vc
            print("AFTER:", st, "| verify calls:", vc)
        except Exception as e:
            res["note"] = f"{e.__class__.__name__}: {e}"
        finally:
            res["net"] = net
            try:
                p.screenshot(path=f"{ROOT}/shots/one_{phone}_final.png")
            except Exception:
                pass
            b.close()
            # tulis hasil SELALU (termasuk early exit)
            print("RESULT:", json.dumps({k: v for k, v in res.items() if k != "net"}, ensure_ascii=False))
            os.makedirs(f"{ROOT}/farm_out", exist_ok=True)
            open(f"{ROOT}/farm_out/one_shot.json", "w").write(
                json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
