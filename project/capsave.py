#!/usr/bin/env python3
"""capsave.py — mitmproxy addon: rekam SEMUA traffic Shopee ke JSONL.
Dipakai: mitmdump -s capsave.py -p 8888 --set confdir=/root/.mitmproxy
Output: /root/shopee-farm/capture/shopee_YYYYmmdd_HHMMSS.jsonl
"""
import os, json, time, gzip, base64

OUT_DIR = "/root/shopee-farm/capture"
os.makedirs(OUT_DIR, exist_ok=True)
STAMP = time.strftime("%Y%m%d_%H%M%S")
OUT = os.path.join(OUT_DIR, f"shopee_{STAMP}.jsonl")

# endpoint penting yang wajib kelihatan lengkap
KEY_HINTS = ("signup", "otp", "vcode", "verify", "password", "login", "register",
             "user", "sms", "whatsapp", "wa_", "account", "captcha", "risk",
             "sap", "sec", "anti", "identify")

_denylist = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".woff", ".woff2",
             ".ttf", ".mp4", ".css", ".svg", ".ico")


def _body_text(flow):
    try:
        b = flow.request.content
    except Exception:
        return None, None
    if b is None:
        return None, None
    enc = flow.request.headers.get("content-encoding", "")
    try:
        if "gzip" in enc:
            b = gzip.decompress(b)
        return b.decode("utf-8", "replace"), "text"
    except Exception:
        return base64.b64encode(b).decode()[:2000], "b64"


def _resp_text(flow):
    try:
        b = flow.response.content
    except Exception:
        return None
    if b is None:
        return None
    enc = flow.response.headers.get("content-encoding", "")
    try:
        if "gzip" in enc:
            b = gzip.decompress(b)
        return b.decode("utf-8", "replace")[:6000]
    except Exception:
        return base64.b64encode(b).decode()[:2000]


def response(flow):
    host = flow.request.pretty_host
    if "shopee" not in host and "susercontent" not in host:
        return
    url = flow.request.pretty_url
    if any(url.lower().split("?")[0].endswith(d) for d in _denylist):
        return
    path = flow.request.path.split("?")[0]
    is_key = any(h in path.lower() for h in KEY_HINTS)
    body, _ = _body_text(flow)
    rec = {
        "t": round(time.time(), 3),
        "method": flow.request.method,
        "host": host,
        "path": path,
        "query": flow.request.url.split("?", 1)[1] if "?" in flow.request.url else "",
        "status": getattr(flow.response, "status_code", None),
        "key": is_key,
        "req_headers": dict(flow.request.headers),
        "req_body": body,
        "resp_headers": dict(flow.response.headers) if flow.response else {},
        "resp_body": _resp_text(flow),
    }
    # hanya simpan yang penting + POST + api path (jangan spam static)
    if not (is_key or flow.request.method in ("POST", "PUT") or "/api/" in path):
        return
    with open(OUT, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if is_key:
        try:
            print(f"[CAP] {flow.request.method} {path} -> {rec['status']}", flush=True)
        except Exception:
            pass
