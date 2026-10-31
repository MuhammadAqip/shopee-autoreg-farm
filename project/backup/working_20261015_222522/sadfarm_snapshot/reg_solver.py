#!/usr/bin/env python3
"""reg_solver.py — register sadcaptcha OTOMATIS penuh pakai AUDIO reCAPTCHA + Whisper.

Flow:
  1. Buka /register
  2. Isi email + password + agree terms
  3. Solve reCAPTCHA via AUDIO challenge (Whisper transcribe)
  4. Klik Register
  5. Return: cookies + status

Usage:
  reg_solver.py <email> <password> [--headful]
"""
import sys, os, time, re, json, argparse
sys.path.insert(0, "/root/sadfarm")
import sadfarm as S

MODEL = None
MODEL_PATH = "/root/whisper-models/faster-whisper-base"
AUDIO_DIR = "/tmp/rc_audio"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def get_model():
    global MODEL
    if MODEL is None:
        from faster_whisper import WhisperModel
        log("loading whisper (local)...")
        MODEL = WhisperModel(MODEL_PATH, device="cpu", compute_type="int8")
    return MODEL


NORM = {"zero":"0","one":"1","two":"2","three":"3","four":"4","five":"5","six":"6","seven":"7","eight":"8","nine":"9"}

def transcribe(path):
    m = get_model()
    # bypass library `av` (broken): decode via ffmpeg → PCM → numpy
    wav = path.rsplit(".", 1)[0] + ".wav"
    os.system(f"ffmpeg -y -i '{path}' -ar 16000 -ac 1 -c:a pcm_s16le '{wav}' -loglevel quiet 2>/dev/null")
    import wave
    import numpy as np
    with wave.open(wav, "rb") as w:
        frames = w.readframes(w.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    segs, _ = m.transcribe(audio, language="en", beam_size=1)
    return " ".join(s.text for s in segs).strip()

def clean(txt):
    txt = txt.lower()
    for w, d in NORM.items():
        txt = txt.replace(w, d)
    txt = re.sub(r"[^a-z0-9 ]", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def recaptcha_frames(page):
    anchor = bframe = None
    for f in page.frames:
        u = f.url or ""
        if "recaptcha" in u and "anchor" in u: anchor = f
        if "recaptcha" in u and "bframe" in u: bframe = f
    return anchor, bframe


def token_of(page):
    try:
        return page.evaluate("()=>{try{return document.querySelector('[name=g-recaptcha-response]').value}catch(e){return ''}}") or ""
    except Exception:
        return ""


def solve_recaptcha(page):
    # scroll biar widget render
    page.evaluate("()=>window.scrollTo(0, document.body.scrollHeight)")
    for _ in range(20):
        a, b = recaptcha_frames(page)
        if a: break
        time.sleep(1)
    a, b = recaptcha_frames(page)
    if not a:
        log("anchor frame ga muncul"); return None

    # klik checkbox awal
    for sel in ["#recaptcha-anchor", "span[role=checkbox]", ".recaptcha-checkbox"]:
        try:
            if a.locator(sel).count():
                a.locator(sel).click(timeout=6000)
                log(f"checkbox diklik ({sel})"); break
        except Exception:
            pass
    time.sleep(3)

    if token_of(page):
        log("langsung solved (no challenge)"); return token_of(page)

    for attempt in range(10):
        a, b = recaptcha_frames(page)
        if not b:
            if token_of(page): return token_of(page)
            time.sleep(2); continue
        # cek expired → re-klik checkbox
        try:
            bc = b.content()
            if "expired" in bc.lower() or "Try again later" in bc:
                log("challenge expired → re-click")
                for f in page.frames:
                    if "anchor" in (f.url or ""):
                        try: f.locator("#recaptcha-anchor").click(timeout=5000)
                        except Exception: pass
                time.sleep(3)
        except Exception:
            pass
        # klik tombol audio TIAP iterasi (kalau ada)
        try:
            if b.locator("#recaptcha-audio-button").count():
                b.locator("#recaptcha-audio-button").click(timeout=6000)
                log("→ audio mode")
        except Exception:
            pass
        # tunggu audio-source muncul (scan content, max 12s)
        src = None
        for _ in range(12):
            time.sleep(1)
            a2, b2 = recaptcha_frames(page)
            fr = b2 or b
            try:
                c = fr.content()
                m = re.search(r'id="audio-source"[^>]*src="([^"]+)"', c)
                if m:
                    src = m.group(1).replace("&amp;", "&")
                    break
            except Exception:
                pass
        # fallback: kadang audio-source ada tapi belum di src — ambil dari <audio>
        if not src:
            try:
                a2, b2 = recaptcha_frames(page)
                fr = b2 or b
                el = fr.locator("#audio-source")
                if el.count():
                    src = el.get_attribute("src", timeout=4000)
                    if src: src = src.replace("&amp;", "&")
            except Exception:
                pass
        if not src:
            log("audio-source ga muncul"); time.sleep(2); continue

        os.makedirs(AUDIO_DIR, exist_ok=True)
        path = f"{AUDIO_DIR}/a{attempt}.mp3"
        try:
            import requests
            open(path, "wb").write(requests.get(src, timeout=30).content)
        except Exception as e:
            log(f"dl err {e}"); continue

        ans = clean(transcribe(path))
        log(f"hear: '{ans}'")
        if not ans:
            time.sleep(2); continue
        a3, b3 = recaptcha_frames(page)
        fr = b3 or b
        try:
            fr.fill("#audio-response", ans)
            time.sleep(1)
            fr.click("#recaptcha-verify-button")
        except Exception as e:
            log(f"submit err {e}")
        time.sleep(4)
        t = token_of(page)
        if t and len(t) > 40:
            log(f"✅ token: {t[:40]}...")
            return t
        log(f"attempt {attempt+1} gagal")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("email")
    ap.add_argument("password")
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--proxy", default=os.environ.get("PROXY", ""))
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright
    pxy = None
    if args.proxy:
        m = re.match(r"http://([^:]+):([^@]+)@([^:]+):(\d+)", args.proxy)
        if m:
            pxy = {"server": f"http://{m.group(3)}:{m.group(4)}",
                   "username": m.group(1), "password": m.group(2)}
            log(f"proxy: {m.group(3)}:{m.group(4)}")
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=not args.headful,
                               args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(proxy=pxy, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        p = ctx.new_page()
        p.goto("https://www.sadcaptcha.com/register", wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)
        # tunggu widget recaptcha render
        for _ in range(30):
            if any("recaptcha" in (f.url or "") for f in p.frames):
                break
            time.sleep(1)
        p.evaluate("()=>{const e=document.querySelector('.g-recaptcha'); if(e) e.scrollIntoView({block:'center'});}")
        time.sleep(3)

        # isi form
        p.fill("input[name=username]", args.email)
        p.fill("input[name=password1]", args.password)
        p.fill("input[name=password2]", args.password)
        try: p.check("#agreeToTerms")
        except Exception: pass
        log(f"form diisi: {args.email}")

        tok = solve_recaptcha(p)
        if not tok:
            p.screenshot(path="/tmp/reg_fail.png")
            log("FAIL solve → /tmp/reg_fail.png")
            b.close(); return

        # submit
        p.click("button[type=submit]")
        time.sleep(5)
        url = p.url
        log(f"after submit: {url}")
        # cookies
        cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        open("/root/sadfarm/.reg_cookies.json", "w").write(json.dumps(cookies))
        log(f"cookies: {list(cookies.keys())}")
        p.screenshot(path="/tmp/reg_done.png")
        b.close()

        # lanjut verify+login+harvest via requests
        import requests
        s = requests.Session()
        s.headers.update({"User-Agent": S.UA})
        for k, v in cookies.items():
            s.cookies.set(k, v, domain="www.sadcaptcha.com")
        link = S.wait_activation(args.email, timeout=180)
        if link:
            log(f"activate: {link[:70]}")
            av = s.get(link, allow_redirects=True, timeout=30)
            log(f"activate -> {av.status_code}")
        # fresh login (session baru, cookie fresh)
        s2 = requests.Session()
        s2.headers.update({"User-Agent": S.UA})
        rl = s2.post(f"{S.SAD}/login", data={"username": args.email, "password": args.password},
                     allow_redirects=False, timeout=30)
        log(f"login: {rl.status_code} {rl.headers.get('Location','')}")
        dh = s2.get(f"{S.SAD}/dashboard", timeout=30).text
        keys = re.findall(r"[a-f0-9]{32}", dh)
        apikey = keys[0] if keys else ""
        cr = None
        if apikey:
            try: cr = requests.get(f"{S.SAD}/api/v1/license/credits", params={"licenseKey": apikey}, timeout=15).json().get("credits")
            except Exception: pass
        if apikey:
            acc = {"ok": True, "email": args.email, "password": args.password,
                   "apikey": apikey, "credits": cr, "created": time.strftime("%Y-%m-%d %H:%M:%S")}
            S.save_account(acc)
            log(f"✅ SUCCESS apikey={apikey} credits={cr}")
            print(json.dumps(acc, indent=1))
        else:
            log("gagal ambil apikey")


if __name__ == "__main__":
    main()
