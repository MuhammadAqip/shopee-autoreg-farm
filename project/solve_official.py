"""Shopee signup via OFFICIAL SadCaptcha client (Chrome extension auto-solve).

make_playwright_solver_context(playwright, api_key, proxy=..., user_data_dir=...)
Extension auto-detect + solve captcha di background.
"""
import sys, time, re as _re
sys.path.insert(0, '/root/shopee-farm')
from playwright.sync_api import sync_playwright
from shopee_captcha_solver import make_playwright_solver_context
from tools.signup_driver import fill_field, click_submit

PHONE  = sys.argv[1] if len(sys.argv) > 1 else "87876125616"
PORT   = sys.argv[2] if len(sys.argv) > 2 else "10003"
API_KEY = sys.argv[3] if len(sys.argv) > 3 else "f231e3e4ea6ae4a5806fcfbc68513bfd"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
PROXY = {"server": f"http://gb.vsproxy.org:{PORT}",
         "username": "8108c95881d0c4b2f18e__cr.id;sessttl.5",
         "password": "[REDACTED]"}


def state(p):
    return p.evaluate("""() => { const b=document.body.innerText||'';
        if(/kode verifikasi|Kirim Kode/i.test(b)) return 'OTP';
        if(/kirim kode otp via|Kirim ke WhatsApp/i.test(b)) return 'OTP_MODAL';
        if(/Simak Ketentuan Akun/i.test(b)) return 'TOS';
        if(/telah terjadi kesalahan|Terjadi kesalahan|Coba lagi/i.test(b)) return 'ERROR';
        if(/Geser untuk/i.test(b)) return 'CAPTCHA';
        return '?'; }""")


def main():
    with sync_playwright() as pw:
        ctx = make_playwright_solver_context(
            pw, API_KEY,
            user_data_dir="/root/shopee-farm/uc_profile",
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            user_agent=UA, locale="id-ID", proxy=PROXY,
            extra_http_headers={"Accept-Language": "id-ID,id;q=0.9,en;q=0.8"},
            viewport={"width": 1280, "height": 900})
        p = ctx.new_page()
        ctx.add_cookies([{"name": "shopee_webLanguage", "value": "id", "domain": ".shopee.co.id", "path": "/"}])
        p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
        try: p.wait_for_load_state("networkidle", timeout=18000)
        except: pass
        time.sleep(3)
        for _ in range(12):
            if not p.evaluate("()=>/Pilih bahasa Anda/i.test(document.body.innerText||'')"): break
            try:
                loc = p.locator("button:has-text('Bahasa Indonesia')").first
                if loc.count() and loc.is_visible(): loc.click(timeout=2000)
            except: pass
            time.sleep(1.5)
        for _ in range(10):
            if p.evaluate("()=>document.querySelectorAll('input').length") > 0: break
            time.sleep(1)
        fill_field(p, 0, PHONE); time.sleep(1)
        click_submit(p); time.sleep(3)
        # tunggu extension auto-solve (poll state sampai OTP / timeout)
        st = "wait"
        for i in range(65):   # ~130s (extension butuh waktu)
            time.sleep(2)
            st = state(p)
            if st == "TOS":
                btn = p.evaluate("""()=>{let f=null;document.querySelectorAll('*').forEach(e=>{const t=(e.childElementCount===0?(e.textContent||''):'').trim();if(!f&&/^setuju$/i.test(t)){const r=e.getBoundingClientRect();f={x:r.x+r.width/2,y:r.y+r.height/2};}});return f;}""")
                if btn: p.mouse.click(btn["x"], btn["y"])
            print(f"  t={i*2}s state={st}")
            if st in ("OTP", "OTP_MODAL", "ERROR"):
                break
        if st == "OTP_MODAL":
            # klik "Kirim ke WhatsApp" / "Kirim Kode"
            ok = p.evaluate("""()=>{let f=null;document.querySelectorAll('*').forEach(e=>{const t=(e.childElementCount===0?(e.textContent||''):'').trim();if(!f&&/kirim ke whatsapp|kirim kode|kirim otp/i.test(t)){const r=e.getBoundingClientRect();f={x:r.x+r.width/2,y:r.y+r.height/2,tag:e.tagName};}});return f;}""")
            print("  klik kirim:", ok)
            if ok: p.mouse.click(ok["x"], ok["y"])
            time.sleep(3)
            st = state(p)
            print("  after kirim:", st)
        safe = _re.sub(r'[^A-Za-z0-9]', '_', str(st))
        p.screenshot(path=f"/root/shopee-farm/shots/official_{PHONE}_{safe}.png")
        print("FINAL:", st)
        ctx.close()


main()
