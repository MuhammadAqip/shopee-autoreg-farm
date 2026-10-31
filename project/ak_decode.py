#!/usr/bin/env python3
"""ak_decode.py — decoder string table Shopee (fungsi `ak`).

Dari sfu-stable.<hash>.js. Alphabet kustom + %xx → decodeURIComponent.
Terverifikasi: index 0 -> "export", 845 -> "__playwright", 927 -> "window.Cypress".
"""
import re, urllib.parse

ALPHA = "ofksgblrxcamqiunzpthjwydevYDSVHBOZKWEGFXCMINTJARQLPU1357249806+/="
_TBL = {c: i for i, c in enumerate(ALPHA)}


def ak_decode(s):
    """Reimpl `ak.Av(s)`: b64(custom alpha) -> bytes -> %xx -> unquote.
    3 byte per 4 char; blok terakhir parsial → 1-2 byte."""
    b = 0
    cnt = 0
    out = bytearray()
    for ch in s:
        fv = _TBL.get(ch)
        if fv is None:
            continue
        b = b * 64 + fv if (cnt % 4) else fv
        cnt += 1
        if cnt % 4 == 0:
            out.append((b >> 16) & 0xFF)
            out.append((b >> 8) & 0xFF)
            out.append(b & 0xFF)
    # blok parsial terakhir
    rem = cnt % 4
    if rem == 2:
        out.append((b >> 4) & 0xFF)
    elif rem == 3:
        out.append((b >> 10) & 0xFF)
        out.append((b >> 2) & 0xFF)
    pieces = "".join("%" + ("00" + format(x, "x"))[-2:] for x in out)
    return urllib.parse.unquote(pieces, encoding="utf-8", errors="replace")


def load_table(js_path):
    src = open(js_path, encoding="utf-8", errors="replace").read()
    m = re.search(r"function aj\(\)\{return\[(.*?)\]\}", src, re.S)
    return re.findall(r'"([^"]*)"', m.group(1))


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "bile.com_shopee_shopee-pcmall-live-sg_assets_sfu-stable.c3d38f8e0e81e513.2023.js.js"
    tbl = load_table(path)
    print(f"table size: {len(tbl)}")
    for i in range(min(5, len(tbl))):
        print(i, "->", repr(ak_decode(tbl[i])))
    # dump semua yg menarik
    kw = ("sap", "sign", "token", "risk", "sz", "enc", "key", "secret", "nonce", "hmac", "sha", "fingerprint", "af-ac")
    print("\n=== interesting strings ===")
    for i, s in enumerate(tbl):
        d = ak_decode(s)
        if any(k in d.lower() for k in kw):
            print(f"[{i}] {d[:80]}")
