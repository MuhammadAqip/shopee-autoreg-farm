#!/usr/bin/env python3
"""vm_worker_trace.py — attach CDP ke WORKER (tempat VM hidup) + trace opcode.

Perbaikan dari vm_trace.py:
  - page.workers / context.on("serviceworker") + CDP Target attach per-worker
  - Cari script VM di worker (via Debugger.scriptParsed per target)
  - Set breakpoint di interpreter → trace opcode (ac[_], tO) di break hits
  - Alternatif ke-2: Runtime.addBinding + patch window di worker via Runtime.evaluate
"""
import sys, os, time, json, base64
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285600003333"
SECONDS = 100
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/vm_worker_trace.json"

worker_scripts = {}   # targetId -> [scriptParsed...]
seen_targets = set()

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", "--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                      ignore_https_errors=False)
    p = c.new_page()
    cdp = c.new_cdp_session(p)
    cdp.send("Target.setAutoAttach", {"autoAttach": True, "waitForDebuggerOnStart": False, "flatten": True})

    def on_attached(e):
        sid = e.get("sessionId")
        tinfo = e.get("targetInfo", {})
        ttype = tinfo.get("type")
        url = tinfo.get("url", "")[:70]
        if ttype in ("worker", "shared_worker", "service_worker"):
            print(f"[wk] attached {ttype}: {url} ({sid})")
            seen_targets.add(sid)
            worker_scripts[sid] = []
            # Playwright: buat CDPSession via browser-level session
            try:
                bcdp = b.new_browser_cdp_session()
                cs = bcdp.send("Target.attachToTarget", {"targetId": tinfo.get("targetId"), "flatten": True})
                print(f"[wk]   nested attach: {cs}")
            except Exception as ex:
                print(f"[wk]   nested err: {ex}")
    cdp.on("Target.attachedToTarget", on_attached)

    print("[wk] load page...")
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(6)

    # Playwright also exposes page.workers directly
    for w in p.workers:
        print(f"[wk] playwright worker: {w.url[:80]}")
    print(f"[wk] targets attached: {len(seen_targets)}")

    # trigger
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

    print(f"[wk] tunggu {SECONDS}s..."); time.sleep(SECONDS)
    b.close()

json.dump({"targets": len(seen_targets), "scripts": worker_scripts}, open(OUT, "w"), indent=1)
print(f"\n[wk] targets: {len(seen_targets)}")
for tid, scripts in worker_scripts.items():
    vm = [s for s in scripts if "sfu-stable" in s.get("url","") or "worker.js" in s.get("url","")]
    print(f"   {tid[:16]}: {len(scripts)} scripts, {len(vm)} VM-candidate")
    for s in vm[:3]: print(f"      {s['url'][:75]}")
print(f"[wk] → {OUT}")
