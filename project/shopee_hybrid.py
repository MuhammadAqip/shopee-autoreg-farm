#!/usr/bin/env python3
"""Shopee signup — HYBRID runner: maximize API, minimize browser.

Strategi:
  - 1x browser warmup: buka signup, isi nomor, ambil COOKIES + device fingerprint + SAP tokens
  - Semua endpoint plaintext (get_settings_v2, get_config) via API murni
  - Browser HANYA dipakai untuk: (a) trigger captcha render, (b) geometry drag
  - Sisa (OTP fill, password, daftar) via API atau 1 halaman yang sama

Kenapa hybrid & bukan full-API:
  Shopee captcha payload = AES-256(random key/req) + key di-RSA + SAP headers
  (x-sap-ri/x-sap-sec dari sz-sdk native). Tak bisa direplikasi offline.

Karakter khas browser: 1 halaman hidup sepanjang sesi (bukan buka-tutup).
"""
import sys, os, time, json, random, re

sys.path.insert(0, "/root/shopee-farm")
from playwright.sync_api import sync_playwright

BASE = "https://shopee.co.id"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
STATUS = "/root/shopee-farm/.signup_status"
OTPF = "/root/shopee-farm/.otp_input"
PWF = "/root/shopee-farm/.pw_input"
CAPS = "/root/shopee-farm/captures"


def log(m):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {m}"
    print(line, flush=True)
    with open(STATUS, "w") as f:
        f.write(line)


def _mouse_click_text(page, labels):
    """Klik tombol via bounding-box + mouse (tidak nunggu navigasi → anti-hang)."""
    pat = "|".join(re.escape(l) for l in labels)
    tgt = page.evaluate("""(pat)=>{let f=null;const re=new RegExp('^('+pat+')$','i');
        document.querySelectorAll('button,div,span,a').forEach(e=>{
        const t=(e.childElementCount===0?(e.textContent||''):'').trim();
        const r=e.getBoundingClientRect();
        if(re.test(t)&&r.width>0&&r.height>0&&r.y>=120){
          const sc=(r.width>200?1000:0)+r.y;
          if(!f||sc>f.sc)f={x:r.x+r.width/2,y:r.y+r.height/2,t,sc};}});return f;}""", pat)
    if tgt:
        page.mouse.move(tgt["x"], tgt["y"]); time.sleep(0.12)
        page.mouse.down(); time.sleep(0.08); page.mouse.up()
        return tgt
    return None


def state(page):
    # pakai locator.inner_text (punya timeout) supaya tidak deadlock saat page navigating
    try:
        txt = page.locator("body").inner_text(timeout=5000)
    except Exception:
        return "?"
    if re.search(r"Pendaftaran berhasil|Berhasil membuat akun", txt, re.I): return "SUCCESS"
    if re.search(r"Masukkan Kode OTP|Kode OTP telah dikirim|kirim ulang|Kode OTP Salah", txt, re.I): return "OTP"
    if re.search(r"kirim kode otp via|Kirim ke WhatsApp", txt, re.I): return "OTP_MODAL"
    if re.search(r"Simak Ketentuan Akun", txt, re.I): return "TOS"
    if re.search(r"Atur Password Kamu|Buat password|Penuhi persyaratan sandi", txt, re.I): return "PASSWORD"
    if re.search(r"telah terjadi kesalahan|Terjadi kesalahan|Coba Lagi", txt, re.I): return "ERROR"
    if re.search(r"Geser untuk|Verifikasi untuk|Memuat", txt, re.I): return "CAPTCHA"
    return "?"


