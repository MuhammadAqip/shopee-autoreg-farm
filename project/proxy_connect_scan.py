#!/usr/bin/env python3
"""proxy_connect_scan.py — cari proxy yg SUPPORT CONNECT (tunnel 443).

Chromium butuh CONNECT. Banyak proxy publik plain-HTTP-only → gagal.
Scan semua, simpan yg CONNECT 200 OK → proxies_tiprouter_connect.txt

Usage: proxy_connect_scan.py [input] [--threads N]
"""
import concurrent.futures
import re
import socket
import sys
import time

INP = "/root/shopee-farm/proxies_tiprouter.txt"
OUT = "/root/shopee-farm/proxies_tiprouter_connect.txt"
THREADS = 40
TARGET = ("shopee.co.id", 443)


def test(proxy):
    m = re.match(r"(\w+)://([\d.]+):(\d+)", proxy.strip())
    if not m:
        return None
    scheme, host, port = m.groups()
    if scheme.startswith("socks"):
        return None  # socks CONNECT beda; skip
    t0 = time.time()
    try:
        s = socket.create_connection((host, int(port)), timeout=8)
        req = f"CONNECT {TARGET[0]}:{TARGET[1]} HTTP/1.1\r\nHost: {TARGET[0]}:{TARGET[1]}\r\n\r\n"
        s.sendall(req.encode())
        resp = s.recv(200)
        s.close()
        line = resp.split(b"\r\n")[0].decode(errors="ignore")
        if "200" in line:
            return (proxy, time.time() - t0, line)
    except Exception:
        return None
    return None


def main():
    global THREADS
    for a in sys.argv[1:]:
        if a.startswith("--threads="):
            THREADS = int(a.split("=", 1)[1])
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    inp = files[0] if files else INP
    proxies = [l.strip() for l in open(inp) if l.strip()]
    print(f"[scan] {len(proxies)} proxy → cari CONNECT support ({THREADS} threads)")
    good = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as ex:
        for res in ex.map(test, proxies):
            if res:
                good.append(res)
                print(f"  ✅ {res[1]:.2f}s {res[0]}")
    good.sort(key=lambda x: x[1])
    print(f"\n[scan] CONNECT-OK: {len(good)}/{len(proxies)}")
    if good:
        open(OUT, "w").write("\n".join(p for p, _, _ in good) + "\n")
        print(f"[scan] → {OUT}")


if __name__ == "__main__":
    main()
