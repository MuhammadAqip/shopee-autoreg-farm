#!/usr/bin/env python3
"""proxy_check_tiprouter.py — cek proxy tiprouter mana yg HIDUP.

Format input: scheme://host:port (no auth) — http/socks4/socks5.
Uji ke shopee.co.id. Simpan yang hidup → proxies_tiprouter_live.txt.

Usage: proxy_check_tiprouter.py [input_file] [--threads N] [--timeout S]
"""
import concurrent.futures
import re
import sys
import time

import requests

INP = "/root/shopee-farm/proxies_tiprouter.txt"
OUT = "/root/shopee-farm/proxies_tiprouter_live.txt"
THREADS = 30
TIMEOUT = 12
TEST_URL = "https://shopee.co.id/api/v4/shop/get_shop_detail?shopid=1"


def test(proxy):
    m = re.match(r"(\w+)://([\d.]+):(\d+)", proxy.strip())
    if not m:
        return proxy, False, "badfmt"
    scheme, host, port = m.groups()
    p = {"http": f"{scheme}://{host}:{port}", "https": f"{scheme}://{host}:{port}"}
    try:
        # cek shopee
        r = requests.get(TEST_URL, proxies=p, timeout=TIMEOUT,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code in (200, 403, 404, 500) and len(r.content) > 0:
            # 200/403 artinya proxy MENERUSKAN koneksi (bukan proxy mati)
            t0 = time.time()
            return proxy, True, f"{r.status_code} {int((time.time()-t0)*1000)}ms"
        return proxy, False, f"http{r.status_code}"
    except Exception as e:
        return proxy, False, type(e).__name__


def main():
    global INP, THREADS, TIMEOUT
    args = sys.argv[1:]
    for a in list(args):
        if a.startswith("--threads"):
            THREADS = int(a.split("=")[1]) if "=" in a else THREADS
        if a.startswith("--timeout"):
            TIMEOUT = int(a.split("=")[1]) if "=" in a else TIMEOUT
    files = [a for a in args if not a.startswith("--")]
    if files:
        INP = files[0]
    proxies = [l.strip() for l in open(INP) if l.strip()]
    print(f"[check] {len(proxies)} proxy, {THREADS} threads, timeout {TIMEOUT}s")
    alive = []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as ex:
        for proxy, ok, info in ex.map(test, proxies):
            if ok:
                alive.append(proxy)
                print(f"  ✅ {proxy} ({info})")
    print(f"\n[check] hidup: {len(alive)}/{len(proxies)} dalam {int(time.time()-t0)}s")
    if alive:
        open(OUT, "w").write("\n".join(alive) + "\n")
        print(f"[check] → {OUT}")


if __name__ == "__main__":
    main()
