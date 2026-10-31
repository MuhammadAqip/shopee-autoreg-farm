#!/usr/bin/env python3
"""vm_dump_full.py — dump bytecode PENUH + data section + struktur VM.

Patch interpreter untuk:
  1. Snapshot `ac` LENGKAP (panjang penuh) saat eksekusi pertama.
  2. Snapshot `S` (data base) per call.
  3. Log operand fetch: (pc, opcode, operands_read) untuk decode encoding.
  4. Dump semua module entry (pc besar->kecil jump).

Hasil: vm_full_dump.json → cukup untuk bangun emulator offline.
"""
import sys, os, time, json
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285612223331"
SECONDS = 90
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/vm_full_dump.json"
SRC = f"{ROOT}/sdk/worker_scripts/bile.com_shopee_shopee-pcmall-live-sg_assets_sfu-stable.c3d38f8e0e81e513.2023.js.js"
FRAG = "sfu-stable.c3d38f8e0e81e513.2023.js"

def patch(source):
    needle = "tO=ac[_++],!tp&&"
    # Snapshot lengkap ac + data trace (opcode + 4 operand lookahead)
    inject = (
        "tO=ac[_++],"
        "(self.__VMINIT||(self.__VMINIT=0))<1&&(self.__VMINIT=1,"
        "self.__ACFULL=ac.slice?ac.slice(0):Array.prototype.slice.call(ac),"
        "self.__S0=(typeof S!=='undefined'?S:null),"
        "self.__TD0=(typeof tD!=='undefined'?String(tD):null)),"
        "(self.__VMT||(self.__VMT=[])).length<80000&&self.__VMT.push([_,tO,ac[_],ac[_+1],ac[_+2],ac[_+3]]),"
        "!tp&&"
    )
    if needle in source:
        return source.replace(needle, inject, 1)
    # fallback
    return source.replace("tO=ac[_++]",
        "(self.__VMT||(self.__VMT=[])).length<80000&&self.__VMT.push([_,ac[_]]),tO=ac[_++]", 1)

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox","--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage","--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server":"http://"+HOST,"username":USER,"password":PASS}, ignore_https_errors=False)
    p = c.new_page()
    src = open(SRC, encoding="utf-8", errors="replace").read()
    patched = patch(src)
    print(f"[dump] patched: {len(src)}->{len(patched)}")
    def route_handler(route):
        if FRAG in route.request.url:
            route.fulfill(status=200, content_type="application/javascript; charset=utf-8", body=patched)
        else: route.continue_()
    p.route("**/*.js", route_handler)
    print("[dump] load..."); p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
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
    print(f"[dump] tunggu {SECONDS}s..."); time.sleep(SECONDS)
    res = p.evaluate("""()=>({ac: self.__ACFULL||null, s0: self.__S0, td0: self.__TD0, t: self.__VMT||[]})""")
    b.close()

json.dump(res, open(OUT,"w"))
print(f"\n[dump] bytecode full len: {len(res.get('ac') or [])}")
print(f"[dump] S0={res.get('s0')} tD0={res.get('td0')}")
t=res.get("t") or []
print(f"[dump] trace: {len(t)} entries")
if t: print(f"  first 5 [pc,op,a,b,c,d]: {t[:5]}")
print(f"[dump] → {OUT}")
