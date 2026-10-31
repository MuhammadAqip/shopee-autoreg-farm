import time, re, sys
from playwright.sync_api import sync_playwright

PROXY = sys.argv[1] if len(sys.argv) > 1 else ""

pm = re.match(r"http://([^:]+):([^@]+)@([^:]+):(\d+)", PROXY) if PROXY else None

with sync_playwright() as pw:
    launch = dict(headless=False, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    pxy = None
    if pm:
        pxy = {"server": f"http://{pm.group(3)}:{pm.group(4)}", "username": pm.group(1), "password": pm.group(2)}
    b = pw.chromium.launch(**launch)
    ctx = b.new_context(proxy=pxy, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    p = ctx.new_page()
    # cek IP
    try:
        p.goto("https://httpbin.org/ip", wait_until="domcontentloaded", timeout=40000)
        time.sleep(2)
        print("IP:", p.evaluate("()=>document.body.innerText")[:120].replace("\n", " "))
    except Exception as e:
        print("ip check err", e)
    p.goto("https://www.sadcaptcha.com/register", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    p.evaluate("()=>window.scrollTo(0,document.body.scrollHeight)")
    time.sleep(3)
    for f in p.frames:
        if "anchor" in (f.url or ""):
            try:
                f.locator("#recaptcha-anchor").click(timeout=6000); print("checkbox clicked")
            except Exception as e: print("cb err", str(e)[:50])
    time.sleep(5)
    # cek status challenge
    for f in p.frames:
        if "bframe" in (f.url or ""):
            c = f.content()
            print("== bframe state ==")
            if "Try again later" in c or "automated queries" in c:
                print("BLOCKED (try again later)")
            if "#audio-source" in c or 'id="audio-source"' in c:
                print("AUDIO available")
            if "recaptcha-audio-button" in c:
                print("has audio-button")
            m = re.search(r'id="audio-source"[^>]*src="([^"]+)"', c)
            if m: print("audio src:", m.group(1)[:100])
    p.screenshot(path="/tmp/reg_proxy.png")
    print("shot /tmp/reg_proxy.png")
    time.sleep(2)
    b.close()
