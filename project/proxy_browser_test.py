#!/usr/bin/env python3
"""proxy_browser_test.py — uji proxy PAKAI CHROMIUM asli (bukan requests).

Kenapa: banyak proxy http cepet di `requests` tapi GAGAL di Chromium
(ERR_TIMED_OUT) karena beda handling CONNECT/tunnel.

Usage: proxy_browser_test.py [list.txt] [--n 5]
  → uji N proxy pertama, tulis yg BROWSER-OK ke proxies_tiprouter_browser.txt
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path("/root/shopee-farm")
INP = ROOT / "proxies_tiprouter_fast.txt"
OUT = ROOT / "proxies_tiprouter_browser.txt"


def parse_proxy(proxy):
    import re
    s = proxy.strip()
    m = re.match(r"(\w+)://([\d.]+):(\d+)", s)
    if not m:
        return None
    scheme, host, port = m.groups()
    return {"server": f"{scheme}://{host}:{port}"}


def main():
    args = sys.argv[1:]
    n = 10
    for a in args:
        if a.startswith("--n="):
            n = int(a.split("=", 1)[1])
    files = [a for a in args if not a.startswith("--")]
    inp = Path(files[0]) if files else INP
    proxies = [l.strip() for l in inp.read_text().splitlines() if l.strip()][:n]
    print(f"[btest] uji {len(proxies)} proxy pakai Chromium")
    good = []
    with sync_playwright() as pw:
        for proxy in proxies:
            pxy = parse_proxy(proxy)
            if not pxy:
                continue
            try:
                b = pw.chromium.launch(headless=True, proxy=pxy,
                                       args=["--no-sandbox", "--disable-dev-shm-usage"])
                ctx = b.new_context(user_agent="Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36")
                pg = ctx.new_page()
                pg.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=25000)
                title = pg.title()
                txt = pg.evaluate("()=>document.body.innerText||''")[:60]
                ok = "shopee" in (title + txt).lower() or len(txt) > 10
                print(f"  {'✅' if ok else '⚠️'} {proxy} | {title[:30]} | {txt[:40]}")
                if ok:
                    good.append(proxy)
                b.close()
            except Exception as e:
                print(f"  ❌ {proxy} | {type(e).__name__}: {str(e)[:50]}")
    if good:
        OUT.write_text("\n".join(good) + "\n")
        print(f"\n[btest] BROWSER-OK: {len(good)} → {OUT}")
    else:
        print("\n[btest] tidak ada yg browser-OK")


if __name__ == "__main__":
    main()
