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
    # tunggu widget recaptcha benar2 render (max 30s)
    for i in range(30):
        fr = [f for f in p.frames if "recaptcha" in (f.url or "")]
        if fr:
            print(f"[{i}s] frames:", [f.url.split('?')[0].split('/')[-1] for f in fr]); break
        time.sleep(1)
    p.evaluate("()=>{const e=document.querySelector('.g-recaptcha'); if(e) e.scrollIntoView({block:'center'});}")
    time.sleep(5)
    print("frames now:", [f.url.split('/')[-1][:30] for f in p.frames if 'recaptcha' in (f.url or '')])
    # klik checkbox
    for f in p.frames:
        if "anchor" in (f.url or ""):
            try:
                f.locator("#recaptcha-anchor").click(timeout=8000); print("checkbox clicked")
            except Exception as e: print("cb err", str(e)[:60])
    time.sleep(6)
    for f in p.frames:
        if "bframe" in (f.url or ""):
            c = f.content()
            print("== bframe ==")
            print("BLOCKED" if ("Try again later" in c or "automated queries" in c) else "not-blocked")
            if "#recaptcha-audio-button" in c: print("audio-button present")
    p.screenshot(path="/tmp/reg_proxy2.png")
    print("shot done")
    time.sleep(2)
    b.close()
