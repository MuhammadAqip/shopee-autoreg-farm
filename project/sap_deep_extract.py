#!/usr/bin/env python3
"""sap_deep_extract.py — #11-A deep: extract SEMUA script source dari worker SAP.

Metode:
  - Target.setAutoAttach waitForDebuggerOnStart=True → worker pause SEBELUM jalan
  - Via CDP raw (playwright new_cdp_session per worker) → Debugger.enable
  - Debugger.scriptParsed → tiap scriptId → Debugger.getScriptSource
  - Simpan tiap script; tandai yg berisi crypto/rule (wasm magic, AES, sign)
  - Juga coba Runtime.evaluate cari WASM instance + key di worker global

Playwright tidak mudah pegang raw worker session → pakai pendekatan: buka worker URL
LANGSUNG sebagai page (kalau bisa), + fetch script dari cache. Fallback: pakai CDP
via chrome-remote-interface kalau ada.

Usage: sap_deep_extract.py <phone> [--seconds 90]
"""
import sys, os, time, json, base64, re
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285600000000"
SECONDS = 90
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
WORKER_URL = "https://shopee.co.id/pcmall-assets/assets/af388a216703068c.worker.js"
OUTDIR = f"{ROOT}/sdk/worker_scripts"
os.makedirs(OUTDIR, exist_ok=True)
OUT = f"{ROOT}/sap_deep_extract.json"

scripts = {}          # url -> {len, saved, flags}
wasm_hits = []

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", "--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                      ignore_https_errors=False)
    # buka worker URL sebagai page (worker script biasanya self-contained) — utk liat isinya
    p = c.new_page()
    cdp = c.new_cdp_session(p)
    cdp.send("Debugger.enable")
    cdp.send("Runtime.enable")

    # hook scriptParsed di page + semua sub-target
    def on_parsed(ev):
        try:
            sid = ev.get("scriptId"); url = ev.get("url") or ""
            if not sid:
                return
            try:
                src = cdp.send("Debugger.getScriptSource", {"scriptId": sid}).get("scriptSource", "")
            except Exception:
                return
            if not src:
                return
            key = url or f"anon_{sid}"
            flags = []
            if "AGFzbQ" in src or "\\x00asm" in src.lower() or "wasm" in src.lower():
                flags.append("WASM-ref")
            for kw in ("x-sap-ri", "x-sap-sec", "shpsec", "X25519", "AES", "sign", "riskToken", "importScripts"):
                if kw in src:
                    flags.append(kw)
            scripts[key] = {"len": len(src), "flags": flags}
            if flags:
                safe = re.sub(r"[^A-Za-z0-9._-]", "_", key)[-80:]
                fp = f"{OUTDIR}/{safe}.js"
                open(fp, "w").write(src)
                scripts[key]["saved"] = fp
                print(f"[deep] script: {key[:70]} len={len(src)} flags={flags}")
        except Exception as e:
            pass
    cdp.on("Debugger.scriptParsed", on_parsed)

    print("[deep] load signup + trigger...")
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)
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

    # sekalian: buka worker URL langsung (kalau bisa diakses sbg script) → liat isi penuh
    try:
        wsrc = p.evaluate("""async (u)=>{try{const r=await fetch(u);return await r.text();}catch(e){return 'ERR:'+e;}}""", WORKER_URL)
        if wsrc and not wsrc.startswith("ERR"):
            open(f"{OUTDIR}/worker_full.js", "w").write(wsrc)
            print(f"[deep] worker_full.js len={len(wsrc)}")
    except Exception as e:
        print(f"[deep] worker fetch err {str(e)[:60]}")

    print(f"[deep] tunggu {SECONDS}s (scriptParsed + worker attach)...")
    time.sleep(SECONDS)
    b.close()

json.dump({"scripts": scripts, "count": len(scripts)}, open(OUT, "w"), indent=1)
flagged = {k: v for k, v in scripts.items() if v.get("flags")}
print(f"\n[deep] total scripts parsed: {len(scripts)} | flagged: {len(flagged)}")
for k, v in list(flagged.items())[:20]:
    print(f"   {k[:70]}  flags={v['flags']}")
print(f"[deep] → {OUT}")
