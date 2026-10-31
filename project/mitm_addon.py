"""
mitmproxy addon — capture Shopee signup/OTP/API flow to JSONL.

Run:
  mitmdump -s shopee_capture.py --listen-port 8080 \
           --set flow_detail=0 -w flows.dump

Then point a browser/phone at <host>:8080 with the mitmproxy CA installed.

Captures every shopee.co.id/api/* call: method, url, headers (incl. the
encrypted anti-bot headers), request body, response body.
Writes: shopee_capture.jsonl (one JSON per line)
"""
import json
import time
from mitmproxy import http

OUT = "/root/shopee-farm/shopee_capture.jsonl"
TARGETS = ("shopee.co.id/api/", "/api/v4/", "/api/v2/")

def _w(rec):
    with open(OUT, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

class ShopeeCapture:
    def request(self, flow: http.HTTPFlow):
        u = flow.request.pretty_url
        if any(t in u for t in TARGETS):
            hdrs = {k: v for k, v in flow.request.headers.items()}
            rec = {
                "t": time.strftime("%H:%M:%S"),
                "dir": "REQ",
                "method": flow.request.method,
                "url": u.split("?")[0],
                "headers": hdrs,
                "body": flow.request.get_text()[:2000] if flow.request.content else "",
            }
            _w(rec)
            # log the interesting bits to console
            fp = hdrs.get("af-ac-enc-dat", "")
            csrf = hdrs.get("x-csrftoken", hdrs.get("x-csrf-token", ""))
            print(f"[REQ] {flow.request.method:4s} {u.split('?')[0]}"
                  f"  csrf={csrf[:8]}  af-ac={fp[:8]}")

    def response(self, flow: http.HTTPFlow):
        u = flow.request.pretty_url
        if any(t in u for t in TARGETS):
            body = ""
            try:
                body = flow.response.get_text()[:2000]
            except Exception:
                body = "<binary>"
            rec = {
                "t": time.strftime("%H:%M:%S"),
                "dir": "RESP",
                "status": flow.response.status_code,
                "url": u.split("?")[0],
                "body": body,
            }
            _w(rec)
            print(f"[RESP] {flow.response.status_code} {u.split('?')[0]}  {body[:90]}")

addons = [ShopeeCapture()]
