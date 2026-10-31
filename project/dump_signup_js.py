#!/usr/bin/env python3
"""dump_signup_js.py — extract endpoint + payload dari bundle SignupByOTP.js pakai mitm capture.
Cari string /api/... signup_by_otp, verify_otp, set password.
"""
import json, re, sys, os

CAP = "/root/shopee-farm/capture"
files = sorted([f for f in os.listdir(CAP) if f.endswith(".jsonl")])
urls = set()
for f in files:
    for l in open(os.path.join(CAP, f)):
        try:
            d = json.loads(l)
        except Exception:
            continue
        p = d.get("path", "")
        if ".js" in p:
            urls.add(p)

print("=== JS bundles captured ===")
for u in sorted(urls):
    print(" ", u)
print()
# look for api paths in captured request bodies / responses
apis = set()
for f in files:
    for l in open(os.path.join(CAP, f)):
        try:
            d = json.loads(l)
        except Exception:
            continue
        for blob in (d.get("path", ""), d.get("resp_body") or "", d.get("req_body") or ""):
            for m in re.finditer(r"/api/v[0-9]+/[a-zA-Z0-9_/{}.-]+", str(blob)):
                apis.add(m.group(0))
print("=== API paths found ===")
for a in sorted(apis):
    print(" ", a)
