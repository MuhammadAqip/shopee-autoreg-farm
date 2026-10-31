#!/usr/bin/env python3
"""dump_pw_form.py — dump struktur form password shopee (button, form, inputs)."""
import sys, time, json
from playwright.sync_api import sync_playwright
PROXY = sys.argv[1] if len(sys.argv) > 1 else "http://user:pass@gb.vsproxy.org:10000"
import re
m = re.match(r"http://([^:]+):([^@]+)@([^:]+):(\d+)", PROXY)
PXY = {"server": f"http://{m.group(3)}:{m.group(4)}", "username": m.group(1), "password": m.group(2)}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, args=["--no-sandbox","--disable-blink-features=AutomationControlled"])
    c = b.new_context(user_agent=UA, locale="id-ID", proxy=PXY, viewport={"width":1280,"height":900})
    p = c.new_page()
    print("goto login page (as logged-in-less) — just inspecting DOM helpers")
    # just dump the signup page DOM structure
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
    time.sleep(6)
    info = p.evaluate("""()=>{
      const out={url:location.href};
      out.buttons=[...document.querySelectorAll('button')].map(b=>({txt:b.innerText.trim().slice(0,40),disabled:b.disabled,cls:b.className.slice(0,60)})).filter(x=>x.txt);
      out.forms=[...document.querySelectorAll('form')].map(f=>({action:f.action,method:f.method}));
      out.inputs=[...document.querySelectorAll('input')].map(i=>({type:i.type,name:i.name,placeholder:i.placeholder.slice(0,30),w:i.getBoundingClientRect().width}));
      return out;
    }""")
    print(json.dumps(info, indent=1, ensure_ascii=False))
    b.close()
