#!/usr/bin/env python3
"""wa_bridge.py — HYBRID optimal: browser AMBIL m_token + cookies (1x), lalu WA via API.
Browser hanya buat: load signup → generate riskToken → (solve captcha kalau muncul) → ambil sesi.
API buat: send_vcode WA, verify_vcode, signup_by_otp.

Usage: wa_bridge.py <PHONE>
"""
import sys, time, json, uuid, hashlib
from playwright.sync_api import sync_playwright
import requests, urllib3
urllib3.disable_warnings()

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6289601416330"
PROXY = open("/root/shopee-farm/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]
USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

JS = {"risk": "", "sap_sec": "", "sap_ri": "", "calls": []}

# ---------- FASE 1: BROWSER ambil token ----------
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False,
                           args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://" + HOST, "username": USER, "password": PASS},
                      ignore_https_errors=True, viewport={"width": 1280, "height": 900})
    c.add_cookies([{"name": "shopee_webLanguage", "value": "id",
                    "domain": ".shopee.co.id", "path": "/"}])
    p = c.new_page()

    def on_resp(r):
        u = r.url
        if "shpsec/web/report" in u:
            try:
                tok = ((r.json().get("data") or {}).get("riskToken")) or ""
                if tok: JS["risk"] = tok; print("[GRAB] riskToken", flush=True)
            except Exception: pass
        if any(k in u for k in ("otp/send_vcode", "otp/verify_vcode", "otp/get_settings")):
            print(f"[NET] {r.request.method} {r.status} {u.split('?')[0][-35:]}", flush=True)
            h = r.request.headers
            JS["calls"].append({"url": u.split("?")[0], "hdrs": dict(h),
                                "body": r.request.post_data or ""})
    p.on("response", on_resp)

    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(18)
    try:
        btn = p.locator("button.shopee-button-outline").first
        if btn.count(): btn.click(timeout=2500, force=True); time.sleep(3)
    except Exception: pass
    try:
        inp = p.locator("input[name='phone']").first
        inp.click(timeout=3000); inp.type(PHONE, delay=45); print("[*] nomor diisi", flush=True)
    except Exception as e: print("fill err", str(e)[:80], flush=True)
    time.sleep(5)
    # klik SETUJU (modal ketentuan) — retry karena modal muncul telat
    for attempt in range(4):
        got = False
        for lbl in ("Setuju", "SETUJU"):
            try:
                loc = p.locator(f"button:has-text('{lbl}')").first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=3000, force=True)
                    print(f"[*] klik {lbl} (modal ketentuan, try {attempt+1})", flush=True)
                    got = True; time.sleep(3); break
            except Exception: pass
        if got: break
        time.sleep(3)
    # klik BERIKUTNYA
    for lbl in ("BERIKUTNYA", "Berikutnya", "Lanjut"):
        try:
            p.locator(f"button:has-text('{lbl}')").first.click(timeout=2500, force=True)
            print(f"[*] klik {lbl}", flush=True); break
        except Exception: pass
    time.sleep(20)
    body = p.evaluate("()=>document.body.innerText||''")
    print("[PAGE]", body[:400].replace("\n", " | "), flush=True)
    # deteksi WA dialog / captcha
    has_wa = "whatsapp" in body.lower() or "kirim ke" in body.lower()
    print("[WA-DIALOG]", has_wa, flush=True)
    # screenshot
    p.screenshot(path="/root/shopee-farm/shots/wa_bridge.png", full_page=True)
    # ambil x-sap-sec dari request terakhir (kalau ada)
    if JS["calls"]:
        h = JS["calls"][-1]["hdrs"]
        JS["sap_sec"] = h.get("x-sap-sec", ""); JS["sap_ri"] = h.get("x-sap-ri", "")
    CK = {ck["name"]: ck["value"] for ck in c.cookies()}
    p.screenshot(path="/root/shopee-farm/shots/wa_bridge.png", full_page=True)
    c.close(); b.close()

json.dump({"risk": JS["risk"], "cookies": CK, "sap_sec": JS["sap_sec"],
           "sap_ri": JS["sap_ri"], "phone": PHONE},
          open("/root/shopee-farm/wa_bridge_state.json", "w"))
print("[SAVED] wa_bridge_state.json | riskToken:", JS["risk"][:40], flush=True)
