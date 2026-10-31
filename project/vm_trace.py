#!/usr/bin/env python3
"""vm_trace.py — TRACE bytecode VM SAP di runtime.

Strategi (bukan reverse statis):
  1. Cari fungsi interpreter VM di page (yang punya polа `tO=ac[_++]`).
  2. Hook: sebelum loop jalan, sudah punya `ac` (bytecode) + `_` (pc).
  3. Alternatif: patch interpreter untuk log (pc, opcode) tiap step.
  4. Jalankan signup sampai signer fire → dapat trace opcode.
  5. Dari trace, rekonstruksi bytecode program + mapping opcode.

Cara paling bersih: hook `Function.prototype` / eval? Tidak — VM-nya closure.
Cara praktis: instrument via CDP Debugger.setBreakpoint di baris interpreter,
baca variabel lokal (ac, _, tO) tiap hit → trace penuh.
"""
import sys, os, time, json
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285600001111"
SECONDS = 90
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/vm_trace.json"

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", "--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                      ignore_https_errors=False)
    p = c.new_page()
    cdp = c.new_cdp_session(p)

    # === Strategi: temukan script VM via Debugger, pasang breakpoint ===
    scripts = []
    cdp.on("Debugger.scriptParsed", lambda e: scripts.append(e))
    cdp.send("Debugger.enable")
    cdp.send("Debugger.setAsyncCallStackDepth", {"maxDepth": 8})

    print("[vm] load page...")
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)

    # cari script yang punya pola interpreter VM (via source)
    vm_script = None
    for s in scripts:
        url = s.get("url", "")
        if "sfu-stable" in url or "worker" in url:
            vm_script = s
            break
    print(f"[vm] scripts parsed: {len(scripts)}, vm candidate: {vm_script.get('url','?')[:80] if vm_script else None}")

    # ekstrak source script VM untuk cari offset interpreter
    if vm_script:
        src = cdp.send("Debugger.getScriptSource", {"scriptId": vm_script["scriptId"]})["scriptSource"]
        idx = src.find("tO=ac[_++]")
        print(f"[vm] interpreter found in vm script at char {idx}")
        if idx > 0:
            line = src.count("\n", 0, idx) + 1
            col = idx - src.rfind("\n", 0, idx) - 1
            print(f"[vm] interpreter at line {line} col {col}")
            # pasang breakpoint di baris interpreter
            try:
                bp = cdp.send("Debugger.setBreakpointByUrl", {
                    "lineNumber": line - 1, "url": vm_script["url"],
                    "columnNumber": col})
                print(f"[vm] breakpoint set: {bp}")
            except Exception as e:
                print(f"[vm] bp err: {e}")

    # trigger signup
    time.sleep(2)
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

    print(f"[vm] tunggu {SECONDS}s (signer fire saat captcha/OTP)...")
    collected = [];
    def on_paused(e):
        try:
            fr = e.get("callFrames", [])
            if fr:
                collected.append({"fn": fr[0].get("functionName"), "loc": fr[0].get("location")})
                if len(collected) in (1, 5, 20, 50):
                    print(f"[vm] paused #{len(collected)} at {fr[0].get('functionName')}")
        except Exception: pass
        try: cdp.send("Debugger.resume")
        except Exception: pass
    cdp.on("Debugger.paused", on_paused)
    try:
        cdp.send("Debugger.resume")   # pastikan jalan
    except Exception: pass

    time.sleep(SECONDS)
    json.dump(collected, open(OUT, "w"), indent=1)
    print(f"\n[vm] total pauses: {len(collected)}")
    from collections import Counter
    fns = Counter(c.get("fn") for c in collected)
    for fn, n in fns.most_common(10):
        print(f"   {str(fn)[:40]:40} x{n}")
    b.close()
print(f"[vm] → {OUT}")
