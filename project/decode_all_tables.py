#!/usr/bin/env python3
"""decode_all_tables.py — decode SEMUA string table obfuscated di sfu-stable.js.

Menemukan `aj()` + `ae()` (dan mungkin lainnya), decode dgn alphabet masing-masing,
tulis hasil ke sdk/strings_decoded.txt. Ini memetakan SEMUA string tersembunyi SAP SDK.

Terverifikasi: aj()->"exports", ae()->"getShaderPrecisionFormat".
"""
import re, urllib.parse, sys, os

TABLES = [
    ("aj", "ofksgblrxcamqiunzpthjwydevYDSVHBOZKWEGFXCMINTJARQLPU1357249806+/="),
    ("ae", "evdqphkgrfmiotbyjlxczanswuTMBGWXRCAEPIZNHFLUDSVKOQJY4912758063+/="),
]


def decode(s, alpha):
    T = {c: i for i, c in enumerate(alpha)}
    b = 0; c = 0; out = bytearray()
    for ch in s:
        fv = T.get(ch)
        if fv is None:
            continue
        b = b * 64 + fv if c % 4 else fv
        c += 1
        if c % 4 == 0:
            out += bytes([(b >> 16) & 0xFF, (b >> 8) & 0xFF, b & 0xFF])
    r = c % 4
    if r == 2:
        out.append((b >> 4) & 0xFF)
    elif r == 3:
        out += bytes([(b >> 10) & 0xFF, (b >> 2) & 0xFF])
    return urllib.parse.unquote("".join("%%%02x" % x for x in out))


def extract(js_path, fn_name):
    src = open(js_path, encoding="utf-8", errors="replace").read()
    m = re.search(r"function " + fn_name + r"\(\)\{return\[(.*?)\]\}", src, re.S)
    if not m:
        return []
    return re.findall(r'"([^"]*)"', m.group(1))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else \
        "/tmp/sap_analysis/bile.com_shopee_shopee-pcmall-live-sg_assets_sfu-stable.c3d38f8e0e81e513.2023.js.js"
    out = sys.argv[2] if len(sys.argv) > 2 else "/root/shopee-farm/sdk/strings_decoded.txt"
    lines = []
    for fn, alpha in TABLES:
        tbl = extract(path, fn)
        lines.append(f"=== table {fn}() — {len(tbl)} strings ===")
        for i, s in enumerate(tbl):
            lines.append(f"[{fn}:{i}] {decode(s, alpha)}")
        lines.append("")
    open(out, "w").write("\n".join(lines))
    print("wrote", out, "lines:", len(lines))
