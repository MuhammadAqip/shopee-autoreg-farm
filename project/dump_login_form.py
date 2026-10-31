#!/usr/bin/env python3
"""dump_login_form.py — lihat struktur form login shopee."""
import sys, time, re
from playwright.sync_api import sync_playwright
PROXY = sys.argv[1] if len(sys.argv) > 1 else ""
pm = re.match(r"http://([^:]+):([^@]+)@([^:]+):(\d+)", PROXY) if PROXY else None
with sync_playwright() as pw:
    br = pw.chromium.launch(headless=False, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    a = dict(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    if pm: a["proxy"] = {"server": f"http://{pm.group(3)}:{pm.group(4)}", "username": pm.group(1), "password": pm.group(2)}
    ctx = br.new_context(**a); p = ctx.new_page()
    p.goto("https://shopee.co.id/buyer/login", wait_until="domcontentloaded", timeout=60000)
    time.sleep(8)
    info = p.evaluate("""()=>{
      const out={url:location.href, inputs:[], buttons:[]};
      document.querySelectorAll('input').forEach(e=>out.inputs.push({name:e.name,type:e.type,ph:e.placeholder,id:e.id,cls:e.className.slice(0,50)}));
      document.querySelectorAll('button').forEach(e=>out.buttons.push({txt:(e.textContent||'').trim().slice(0,30),cls:e.className.slice(0,40)}));
      return out;}""")
    print("URL:", info["url"])
    print("INPUTS:")
    for i in info["inputs"]: print("  ", i)
    print("BUTTONS:")
    for b in info["buttons"][:15]: print("  ", b)
    p.screenshot(path="/tmp/login_page.png")
    br.close()
