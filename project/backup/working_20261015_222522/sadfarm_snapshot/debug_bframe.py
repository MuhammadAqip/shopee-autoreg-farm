import time, re
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    p = ctx.new_page()
    p.goto("https://www.sadcaptcha.com/register", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    p.evaluate("()=>window.scrollTo(0,document.body.scrollHeight)")
    time.sleep(3)
    for f in p.frames:
        if "anchor" in (f.url or ""):
            try:
                f.locator("#recaptcha-anchor").click(timeout=6000)
                print("checkbox clicked")
            except Exception as e:
                print("cb err", e)
    time.sleep(5)
    print("=== frames ===")
    for f in p.frames:
        print(" ", (f.url or "")[:90])
    for f in p.frames:
        if "bframe" in (f.url or ""):
            print("=== BFRAME CONTENT (first 1500) ===")
            try:
                print(f.content()[:1500])
            except Exception as e:
                print("err", e)
    p.screenshot(path="/tmp/bframe.png")
    print("shot /tmp/bframe.png")
    # klik audio
    for f in p.frames:
        if "bframe" in (f.url or ""):
            for sel in ["#recaptcha-audio-button", ".rc-button-audio", "button[title*='audio' i]"]:
                try:
                    if f.locator(sel).count():
                        f.locator(sel).click(timeout=6000)
                        print("audio clicked via", sel)
                        break
                except Exception as e:
                    print(sel, "err", str(e)[:60])
    time.sleep(5)
    for f in p.frames:
        if "bframe" in (f.url or ""):
            c = f.content()
            m = re.search(r'id="audio-source"[^>]*src="([^"]+)"', c)
            print("audio src:", (m.group(1)[:120] if m else "NOT FOUND"))
            print("has audio-response:", "#audio-response" in c)
    p.screenshot(path="/tmp/bframe_audio.png")
    print("shot /tmp/bframe_audio.png")
    time.sleep(2)
    b.close()
