#!/usr/bin/env python3
"""proxy_rank_tiprouter.py — rank proxy tiprouter by LATENCY ke Shopee (page-like).

Beda dari proxy_check_tiprouter.py (yg cuma cek connect):
  - request ke halaman /buyer/signup (HTML, bukan API)
  - ukur latency nyata
  - buang yg > 8s

Usage: proxy_rank_tiprouter.py [input] [--threads N] [--maxt 8]
"""
import concurrent.futures
import re
import sys
import time

import requests

INP = "/root/shopee-farm/proxies_tiprouter_live.txt"
OUT = "/root/shopee-farm/proxies_tiprouter_fast.txt"
THREADS = 25
MAXT = 8.0
URL = "https://shopee.co.id/buyer/signup"


def test(proxy):
    m = re.match(r"(\w+)://([\d.]+):(\d+)", proxy.strip())
    if not m:
        return None
    scheme, host, port = m.groups()
    # Playwright/requests natively supports http; socks needs extra — fokus http dulu
    if scheme.startswith("socks"):
        return None
    p = {"http": f"http://{host}:{port}", "https": f"http://{host}:{port}"}
    t0 = time.time()
    try:
        r = requests.get(URL, proxies=p, timeout=MAXT,
                         headers={"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"},
                         allow_redirects=True)
        dt = time.time() - t0
        if dt <= MAXT and len(r.content) > 1000:
            return (proxy, dt, r.status_code)
    except Exception:
        return None
    return None


def main():
    global INP, THREADS, MAXT
    for a in sys.argv[1:]:
        if a.startswith("--threads"): THREADS = int(a.split("=")[1]) if "=" in a else THREADS
        if a.startswith("--maxt"): MAXT = float(a.split("=")[1]) if "=" in a else MAXT
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    if files: INP = files[0]
    proxies = [l.strip() for l in open(INP) if l.strip()]
    print(f"[rank] {len(proxies)} proxy, {THREADS} threads, max {MAXT}s")
    good = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as ex:
        for res in ex.map(test, proxies):
            if res:
                good.append(res)
    good.sort(key=lambda x: x[1])
    print(f"\n[rank] lolos: {len(good)}/{len(proxies)}")
    for proxy, dt, sc in good[:20]:
        print(f"  🚀 {dt:5.2f}s [{sc}] {proxy}")
    if good:
        open(OUT, "w").write("\n".join(p for p, _, _ in good) + "\n")
        print(f"\n[rank] → {OUT}")


if __name__ == "__main__":
    main()
