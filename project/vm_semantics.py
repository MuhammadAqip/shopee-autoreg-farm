#!/usr/bin/env python3
"""vm_semantics.py — capture semantik opcode dari RUNTIME (nilai operand + efek).

Patch interpreter untuk merekam, per eksekusi:
  - opcode
  - operand dibaca (ac[pc..pc+len-1])
  - nilai stack/variabel sebelum & sesudah (via tM/tG helpers)

Dengan ini: opcode → efek observable → semantik.
"""
import sys, os, time, json
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285613334442"
SECONDS = 90
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/vm_semantics.json"
SRC = f"{ROOT}/sdk/worker_scripts/bile.com_shopee_shopee-pcmall-live-sg_assets_sfu-stable.c3d38f8e0e81e513.2023.js.js"
FRAG = "sfu-stable.c3d38f8e0e81e513.2023.js"

def patch(source):
    needle = "tO=ac[_++],!tp&&"
    # Rekam opcode + window operand + L variabel snapshot (kalau ada)
    inject = (
        "tO=ac[_++],"
        "(self.__VMS||(self.__VMS=[])).length<40000&&self.__VMS.push("
        "[_,tO,ac[_],ac[_+1],ac[_+2],ac[_+3],ac[_+4],"
        "(typeof K!=='undefined'?K:null),(typeof G!=='undefined'?G:null)]),"
        "!tp&&"
    )
    if needle in source:
        return source.replace(needle, inject, 1)
    return source

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox","--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage","--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server":"http://"+HOST,"username":USER,"password":PASS}, ignore_https_errors=False)
    p = c.new_page()
    src = open(SRC, encoding="utf-8", errors="replace").read()
    patched = patch(src)
    print(f"[sem] patched: {len(src)}->{len(patched)}")
    def route_handler(route):
        if FRAG in route.request.url:
            route.fulfill(status=200, content_type="application/javascript; charset=utf-8", body=patched)
        else: route.continue_()
    p.route("**/*.js", route_handler)
    print("[sem] load..."); p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
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
    print(f"[sem] tunggu {SECONDS}s..."); time.sleep(SECONDS)
    res = p.evaluate("()=>({s:self.__VMS||[]})")
    b.close()

json.dump(res, open(OUT,"w"))
t=res.get("s") or []
print(f"\n[sem] captured: {len(t)} exec entries")
# Kelompokkan per opcode: nilai K/G yang muncul
from collections import defaultdict, Counter
per_op=defaultdict(list)
for e in t:
    per_op[e[1]].append(e)
print(f"[sem] unique opcodes: {len(per_op)}")
for op in sorted(per_op)[:20]:
    rows=per_op[op]
    Ks=Counter(r[7] for r in rows if r[7] is not None)
    print(f"  op{op}: {len(rows)}× K-vals={list(Ks)[:3]}")
print(f"[sem] → {OUT}")