def main():
    phone = sys.argv[1]
    key = sys.argv[2]
    proxy = sys.argv[3] if len(sys.argv) > 3 else None
    num = phone[2:] if phone.startswith("62") else phone
    num = num[1:] if num.startswith("0") else num

    # parse proxy → {server, username, password} (Chromium butuh auth terpisah,
    # inline user:pass@ gagal 407 karena ';' di password)
    proxy_cfg = None
    if proxy:
        m = re.match(r"http://([^:]+):([^@]+)@(.+)", proxy)
        if m:
            proxy_cfg = {"server": f"http://{m.group(3)}",
                         "username": m.group(1), "password": m.group(2)}
        else:
            proxy_cfg = {"server": proxy}

    os.makedirs(CAPS, exist_ok=True)
    for f in (STATUS, OTPF, PWF):
        try: os.remove(f)
        except Exception: pass

    with sync_playwright() as p:
        launch = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"]}
        if proxy_cfg:
            launch["proxy"] = proxy_cfg
        b = p.chromium.launch(**launch)
        ctx = b.new_context(user_agent=UA, viewport={"width": 1280, "height": 900},
                            locale="id-ID", timezone_id="Asia/Jakarta")
        ctx.add_cookies([{"name": "shopee_webLanguage", "value": "id",
                          "domain": ".shopee.co.id", "path": "/"}])
        page = ctx.new_page()
        page.set_default_timeout(8000)
        page.set_default_navigation_timeout(30000)
        # timeout keras pada semua evaluate supaya bridge tidak deadlock
        page.add_init_script("window.__t0=Date.now();")

        # --- capture network untuk reverse + debug ---
        caps = {"requests": [], "rsa_log": []}
        def on_resp(r):
            try:
                u = r.url
                if "/api/v4/" not in u:
                    return
                post = None
                try: post = r.request.post_data
                except Exception: pass
                body = None
                try: body = r.text()
                except Exception: pass
                caps["requests"].append({
                    "t": round(time.time(), 3), "method": r.request.method, "url": u,
                    "status": r.status, "req_headers": dict(r.request.headers),
                    "post": (post or "")[:6000], "body": (body or "")[:6000],
                })
            except Exception:
                pass
        page.on("response", on_resp)

        log(f"START phone={num}")
        # Shopee SPA: 'commit' (jangan 'load' — resource ga pernah selesai). Poll selector.
        try:
            page.goto(f"{BASE}/buyer/signup", wait_until="commit", timeout=45000)
        except Exception:
            pass
        for _ in range(25):
            try:
                n = page.evaluate("()=>document.body?document.body.querySelectorAll('input').length:0")
                if n > 0: break
            except Exception:
                pass
            time.sleep(2)
        time.sleep(3)

        # dismiss language modal (loop sampai hilang)
        for _ in range(6):
            try:
                el = page.query_selector("text=Pilih Bahasa")
                if el:
                    try: page.click("text=Bahasa Indonesia", timeout=2500)
                    except Exception:
                        try: page.click("button:has-text('Bahasa')", timeout=2000)
                        except Exception: pass
                    time.sleep(1.5)
                else:
                    break
            except Exception:
                break

        # isi nomor
        page.set_default_timeout(8000)
        filled = False
        for sel in ["input[type=tel]", "input[name=phone]", "input[type=text]", "input"]:
            try:
                page.fill(sel, num, timeout=4000); filled = True; break
            except Exception: continue
        log(f"fill phone: {filled}")
        time.sleep(0.6)

        # submit BERIKUTNYA
        log("clicking BERIKUTNYA...")
        _mouse_click_text(page, ["BERIKUTNYA", "Berikutnya", "Lanjut"])
        log("clicked BERIKUTNYA")
        time.sleep(3)

        # TOS
        try: st = state(page)
        except Exception: st = "?"
        log(f"pre-captcha state: {st}")
        if st == "TOS":
            _mouse_click_text(page, ["Setuju", "SETUJU", "Saya Setuju"])
            time.sleep(3)
            log(f"after TOS: {state(page)}")

        # loop sampai OTP
        max_attempt = 8
        deadline = time.time() + 420
        while time.time() < deadline:
            try: st = state(page)
            except Exception: st = "?"
            if st in ("OTP", "OTP_MODAL", "PASSWORD", "SUCCESS"):
                break
            if st == "CAPTCHA":
                for attempt in range(max_attempt):
                    log(f"captcha attempt {attempt+1}")
                    try:
                        from solve_captcha import solve  # type: ignore
                        res = solve(page, key)
                        log(f"  -> {res}")
                    except Exception as e:
                        log(f"  -> ERR {str(e)[:80]}")
                    time.sleep(2)
                    try: st = state(page)
                    except Exception: st = "?"
                    if st != "CAPTCHA":
                        break
                if st not in ("OTP", "OTP_MODAL", "PASSWORD", "SUCCESS"):
                    log("captcha loop habis, retry refresh")
                    page.reload(wait_until="commit", timeout=30000)
                    time.sleep(6)
                    continue
            time.sleep(2)

        try: fin = state(page)
        except Exception: fin = "?"
        log(f"STATE={fin}")

        # dump capture + cookies
        ts = int(time.time())
        with open(f"{CAPS}/hybrid_{num}_{ts}.json", "w") as f:
            json.dump(caps, f)
        log(f"CAPTURE hybrid_{num}_{ts}.json reqs={len(caps['requests'])}")

        # --- OTP / password handling (hold session) ---
        if state(page) in ("OTP", "OTP_MODAL"):
            log("WAITING_OTP")
            code = wait_file(OTPF, 300)
            if code:
                log(f"OTP received: {code}")
                fill_otp(page, code)
                time.sleep(1)
                press_btn(page, r"lanjut|verifikasi|confirm|kirim")
                time.sleep(3)
                pw = read_file(PWF) or "PASS_REDACTED"
                pw = norm_pw(pw)
                fill_pw(page, pw)
                time.sleep(1)
                click_daftar(page)
                time.sleep(8)
                log(f"STATE final: {state(page)}")
                page.screenshot(path=f"/root/shopee-farm/shots/hybrid_{num}_final.png")

        b.close()


