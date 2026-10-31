#!/usr/bin/env python3
"""Hook fungsi RSA encrypt (D) di bundle Shopee captcha.

Intercept input plaintext SEBELUM dienkripsi RSA + log output.
Jalankan berdampingan dengan signup flow → nangkep plaintext semua payload captcha.
"""
import sys, time, json, re

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("need playwright"); sys.exit(1)

phone = (sys.argv[1] if len(sys.argv) > 1 else "").lstrip("+0")
px = sys.argv[2] if len(sys.argv) > 2 else ""
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Hook: cari jsencrypt RSAKey.prototype.encrypt / setPublic
HOOK_JS = r"""
() => {
  window.__RSA_LOG = [];
  // hook JSEencrypt if present
  const tryHook = (obj, name) => {
    if (obj && obj.prototype && typeof obj.prototype[name] === 'function') {
      const orig = obj.prototype[name];
      obj.prototype[name] = function(...args) {
        const res = orig.apply(this, args);
        try {
          window.__RSA_LOG.push({fn:name, input:args.map(a=>typeof a==='string'?a.slice(0,500):String(a)), out:(typeof res==='string'?res.slice(0,80):String(res))});
        } catch(e){}
        return res;
      };
      return true;
    }
    return false;
  };
  tryHook(window.JSEncrypt, 'encrypt');
  tryHook(window.RSAKey, 'encrypt');
  // generic: patch WebCrypto
  if (window.crypto && window.crypto.subtle) {
    const oe = window.crypto.subtle.encrypt;
    window.crypto.subtle.encrypt = function(algo, key, data){
      try {
        const dv = data instanceof ArrayBuffer ? new Uint8Array(data) : null;
        window.__RSA_LOG.push({fn:'subtle.encrypt', input: dv?Array.from(dv.slice(0,200)).join(','):String(data).slice(0,200)});
      } catch(e){}
      return oe.apply(this, arguments);
    };
  }
  return Object.keys(window).filter(k=>/rsa|jsencrypt|encrypt/i.test(k));
}
"""

if not px:
    print("usage: hook_crypto.py <phone> <proxy_url>"); sys.exit(1)
pm = re.match(r"http://([^:]+):([^@]+)@([^:]+):(\d+)", px)
pxy = {"server": f"http://{pm.group(3)}:{pm.group(4)}",
       "username": pm.group(1), "password": pm.group(2)}

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False,
                           args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    c = b.new_context(user_agent=UA, locale="id-ID", proxy=pxy,
                      viewport={"width": 1280, "height": 900})
    c.add_cookies([{"name": "shopee_webLanguage", "value": "id",
                    "domain": ".shopee.co.id", "path": "/"}])
    p = c.new_page()
    # inject hook sebelum load
    p.add_init_script("window.__RSA_LOG=[];")
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
    time.sleep(4)
    keys = p.evaluate(HOOK_JS)
    print("hooked candidates:", keys)

    # trigger captcha flow
    for _ in range(40):
        t = p.evaluate("()=>document.body.innerText||''")
        if "Pilih bahasa" not in t and p.evaluate("()=>document.querySelectorAll('input').length")>0:
            break
        try: p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=1500, force=True)
        except Exception: pass
        time.sleep(1.2)

    try:
        p.locator("input").first.fill(phone)
        time.sleep(1)
        p.locator("button:has-text('BERIKUTNYA')").first.click(timeout=3000)
    except Exception as e:
        print("submit fail:", e)

    # tunggu captcha, lalu dump log tiap 3 detik
    for i in range(20):
        time.sleep(3)
        log = p.evaluate("()=>window.__RSA_LOG||[]")
        if log:
            for entry in log:
                print("RSA CALL:", json.dumps(entry)[:400])
            p.evaluate("()=>window.__RSA_LOG=[]")
        st = p.evaluate("()=>{const b=document.body.innerText||'';return /Geser|puzzle|Memuat/i.test(b)?'CAPTCHA':'?'}")
        if st == '?': break
    p.screenshot(path="/root/shopee-farm/shots/hook_crypto_final.png")
    print("DONE")
    b.close()
