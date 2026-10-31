#!/usr/bin/env python3
"""vm_patch_trace.py — PATCH sumber interpreter VM, sajikan via route, trace opcode.

Pendekatan PALING LANGSUNG (tanpa CDP worker attach yang ribet):
  1. Download sfu-stable.js (atau pakai file lokal).
  2. Sisipkan instrumentasi ke dalam interpreter Z: setiap iterasi loop,
     catat (pc=_, opcode=tO) ke array global; prefix hasil trace ke window.
  3. Route-intercept request script → serve versi patched.
  4. Jalankan signup → signer fire → trace terkumpul.
  5. Baca trace: opcode sequence + bytecode.

Ini menembus VM dengan MELIHAT bytecode-nya jalan, bukan reverse statis.
"""
import sys, os, time, json, base64, re
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285607778889"
SECONDS = 100
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/vm_patch_trace.json"
SRC_FILE = f"{ROOT}/sdk/worker_scripts/bile.com_shopee_shopee-pcmall-live-sg_assets_sfu-stable.c3d38f8e0e81e513.2023.js.js"
TARGET_FRAG = "sfu-stable.c3d38f8e0e81e513.2023.js"

def patch(source):
    """Sisipkan logging ke interpreter: pada 'tO=ac[_++]' catat tO+_.
    Juga snapshot bytecode `ac` pada pc eksekusi pertama."""
    needle = "tO=ac[_++],!tp&&"
    inject = ("tO=ac[_++],"
              "(self.__VMAC||(self.__VMAC=[])).length<1&&(self.__VMAC.push(1),"
              "self.__AC0=ac.slice?ac.slice(0,6000):ac),"
              "(self.__VMT||(self.__VMT=[])).length<200000&&self.__VMT.push([_,tO]),"
              "!tp&&")
    n = source.count(needle)
    if n == 0:
        # fallback: cari pola longgar
        needle2 = "tO=ac[_++]"
        return source.replace(needle2, "(self.__VMT||(self.__VMT=[])).length<12000&&self.__VMT.push([_,ac[_]]),"+needle2, 1), 0
    return source.replace(needle, inject, 1), n

def main():
    src = open(SRC_FILE, encoding="utf-8", errors="replace").read()
    patched, n = patch(src)
    print(f"[patch] interpreter hook injected: {n} site(s), size {len(src)}->{len(patched)}")
    open(f"{ROOT}/sdk/sfu_patched.js", "w").write(patched)

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage", "--use-gl=swiftshader"])
        c = b.new_context(user_agent=UA, locale="id-ID",
                          proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                          ignore_https_errors=False)
        p = c.new_page()

        # route: serve patched script untuk URL target
        def route_handler(route):
            u = route.request.url
            if TARGET_FRAG in u:
                print(f"[route] serving patched: {u[:70]}")
                route.fulfill(status=200, content_type="application/javascript; charset=utf-8",
                              body=patched)
            else:
                route.continue_()
        p.route("**/*.js", route_handler)

        print("[patch] load page...")
        p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        try:
            p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=2000, force=True); time.sleep(2)
        except Exception: pass
        try:
            inp = p.locator("input[name='phone']").first
            if inp.count():
                inp.click(timeout=4000); inp.type(PHONE.lstrip("62").lstrip("0"), delay=40)
        except Exception: pass
        time.sleep(1.5)
        for sel in ["button:has-text('BERIKUTNYA')", "text=BERIKUTNYA"]:
            try:
                loc = p.locator(sel).first
                if loc.count():
                    bb = loc.bounding_box()
                    if bb:
                        p.mouse.move(bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2); time.sleep(0.15)
                        p.mouse.down(); time.sleep(0.08); p.mouse.up(); break
            except Exception: pass
        print(f"[patch] tunggu {SECONDS}s..."); time.sleep(SECONDS)
        data = p.evaluate("()=>({t:(self.__VMT||window.__VMT||[]), a:(self.__AC0||window.__AC0||null)})")
        b.close()

    json.dump(data, open(OUT, "w"))
    trace = data.get("t", [])
    ac0 = data.get("a")
    print(f"\n[patch] trace entries: {len(trace)}")
    if ac0:
        print(f"  bytecode snapshot: {len(ac0)} slots, first30={ac0[:30]}")
        json.dump(ac0, open(f"{ROOT}/vm_bytecode_snapshot.json", "w"))
    if trace:
        print(f"  first 20 [pc, opcode]: {trace[:20]}")
        ops = [d[1] for d in trace if isinstance(d, list) and len(d)>1]
        from collections import Counter
        c = Counter(ops)
        print(f"  unique opcodes: {len(c)}")
        print(f"  top opcodes: {c.most_common(15)}")
    print(f"[patch] → {OUT}")

if __name__ == "__main__":
    main()