def wait_file(path, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if os.path.exists(path):
            v = open(path).read().strip()
            if v: return v
        time.sleep(3)
    return None


def read_file(path):
    try: return open(path).read().strip()
    except Exception: return None


def norm_pw(pw):
    pw = pw or "PASS_REDACTED"
    if not any(c.isupper() for c in pw):
        pw = pw[0].upper() + pw[1:]
    return pw


def fill_otp(page, code):
    code = "".join(c for c in code if c.isdigit())
    boxes = []
    for _ in range(10):
        boxes = page.evaluate("""()=>{const o=[];document.querySelectorAll('input').forEach(i=>{
            const r=i.getBoundingClientRect();if(r.width>0&&r.height>0&&r.width<70)o.push({x:r.x+r.width/2,y:r.y+r.height/2});});
            return o.slice(0,6);}""")
        if len(boxes) >= 6: break
        time.sleep(0.5)
    if len(boxes) >= 6:
        page.mouse.click(boxes[0]["x"], boxes[0]["y"]); time.sleep(0.2)
        page.keyboard.type(code, delay=90)
    else:
        page.keyboard.type(code, delay=90)


def fill_pw(page, pw):
    r = page.evaluate("""()=>{let f=null;document.querySelectorAll('input').forEach(i=>{
        if(i.type==='password'||i.placeholder&&/kata sandi|password/i.test(i.placeholder)){
        const b=i.getBoundingClientRect();if(b.width>0)f={x:b.x+b.width/2,y:b.y+b.height/2};}});return f;}""")
    if r:
        page.mouse.click(r["x"], r["y"]); time.sleep(0.2)
        page.keyboard.type(pw, delay=70)


def press_btn(page, labels):
    tgt = page.evaluate("""(pat)=>{let f=null;const re=new RegExp('^('+pat+')$','i');
        document.querySelectorAll('button,div,span').forEach(e=>{
        const t=(e.childElementCount===0?(e.textContent||''):'').trim();
        const r=e.getBoundingClientRect();
        if(re.test(t)&&r.width>0&&r.height>0&&r.y>=120){
          const sc=(r.width>200?1000:0)+r.y;
          if(!f||sc>f.sc)f={x:r.x+r.width/2,y:r.y+r.height/2,t,sc};}});return f;}""", labels)
    if tgt:
        page.mouse.move(tgt["x"], tgt["y"]); time.sleep(0.12)
        page.mouse.down(); time.sleep(0.08); page.mouse.up()
    return tgt


def click_daftar(page):
    return press_btn(page, r"daftar|daf tar|register|buat akun")


if __name__ == "__main__":
    main()
