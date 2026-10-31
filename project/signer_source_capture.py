#!/usr/bin/env python3
"""signer_source_capture.py — Option B: capture SOURCE SIGNER ASLI per-fungsi.

VM = JIT (V() generate JS → y()=eval). Hook eval → tiap generated function
disimpen. Cari yang:
  - punya byk argumen / operation crypto
  - menghasilkan string panjang (signature)
  - referensi ke header name

Output: tiap fungsi JS asli → file terpisah.
"""
import sys, os, time, json, re
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285617778886"
SECONDS = 140
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/signer_sources.json"
SRC = f"{ROOT}/sdk/worker_scripts/bile.com_shopee_shopee-pcmall-live-sg_assets_sfu-stable.c3d38f8e0e81e513.2023.js.js"
FRAG = "sfu-stable.c3d38f8e0e81e513.2023.js"

def patch(source):
    hook = ("(function(){"
            "self.__SRC=self.__SRC||[];"
            "var _e=window.eval;"
            "window.eval=function(s){try{if(self.__SRC.length<2000)self.__SRC.push(String(s));}catch(_){}return _e(s);};"
            "if(typeof Function!=='undefined'){var _F=Function;"
            "window.Function=function(){try{var b=arguments[arguments.length-1];"
            "if(typeof b==='string'&&self.__SRC.length<2000)self.__SRC.push('/*Function*/ '+b);}catch(_){}"
            "return _F.apply(this,arguments);};window.Function.prototype=_F.prototype;}"
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
    print(f"[B] patched: {len(src)}->{len(patched)}")
    def route_handler(route):
        if FRAG in route.request.url:
            route.fulfill(status=200, content_type="application/javascript; charset=utf-8", body=patched)
        else: route.continue_()
    p.route("**/*.js", route_handler)
    print("[B] load..."); p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
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
    print(f"[B] tunggu {SECONDS}s..."); time.sleep(SECONDS)
    res = p.evaluate("()=>({s:self.__SRC||[]})")
    b.close()

srcs = res.get("s") or []
json.dump(srcs, open(OUT,"w"))
print(f"\n[B] captured {len(srcs)} sources")
# filter kandidat signer: panjang + mengandung operasi crypto
crypt=[]
for i,s in enumerate(srcs):
    score=0
    for kw in ['charCodeAt','fromCharCode','^','toString(16)','>>>','<<','&','|','Math.imul','sha','hmac','length','for(']:
        if kw in s: score+=1
    if score>=4 and len(s)>150: crypt.append((i,len(s),score,s[:120]))
crypt.sort(key=lambda x:-x[2])
print(f"\n[B] crypto-candidate sources: {len(crypt)}")
for i,l,sc,pre in crypt[:12]:
    print(f"  #{i} len={l} score={sc}: {pre[:90]}")
# simpan kandidat terbesar
if crypt:
    top=sorted(srcs, key=len, reverse=True)[:30]
    open(f"{ROOT}/signer_src_dump.js","w").write('\n\n/* ===== */\n\n'.join(top))
    print(f"\n[B] top-30 largest → signer_src_dump.js")
print(f"[B] → {OUT}")
