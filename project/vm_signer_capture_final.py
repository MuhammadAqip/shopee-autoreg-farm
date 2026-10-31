#!/usr/bin/env python3
"""vm_signer_capture_final.py — drive FULL signup → trigger signer → capture.

Tujuan 100%:
  1. Hook eval (y) → capture ALL generated JS (termasuk signer)
  2. Hook crypto + fetch → capture x-sap-sec output
  3. Drive sampai stage "kirim OTP" (di situ signer fire)
  4. Simpan: generated source + header sample

Run sampai signer menghasilkan x-sap-sec.
"""
import sys, os, time, json
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285616667775"
SECONDS = 120
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/vm_signer_final.json"
SRC = f"{ROOT}/sdk/worker_scripts/bile.com_shopee_shopee-pcmall-live-sg_assets_sfu-stable.c3d38f8e0e81e513.2023.js.js"
FRAG = "sfu-stable.c3d38f8e0e81e513.2023.js"

def patch(source):
    # hook eval + capture headers via fetch wrap
    hook = ("(function(){"
            "var _e=window.eval;"
            "var _f=window.fetch;"
            "self.__JIT=self.__JIT||[]; self.__HDR=self.__HDR||[];"
            "window.eval=function(s){ try{ if(self.__JIT.length<800) self.__JIT.push(String(s).slice(0,60000)); }catch(_){} return _e(s); };"
            "window.fetch=function(){"
            "  try{ var a=arguments; var opt=a[1]||{}; var h=opt.headers||{};"
            "    var rec={url:(typeof a[0]==='string'?a[0]:(a[0]&&a[0].url)||''), hdrs:{}};"
            "    for(var k in h){ if(/x-sap|sz-token|af-ac|shpsec|risk|csrftoken/i.test(k)) rec.hdrs[k]=h[k]; }"
            "    if(Object.keys(rec.hdrs).length) self.__HDR.push(rec);"
            "  }catch(_){}"
            "  return _f.apply(this,arguments); };"
            "})();")
    return hook + source

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox","--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage","--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server":"http://"+HOST,"username":USER,"password":PASS}, ignore_https_errors=False)
    p = c.new_page()
    src = open(SRC, encoding="utf-8", errors="replace").read()
    patched = patch(src)
    print(f"[final] patched: {len(src)}->{len(patched)}")
    def route_handler(route):
        if FRAG in route.request.url:
            route.fulfill(status=200, content_type="application/javascript; charset=utf-8", body=patched)
        else: route.continue_()
    p.route("**/*.js", route_handler)
    print("[final] load..."); p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    try: p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=2000, force=True); time.sleep(2)
    except Exception: pass
    # isi phone
    try:
        inp=p.locator("input[name='phone']").first
        if inp.count(): inp.click(timeout=4000); inp.type(PHONE.lstrip("62").lstrip("0"), delay=40)
    except Exception: pass
    time.sleep(1.5)
    # klik BERIKUTNYA (human-like)
    for sel in ["button:has-text('BERIKUTNYA')","text=BERIKUTNYA","button:has-text('Berikutnya')"]:
        try:
            loc=p.locator(sel).first
            if loc.count():
                bb=loc.bounding_box()
                if bb:
                    p.mouse.move(bb["x"]+bb["width"]/2,bb["y"]+bb["height"]/2); time.sleep(0.15)
                    p.mouse.down(); time.sleep(0.08); p.mouse.up(); break
        except Exception: pass
    print(f"[final] tunggu {SECONDS}s (signer window)..."); time.sleep(SECONDS)
    res = p.evaluate("()=>({jit:self.__JIT||[], hdr:self.__HDR||[]})")
    b.close()

json.dump(res, open(OUT,"w"))
j=res.get("jit") or []; h=res.get("hdr") or []
print(f"\n[final] generated JS: {len(j)}")
print(f"[final] signed requests: {len(h)}")
for r in h[:8]: print(f"  {r['url'][:60]} → {list(r['hdrs'].keys())}")
# simpan source terbesar (kandidat signer)
if j:
    big=sorted(j, key=len, reverse=True)
    open(f"{ROOT}/vm_signer_gen.js","w").write('\n\n/* ---- */\n\n'.join(big[:20]))
    print(f"[final] largest generated source: {len(big[0])} chars")
print(f"[final] → {OUT}")
