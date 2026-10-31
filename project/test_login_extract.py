#!/usr/bin/env python3
"""test_login_extract.py — buktikan fix: login eksplisit → cookie lengkap + userId."""
import sys, time, json
sys.path.insert(0, "/root/shopee-farm")
from playwright.sync_api import sync_playwright

PHONE = sys.argv[1]      # loginKey (phone stem)
PW = sys.argv[2]         # password
PROXY = sys.argv[3] if len(sys.argv) > 3 else ""

import re
pm = re.match(r"http://([^:]+):([^@]+)@([^:]+):(\d+)", PROXY) if PROXY else None

with sync_playwright() as pw:
    br = pw.chromium.launch(headless=False, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    ctx_args = dict(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    if pm:
        ctx_args["proxy"] = {"server": f"http://{pm.group(3)}:{pm.group(4)}", "username": pm.group(1), "password": pm.group(2)}
    ctx = br.new_context(**ctx_args)
    p = ctx.new_page()
    p.goto("https://shopee.co.id/buyer/login", wait_until="domcontentloaded", timeout=60000)
    time.sleep(6)
    filled = p.evaluate("""(a)=>{const[ph,pwv]=a;
      const setV=(el,v)=>{const d=Object.getOwnPropertyDescriptor(el,'value');
        if(d&&d.set)d.set.call(el,v);else el.value=v;
        el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};
      let fi=document.querySelector('input[name="loginKey"],input[type="text"]');
      let fp=document.querySelector('input[name="password"],input[type="password"]');
      if(!fi||!fp)return false; setV(fi,ph); setV(fp,pwv); return true;}""", [PHONE, PW])
    print("fill:", filled)
    time.sleep(1)
    for b in p.locator("button").all():
        try:
            t = (b.inner_text() or "").strip().lower()
            if t in ("log in", "login", "masuk"):
                b.click(); print("clicked:", t); break
        except Exception:
            pass
    # tunggu SPC_U (max 40s)
    spc_u = None
    for i in range(40):
        c = {ck["name"]: ck["value"] for ck in ctx.cookies()}
        if c.get("SPC_U"):
            spc_u = c["SPC_U"]; print(f"[{i}s] SPC_U={spc_u}"); break
        time.sleep(1)
    if not spc_u:
        print("SPC_U GAK MUNCUL")
    p.goto("https://shopee.co.id/", wait_until="domcontentloaded", timeout=60000)
    time.sleep(6)
    import shopee_hold as H
    acc = H.extract_account(p, PHONE, PW, "")
    print("=== HASIL EXTRACT ===")
    print("user_id   :", repr(acc["user_id"]))
    print("username  :", repr(acc["username"]))
    print("device_id :", repr(acc["device_id"]))
    print("fp        :", repr(acc["fingerprint"]))
    print("cookie keys:", [x.split("=")[0] for x in acc["cookie"].split("; ")])
    print("=== VALIDATE ===")
    import validate_account as VA
    print(VA.validate(acc["cookie"]))
    br.close()
