#!/usr/bin/env python3
"""recap_audio.py — solve reCAPTCHA v2 pakai AUDIO challenge + Whisper.

Flow:
  1. Playwright buka halaman target (register)
  2. klik checkbox reCAPTCHA
  3. kalau muncul image challenge → switch ke AUDIO
  4. download audio (mp3) → transcribe (faster-whisper)
  5. isi jawaban + verify
  6. ambil token dari g-recaptcha-response

Usage:
  recap_audio.py <url> [--sitekey KEY] [--headful]
"""
import sys, os, time, re, json, argparse

MODEL = None


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def get_model():
    global MODEL
    if MODEL is None:
        from faster_whisper import WhisperModel
        log("loading whisper model (base)...")
        MODEL = WhisperModel("base", device="cpu", compute_type="int8")
    return MODEL


def transcribe(path):
    m = get_model()
    segs, info = m.transcribe(path, language="en", beam_size=1)
    return " ".join(s.text for s in segs).strip()


NORM = {"zero":"0","one":"1","two":"2","three":"3","four":"4","five":"5",
        "six":"6","seven":"7","eight":"8","nine":"9"}


def clean_answer(txt):
    txt = txt.lower()
    for w, d in NORM.items():
        txt = txt.replace(w, d)
    txt = re.sub(r"[^a-z0-9 ]", " ", txt)
    return txt.strip()


def solve_audio(page, audio_dir="/tmp/rc_audio"):
    """di dalam frame reCAPTCHA: switch ke audio, download, transcribe, jawab."""
    os.makedirs(audio_dir, exist_ok=True)

    def find_frame():
        for f in page.frames:
            if "recaptcha" in (f.url or "") and "anchor" in (f.url or ""):
                return f
        for f in page.frames:
            if "recaptcha" in (f.url or ""):
                return f
        return None

    fr = find_frame()
    if not fr:
        log("ga nemu recaptcha frame")
        return None

    # klik checkbox
    try:
        cb = fr.locator("#recaptcha-anchor")
        if cb.count():
            cb.click(timeout=8000)
            log("checkbox diklik")
    except Exception as e:
        log(f"klik checkbox: {e}")

    time.sleep(3)

    # frame challenge (bframe)
    bf = None
    for f in page.frames:
        if "recaptcha" in (f.url or "") and "bframe" in (f.url or ""):
            bf = f; break
    if not bf:
        # mungkin udah solved langsung
        tok = page.evaluate("()=>{try{return document.querySelector('[name=g-recaptcha-response]').value}catch(e){return ''}}")
        if tok:
            return tok
        log("ga nemu bframe challenge")
        return None

    for attempt in range(6):
        # klik tombol audio
        try:
            ab = bf.locator("#recaptcha-audio-button")
            if ab.count():
                ab.click(timeout=8000)
                log("switch ke audio")
        except Exception:
            pass
        time.sleep(2)

        # ambil link audio
        try:
            dl = bf.locator("#audio-source")
            src = dl.get_attribute("src", timeout=8000)
        except Exception:
            src = None
        if not src:
            log("ga ada audio-source, mungkin image challenge")
            time.sleep(2); continue

        log(f"audio: {src[:80]}...")
        path = f"{audio_dir}/a{attempt}.mp3"
        try:
            import requests
            r = requests.get(src, timeout=30)
            open(path, "wb").write(r.content)
        except Exception as e:
            log(f"download err: {e}"); continue

        ans = clean_answer(transcribe(path))
        log(f"transcribe: '{ans}'")
        try:
            bf.fill("#audio-response", ans)
            time.sleep(1)
            bf.click("#recaptcha-verify-button")
        except Exception as e:
            log(f"submit err: {e}")

        time.sleep(4)
        tok = page.evaluate("()=>{try{return document.querySelector('[name=g-recaptcha-response]').value}catch(e){return ''}}")
        if tok and len(tok) > 40:
            log(f"✅ TOKEN = {tok[:40]}...")
            return tok
        log(f"attempt {attempt+1} gagal, retry...")

    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=not args.headful,
                               args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"))
        p = ctx.new_page()
        p.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        tok = solve_audio(p)
        if tok:
            print("TOKEN:", tok)
            open("/root/sadfarm/.token_input", "w").write(tok)
        else:
            print("FAIL solve audio")
        b.close()


if __name__ == "__main__":
    main()
