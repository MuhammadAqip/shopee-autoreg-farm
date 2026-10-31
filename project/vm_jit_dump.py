#!/usr/bin/env python3
"""vm_jit_dump.py — dump GENERATED JS SOURCE dari JIT VM.

VM = source-generator: V(bytecode) → JS source string → y()=eval → function.
Patch: wrap eval (y) supaya log SEMUA source yang di-generate+eval.

HASIL: kode JS asli signer (bukan opcode)!
"""
import sys, os, time, json
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285614445553"
SECONDS = 90
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/vm_jit_source.json"
SRC = f"{ROOT}/sdk/worker_scripts/bile.com_shopee_shopee-pcmall-live-sg_assets_sfu-stable.c3d38f8e0e81e513.2023.js.js"
FRAG = "sfu-stable.c3d38f8e0e81e513.2023.js"

def patch(source):
    # Wrap global eval: log source before eval.
    # Sumber: 'ek=y(V())' → y = eval. Sufix inject di 'f=eval' assignment.
    needle = "f=eval,"
    inject = ("f=(function(origEval){return function(src){"
              "try{(self.__JIT||(self.__JIT=[])).length<500&&"
              "self.__JIT.push(typeof src==='string'?src.slice(0,50000):String(src));}catch(_){}"
              "return origEval(src);};})(eval),")
    if needle in source:
        return source.replace(needle, inject, 1)
    # fallback: hook global eval via defineProperty at top
    pre = ("(function(){var _e=window.eval;"
           "Object.defineProperty(window,'eval',{value:function(s){"
           "try{(self.__JIT||(self.__JIT=[])).length<500&&self.__JIT.push(String(s).slice(0,20000));}catch(_){}"
           "return _e(s);},configurable:true});})();")
    return pre + source

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox","--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage","--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server":"http://"+HOST,"username":USER,"password":PASS}, ignore_https_errors=False)
    p = c.new_page()
    src = open(SRC, encoding="utf-8", errors="replace").read()
    patched = patch(src)
    print(f"[jit] patched: {len(src)}->{len(patched)}")
    def route_handler(route):
        if FRAG in route.request.url:
            route.fulfill(status=200, content_type="application/javascript; charset=utf-8", body=patched)
        else: route.continue_()
    p.route("**/*.js", route_handler)
    print("[jit] load..."); p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    try: p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=2000, force=True); time.sleep(2)
    except Exception: pass
    try:
        inp=p.locator("input[name='phone']").first
        if inp.count(): inp.click(timeout=4000); inp.type(PHONE.lstrip("62").lstrip("0"), delay=40)
    except Exception: pass
    time.sleep(1.5)
    for sel in ["button:has-text('BERIKUTNYA')","text=BERIKUTNYA"]:
        try:
            loc=p.locator(sel).first
            if loc.count():
                bb=loc.bounding_box()
                if bb:
                    p.mouse.move(bb["x"]+bb["width"]/2,bb["y"]+bb["height"]/2); time.sleep(0.15)
                    p.mouse.down(); time.sleep(0.08); p.mouse.up(); break
        except Exception: pass
    print(f"[jit] tunggu {SECONDS}s..."); time.sleep(SECONDS)
    res = p.evaluate("()=>({jit:self.__JIT||[]})")
    b.close()

json.dump(res, open(OUT,"w"))
j=res.get("jit") or []
print(f"\n[jit] generated sources captured: {len(j)}")
# Tampilkan yang paling menarik (mengandung crypto/sign)
import re
keys=['x-sap','sign','sha','hmac','aes','encrypt','toString','slice','function','verify']
for i,s in enumerate(j[:5]):
    print(f"\n--- JIT source #{i} (len {len(s)}) ---")
    print(s[:400])
json.dump(j, open(f"{ROOT}/vm_jit_sources_full.json","w"))
print(f"\n[jit] → {OUT}")
