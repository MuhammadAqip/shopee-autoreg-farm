#!/usr/bin/env python3
"""Hook runtime CryptoJS AES + RSA di Shopee captcha bundle.

Tujuan: tangkap (aesKey, plaintext, ciphertext) supaya bisa reverse full-API.
Inject sebelum bundle load; override prototype AES.encrypt + jsbn RSA D(t).

Output: window.__AES_LOG = [{key_hex, iv_hex, plaintext, ciphertext}]
"""
import sys, json, time, os

sys.path.insert(0, "/root/shopee-farm")
from playwright.sync_api import sync_playwright

HOOK = r"""
(() => {
  window.__AES_LOG = [];
  window.__RSA_LOG = [];
  // Patch di level low: intercept CryptoJS AES encrypt via Function.prototype
  // Strategi: setelah bundle load, cari objek AES dgn marker _doReset & createEncryptor
  function findAES() {
    // CryptoJS AES punya property keySize, _doReset, encrypt
    // Kita scan window + modul internal tdk bisa; jadi hook String output format 'Salted__'
  }
  // Trick: override btoa/atob tdk cukup. Hook Function yang return 'Salted__'
  // Cara paling reliable: monkey-patch Object.defineProperty utk module.exports? tdk.
  // Fallback: hook global crypto.getRandomValues utk KETAHUI aesKey random!
  const origGetRandom = (window.crypto && window.crypto.getRandomValues) ? window.crypto.getRandomValues.bind(window.crypto) : null;
  if (origGetRandom) {
    window.crypto.getRandomValues = function(arr) {
      const r = origGetRandom(arr);
      try {
        if (arr && arr.length === 16) {
          window.__AES_LOG.push({ev: 'getRandom16', hex: Array.from(arr).map(b=>b.toString(16).padStart(2,'0')).join('')});
        }
      } catch(e){}
      return r;
    };
  }
})();
"""

def main():
    url = "https://shopee.co.id/buyer/signup"
    proxy = sys.argv[1] if len(sys.argv) > 1 else None
    phone = sys.argv[2] if len(sys.argv) > 2 else "88986236822"

    with sync_playwright() as p:
        launch = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if proxy:
            launch["proxy"] = {"server": proxy}
        b = p.chromium.launch(**launch)
        ctx = b.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        ctx.add_cookies([{"name": "shopee_webLanguage", "value": "id", "domain": ".shopee.co.id", "path": "/"}])
        page = ctx.new_page()
        page.add_init_script(HOOK)
        # tangkap response captcha generate/verify
        caps = {"gen": [], "ver": []}
        def on_resp(r):
            u = r.url
            if "captcha/generate" in u:
                try: caps["gen"].append({"url": u, "req": r.request.post_data, "resp": r.text()[:200]})
                except Exception: pass
            elif "verify" in u:
                try: caps["ver"].append({"url": u, "req": r.request.post_data, "resp": r.text()[:200]})
                except Exception: pass
        page.on("response", on_resp)
        page.goto(url, wait_until="commit", timeout=90000)
        # tunggu SPA render (domcontentloaded sering ga keluar di Shopee)
        try:
            page.wait_for_selector("input", timeout=45000)
        except Exception:
            pass
        time.sleep(8)
        # isi nomor + submit untuk trigger captcha
        try:
            page.fill("input[type=tel], input[name=phone], input[type=text]", phone.split("0",1)[-1] if phone.startswith("0") else phone, timeout=8000)
        except Exception:
            try:
                page.fill("input", phone, timeout=5000)
            except Exception: pass
        time.sleep(1)
        for lab in ["BERIKUTNYA", "Berikutnya", "Lanjut"]:
            try:
                page.click(f"button:has-text('{lab}')", timeout=2500); break
            except Exception: continue
        time.sleep(6)
        # tunggu captcha muncul lalu ambil log
        log = page.evaluate("()=>window.__AES_LOG||[]")
        print("AES_LOG entries:", len(log))
        for e in log[:20]:
            print(" ", e)
        print("captured generate:", len(caps["gen"]), "verify:", len(caps["ver"]))
        for g in caps["gen"][:3]:
            print("  GEN req len:", len(g["req"] or ""))
        time.sleep(2)
        b.close()

if __name__ == "__main__":
    main()
