import time, re, sys
from playwright.sync_api import sync_playwright

PROXY = sys.argv[1] if len(sys.argv) > 1 else ""
pm = re.match(r"http://([^:]+):([^@]+)@([^:]+):(\d+)", PROXY) if PROXY else None

with sync_playwright() as pw:
    pxy = {"server": f"http://{pm.group(3)}:{pm.group(4)}", "username": pm.group(1), "password": pm.group(2)} if pm else None
    b = pw.chromium.launch(headless=False, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(proxy=pxy, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    p = ctx.new_page()
    p.goto("https://www.sadcaptcha.com/register", wait_until="domcontentloaded", timeout=60000)
    for _ in range(30):
        if any("recaptcha" in (f.url or "") for f in p.frames): break
        time.sleep(1)
    p.evaluate("()=>{const e=document.querySelector('.g-recaptcha'); if(e) e.scrollIntoView({block:'center'});}")
    time.sleep(4)
    for f in p.frames:
        if "anchor" in (f.url or ""):
            try: f.locator("#recaptcha-anchor").click(timeout=8000); print("cb clicked")
            except Exception as e: print("cb err", str(e)[:50])
    time.sleep(6)
    # cari bframe + dump SEMUA selector penting
    for f in p.frames:
        if "bframe" in (f.url or ""):
            print("== BFRAME ==")
            c = f.content()
            print("len:", len(c))
            print("blocked:", ("Try again later" in c or "automated queries" in c))
            print("has audio-button id:", "recaptcha-audio-button" in c)
            print("has audio-source id:", 'id="audio-source"' in c or "#audio-source" in c)
            print("has audio-response:", "audio-response" in c)
            # cari semua id= di bframe
            ids = re.findall(r'id="([^"]+)"', c)
            print("ids:", ids[:40])
            m = re.search(r'id="audio-source"[^>]*src="([^"]+)"', c)
            print("audio src:", (m.group(1)[:120] if m else "NONE"))
    p.screenshot(path="/tmp/bf3.png")
    # klik audio
    for f in p.frames:
        if "bframe" in (f.url or ""):
            try:
                f.locator("#recaptcha-audio-button").click(timeout=8000); print("audio btn clicked")
            except Exception as e: print("audio click err", str(e)[:60])
    time.sleep(7)
    for f in p.frames:
        if "bframe" in (f.url or ""):
            c = f.content()
            print("== AFTER AUDIO ==")
            print("blocked:", ("Try again later" in c or "automated queries" in c))
            ids = re.findall(r'id="([^"]+)"', c)
            print("ids:", ids[:40])
            # cari audio element apapun
            for pat in [r'<audio[^>]*>', r'id="[^"]*audio[^"]*"[^>]*', r'src="https://[^"]*\.mp3[^"]*"']:
                mm = re.findall(pat, c, re.I)
                if mm: print("match", pat[:20], ":", mm[:3])
    p.screenshot(path="/tmp/bf3_audio.png")
    print("shots done")
    time.sleep(2)
    b.close()
