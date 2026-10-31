#!/usr/bin/env python3
"""debug_reg.py — lihat halaman register + frame reCAPTCHA."""
import time, sys
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    p = ctx.new_page()
    p.goto("https://www.sadcaptcha.com/register", wait_until="domcontentloaded", timeout=60000)
    time.sleep(6)
    print("=== FRAMES ===")
    for f in p.frames:
        print(" ", (f.url or "(empty)")[:100])
    print("=== inputs ===")
    for sel in ["input[name=username]", "input[name=password1]", "input[name=password2]", "#agreeToTerms", ".g-recaptcha"]:
        try:
            n = p.locator(sel).count()
            print(f"  {sel}: {n}")
        except Exception as e:
            print(f"  {sel}: err {e}")
    # scroll ke bawah biar captcha muncul
    p.evaluate("()=>window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(3)
    print("=== frames after scroll ===")
    for f in p.frames:
        print(" ", (f.url or "(empty)")[:100])
    p.screenshot(path="/tmp/reg_debug.png", full_page=True)
    print("screenshot: /tmp/reg_debug.png")
    time.sleep(2)
    b.close()
