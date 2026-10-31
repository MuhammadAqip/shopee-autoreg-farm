#!/usr/bin/env python3
"""sense_cli.py — CLI: decrypt/forge payload Sense (Shopee anti-fraud).

Terverifikasi pada body live POST /api/v4/web/subcart & /v2/shpsec/web/report.

Usage:
  sense_cli.py dec <file|b64>        # decrypt payload → dump events+device
  sense_cli.py dec-har <har>         # decrypt semua body Sense di HAR
  sense_cli.py forge <out.bin>       # contoh forge payload (sample events)
  sense_cli.py sniff <jsonl>         # scan jsonl cari body Sense, decrypt
"""
import sys, os, json, base64, struct, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sense_decrypt as S

VERSION = 1001000


def find_sense_bodies(text_b64_list):
    """dari list string base64, ambil yg mengandung version marker"""
    out = []
    for b64 in text_b64_list:
        if not b64:
            continue
        try:
            pad = "=" * ((4 - len(b64) % 4) % 4)
            raw = base64.b64decode(b64 + pad)
        except Exception:
            continue
        if b"\x00\x0f\x46\x28" in raw:
            out.append(raw)
    return out


def dump(raw):
    r = S.parse_payload(raw)
    print(f"  crc_ok={r.get('crc_ok')} version={r.get('version')} len_ev={r.get('len_events')} len_dev={r.get('len_device')}")
    if r.get("events_bytes") is not None:
        ev = S.aes_cbc_decrypt(r["events_bytes"])
        dv = S.aes_cbc_decrypt(r["device_bytes"])
        print(f"  EVENTS ({len(ev)}B): {ev[:200]}")
        print(f"  DEVICE ({len(dv)}B): {dv[:300]}")
    return r


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "dec" and arg:
        if os.path.exists(arg):
            raw = open(arg, "rb").read()
        else:
            raw = base64.b64decode(arg + "=" * ((4 - len(arg) % 4) % 4))
        print(f"payload {len(raw)}B"); dump(raw)

    elif cmd == "dec-har" and arg:
        h = json.load(open(arg))
        n = 0
        for e in h["log"]["entries"]:
            txt = e["request"].get("postData", {}).get("text", "")
            if not txt:
                continue
            for raw in find_sense_bodies([txt]):
                n += 1
                print(f"[{e['request']['url'][:70]}]")
                dump(raw)
        print("total Sense bodies:", n)

    elif cmd == "sniff" and arg:
        n = 0
        for line in open(arg):
            try:
                d = json.loads(line)
            except Exception:
                continue
            b64 = d.get("postData")
            if not b64 or not isinstance(b64, str):
                continue
            for raw in find_sense_bodies([b64]):
                n += 1
                print(f"[{d.get('url','')[:70]}]")
                dump(raw)
                if n >= 5:
                    break
        print("total Sense bodies:", n)

    elif cmd == "forge" and arg:
        import sense_serialize as SS
        import time
        now = int(time.time() * 1000)
        evs = [{"type": "page_view", "timestamp": now, "url": "https://shopee.co.id/buyer/signup"}]
        dev = {"trace_id": "cli-0001", "start_time": now - 3000, "platform": "pc",
               "report_time": now, "report_count": 1, "report_type": 1,
               "location_href": "https://shopee.co.id/buyer/signup", "has_been_active": 1}
        p = SS.forge(evs, dev)
        open(arg, "wb").write(p)
        print(f"forged {len(p)}B → {arg}"); dump(p)

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
