#!/usr/bin/env python3
"""Shopee farm panel -- zero-dependency (http.server). Browse accounts,
filter by status, export CSV/JSON, view per-account detail.

Run:  python3 panel/app.py --port 8088
Open: http://127.0.0.1:8088
"""
import argparse
import csv
import io
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, "/root/shopee-farm")
from core.store import Store

STORE = Store()
TOKEN = os.environ.get("PANEL_TOKEN", "")   # optional ?token= guard

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Shopee Farm Panel</title>
<style>
 body{{background:#0f0d17;color:#e8e4f0;font:14px/1.5 system-ui,sans-serif;margin:0;padding:24px}}
 h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#9a92ad;margin-bottom:18px}}
 .cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}
 .card{{background:#1b1730;border:1px solid #2e2748;border-radius:10px;padding:14px 18px;min-width:110px}}
 .card b{{display:block;font-size:24px}} .card span{{color:#9a92ad;font-size:12px}}
 table{{width:100%;border-collapse:collapse;background:#161227;border-radius:10px;overflow:hidden}}
 th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid #241f3b;font-size:13px}}
 th{{background:#1e1836;color:#b9b2cf;font-weight:600}}
 tr:hover td{{background:#1d1834}}
 .pill{{padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600}}
 .s-active{{background:#1e5c3a;color:#7ef0a8}} .s-pending{{background:#5c4a1e;color:#f0d97e}}
 .s-otp_sent{{background:#1e3f5c;color:#7ec7f0}} .s-banned{{background:#5c1e1e;color:#f07e7e}}
 .s-dry{{background:#333;color:#aaa}}
 .bar{{margin-bottom:14px;display:flex;gap:8px;flex-wrap:wrap}}
 .bar a{{color:#b9b2cf;text-decoration:none;padding:5px 12px;background:#1b1730;
        border:1px solid #2e2748;border-radius:8px;font-size:12px}}
 .bar a.on{{background:#7a3a6b;color:#fff}}
 code{{background:#201a38;padding:1px 6px;border-radius:5px;font-size:12px}}
</style></head><body>
<h1>🛍️ Shopee Farm Panel</h1>
<div class="sub">total {total} akun · db <code>{db}</code></div>
<div class="cards">{cards}</div>
<div class="bar">
 <a href="/" class="{a_all}">semua</a>
 <a href="/?status=active" class="{a_act}">active</a>
 <a href="/?status=pending" class="{a_pend}">pending</a>
 <a href="/?status=otp_sent" class="{a_otp}">otp_sent</a>
 <a href="/?status=banned" class="{a_ban}">banned</a>
 <a href="/export.csv">⬇ CSV</a>
 <a href="/export.json">⬇ JSON</a>
</div>
<table><thead><tr>
 <th>#</th><th>phone</th><th>name</th><th>status</th><th>proxy</th>
 <th>token</th><th>updated</th>
</tr></thead><tbody>{rows}</tbody></table>
</body></html>"""


def esc(s):
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;")


def render(status=None):
    rows = STORE.by_status(status) if status else STORE.all()
    stats = STORE.stats()
    total = sum(stats.values())

    cards = "".join(
        f'<div class="card"><b>{n}</b><span>{esc(k)}</span></div>'
        for k, n in sorted(stats.items())
    ) or '<div class="card"><b>0</b><span>kosong</span></div>'

    body = []
    for i, r in enumerate(rows, 1):
        tok = "✅" if r.get("access_token") else "—"
        prx = (r.get("proxy") or "—")
        prx = esc(prx[:28] + ("…" if len(prx) > 28 else ""))
        st = r.get("status") or "pending"
        body.append(
            f"<tr><td>{i}</td><td>{esc(r.get('phone'))}</td>"
            f"<td>{esc(r.get('name'))}</td>"
            f'<td><span class="pill s-{esc(st)}">{esc(st)}</span></td>'
            f"<td><code>{prx}</code></td><td>{tok}</td>"
            f"<td>{esc(time_str(r.get('updated_at')))}</td></tr>"
        )
    rows_html = "".join(body) or '<tr><td colspan="7">tidak ada data</td></tr>'

    q = status or ""
    return PAGE.format(
        total=total, db=esc(STORE.db), cards=cards, rows=rows_html,
        a_all="on" if not status else "",
        a_act="on" if q == "active" else "",
        a_pend="on" if q == "pending" else "",
        a_otp="on" if q == "otp_sent" else "",
        a_ban="on" if q == "banned" else "",
    )


def time_str(ts):
    import datetime
    if not ts:
        return "—"
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _auth_ok(self, qs):
        if not TOKEN:
            return True
        return qs.get("token", [""])[0] == TOKEN

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        if not self._auth_ok(qs):
            self.send_response(401); self.end_headers(); self.wfile.write(b"401"); return

        if u.path == "/export.csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["phone", "password", "name", "email", "status",
                        "access_token", "proxy", "created_at"])
            for r in STORE.all():
                w.writerow([r.get("phone"), r.get("password"), r.get("name"),
                            r.get("email"), r.get("status"), r.get("access_token"),
                            r.get("proxy"), time_str(r.get("created_at"))])
            data = buf.getvalue().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", "attachment; filename=shopee_accounts.csv")
            self.end_headers(); self.wfile.write(data); return

        if u.path == "/export.json":
            data = json.dumps(STORE.all(), indent=2, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Disposition", "attachment; filename=shopee_accounts.json")
            self.end_headers(); self.wfile.write(data); return

        status = qs.get("status", [None])[0]
        html = render(status).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers(); self.wfile.write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8088)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[panel] http://{args.host}:{args.port}  ({STORE.db})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
