#!/usr/bin/env python3
"""sense_serialize.py — port penuh serializer Sense SDK (bisa FORGE payload).

Dari reverse 8094.<hash>.2023.js:
  - writeUint8/16/32, writeInt16/32/64, writeString, writeRaw, toUint8Array
  - event tags: page_view:1, move:2, keydown:3, keyup:4, click:5, scroll:6, fetch:7
  - device_info: trace_id, start_time, platform, sapid, dfp, report_time, report_count,
                 report_type, region, location_href, event_counts, first_input,
                 has_been_active, storage_search_history, performance_time_origin, ...

Dipakai buat: build payload Sense yg valid (encrypt → kirim ke shpsec/web/report).
"""
import struct, zlib, time, base64, json
from sense_decrypt import build_payload, KEY, IV, VERSION

# tag enum
C = {"page_view": 1, "move": 2, "keydown": 3, "keyup": 4, "click": 5, "scroll": 6, "fetch": 7}


class W:
    """writer biner (little-endian) sesuai Sense"""
    def __init__(self):
        self.b = bytearray()

    def u8(self, v): self.b += struct.pack(">B", v & 0xFF); return self
    def u16(self, v): self.b += struct.pack(">H", v & 0xFFFF); return self
    def u32(self, v): self.b += struct.pack(">I", v & 0xFFFFFFFF); return self
    def i16(self, v): self.b += struct.pack(">h", v); return self
    def i32(self, v): self.b += struct.pack(">i", v); return self
    def i64(self, v): self.b += struct.pack(">q", v); return self

    def string(self, s):
        s = (s or "").encode("utf-8")
        self.i16(len(s)); self.b += s; return self

    def raw(self, b): self.b += b; return self
    def out(self): return bytes(self.b)


def _ev(ev):
    """serialize satu event → bytes (dgn i16 length prefix)"""
    w = W()
    t = ev.get("type")
    if t == "page_view":
        w.u8(C["page_view"]).i64(ev.get("timestamp", 0)).string(ev.get("url", ""))
    elif t == "move":
        w.u8(C["move"])
        inner = W()
        for pt in ev.get("mouse_events", []):
            x, y, ts = pt[0], pt[1], pt[2]
            inner.i32(x).i32(y).i64(ts)
            if len(pt) > 3 and pt[3]:  # touch?
                pass
        w.u16(len(ev.get("mouse_events", [])))
        w.raw(inner.out())
    elif t in ("keydown", "keyup"):
        w.u8(C[t]).i64(ev.get("timestamp", 0)).u16(ev.get("key_code", 0)).string(ev.get("v", ""))
    elif t == "click":
        w.u8(C["click"]).i64(ev.get("timestamp", 0)) \
         .i32(ev.get("x", 0)).i32(ev.get("y", 0)) \
         .i32(ev.get("screen_x", 0)).i32(ev.get("screen_y", 0)) \
         .string(ev.get("target", ""))
    elif t == "scroll":
        w.u8(C["scroll"]).i64(ev.get("timestamp", 0)).u8(ev.get("percent", 0))
    elif t == "fetch":
        w.u8(C["fetch"]).i64(ev.get("request_timestamp", 0)).string(ev.get("url", ""))
    raw = w.out()
    return struct.pack(">h", len(raw)) + raw


def serialize_events(events):
    w = W()
    for e in events:
        w.raw(_ev(e))
    return w.out()


def serialize_device(dev):
    """device_info sesuai urutan di fungsi s()"""
    w = W()
    w.string(dev.get("trace_id", ""))
    w.i64(dev.get("start_time", 0))
    w.string(dev.get("platform", "pc"))
    w.string(dev.get("sapid", ""))
    w.string(dev.get("dfp", ""))
    w.i64(dev.get("report_time", 0))
    w.i16(dev.get("report_count", 1))
    w.u8(dev.get("report_type", 0))
    w.string(dev.get("region", ""))
    w.string(dev.get("location_href", ""))
    w.string(dev.get("event_counts", ""))
    w.string(dev.get("first_input", ""))
    w.u8(dev.get("has_been_active", 1))
    w.string(dev.get("storage_search_history", ""))
    w.i64(dev.get("performance_time_origin", 0))
    return w.out()


def forge(events, device):
    ev_bytes = serialize_events(events)
    dev_bytes = serialize_device(device)
    payload = build_payload(ev_bytes, dev_bytes, VERSION)
    return payload


if __name__ == "__main__":
    now = int(time.time() * 1000)
    evs = [
        {"type": "page_view", "timestamp": now, "url": "https://shopee.co.id/buyer/signup"},
        {"type": "move", "mouse_events": [[100, 200, now], [120, 210, now + 20], [140, 220, now + 40]]},
        {"type": "click", "timestamp": now + 100, "x": 300, "y": 400, "screen_x": 300, "screen_y": 500, "target": "BUTTON"},
        {"type": "scroll", "timestamp": now + 200, "percent": 12},
        {"type": "fetch", "request_timestamp": now + 300, "url": "/api/v4/otp/get_settings_v2"},
    ]
    dev = {
        "trace_id": "test-trace-0001", "start_time": now - 5000, "platform": "pc",
        "sapid": "", "dfp": "", "report_time": now, "report_count": 1, "report_type": 1,
        "region": "", "location_href": "https://shopee.co.id/buyer/signup",
        "event_counts": str(len(evs)), "first_input": "", "has_been_active": 1,
        "storage_search_history": "", "performance_time_origin": now - 8000,
    }
    p = forge(evs, dev)
    print("forged payload len:", len(p))
    print("head hex:", p[:16].hex())
    # roundtrip verify
    import sense_decrypt as S
    r = S.parse_payload(p)
    print("parse:", {k: r.get(k) for k in ("crc_ok", "version", "len_events", "len_device")})
    ev_p = S.aes_cbc_decrypt(r["events_bytes"])
    print("events decoded len:", len(ev_p), "first tag:", ev_p[2] if len(ev_p) > 2 else None)
