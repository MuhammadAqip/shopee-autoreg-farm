#!/usr/bin/env python3
"""fpgen.py — #11: generator fingerprint + device profile lengkap & konsisten.

- shopee_webUnique_ccd format: <p1>%7C<p2>%7C<p3>%7C08%7C1  (p1|p2|p3|08|1 url-encoded)
- device profile: brand/model/android_version/resolution/UA  (konsisten per nomor)
- deterministic per phone (nomor sama → fp sama, nomor beda → fp beda) supaya stabil & unik.
"""
import hashlib, urllib.parse, random

# pool device nyata (sering muncul di traffic ID)
DEVICES = [
    {"brand": "Samsung", "model": "SM-G991B", "android": "13", "res": "1080x2400", "ua_model": "SM-G991B"},
    {"brand": "Samsung", "model": "SM-A536E", "android": "14", "res": "1080x2340", "ua_model": "SM-A536E"},
    {"brand": "Xiaomi",  "model": "2201117TG", "android": "12", "res": "1080x2400", "ua_model": "2201117TG"},
    {"brand": "Xiaomi",  "model": "M2101K7AG", "android": "13", "res": "1080x2400", "ua_model": "M2101K7AG"},
    {"brand": "Oppo",    "model": "CPH2363",  "android": "13", "res": "1080x2400", "ua_model": "CPH2363"},
    {"brand": "Oppo",    "model": "CPH2211",  "android": "12", "res": "1080x2400", "ua_model": "CPH2211"},
    {"brand": "vivo",    "model": "V2111",    "android": "13", "res": "1080x2400", "ua_model": "V2111"},
    {"brand": "realme",  "model": "RMX3630",  "android": "13", "res": "1080x2412", "ua_model": "RMX3630"},
    {"brand": "Infinix", "model": "X6819",    "android": "13", "res": "1080x2408", "ua_model": "X6819"},
    {"brand": "Redmi",   "model": "22011119U", "android": "12", "res": "1080x2400", "ua_model": "22011119U"},
    {"brand": "Google",  "model": "Pixel 7",  "android": "14", "res": "1080x2400", "ua_model": "Pixel 7"},
    {"brand": "OnePlus", "model": "CPH2451",  "android": "13", "res": "1080x2412", "ua_model": "CPH2451"},
]
BUILDS = ["", "TKQ1.221114.001", "TP1A.220624.014", "RP1A.200720.011", "SP1A.210812.016"]


def _seed(phone: str) -> int:
    return int(hashlib.md5(phone.encode()).hexdigest(), 16)


def fp_shopee_ccd(phone: str, platform: int = 1) -> str:
    """shopee_webUnique_ccd — format REAL (dari capture):
       p1 = base64(16 byte)  → 24 char, ends '=='
       p2 = base64(64 byte)  → 88 char, ends '='
       p3 = base64(12 byte)  → 16 char, no pad
       suffix |08|<platform> ; platform: 1=Android 2=iOS 3=Windows
    Deterministik per (phone, platform)."""
    import base64
    s = _seed(phone + str(platform))
    rnd = random.Random(s)
    b1 = bytes(rnd.getrandbits(8) for _ in range(16))   # → 24 char '=='
    b2 = bytes(rnd.getrandbits(8) for _ in range(64))   # → 88 char '='
    b3 = bytes(rnd.getrandbits(8) for _ in range(12))   # → 16 char
    p1 = base64.b64encode(b1).decode()
    p2 = base64.b64encode(b2).decode()
    p3 = base64.b64encode(b3).decode()
    raw = f"{p1}|{p2}|{p3}|08|{platform}"
    return urllib.parse.quote(raw, safe="")


def device_profile(phone: str) -> dict:
    """Device profile konsisten per nomor (brand/model/android/res/UA)."""
    s = _seed(phone)
    rnd = random.Random(s)
    d = dict(rnd.choice(DEVICES))
    d["build"] = rnd.choice(BUILDS)
    d["phone"] = phone
    # UA Android WebView/Chrome konsisten dgn model
    d["ua"] = (f"Mozilla/5.0 (Linux; Android {d['android']}; {d['ua_model']} "
               f"Build/{d['build'] or d['ua_model']}) AppleWebKit/537.36 "
               f"(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
    return d


def gen(phone: str) -> dict:
    return {"fingerprint": fp_shopee_ccd(phone), "device": device_profile(phone)}


if __name__ == "__main__":
    import sys, json
    ph = sys.argv[1] if len(sys.argv) > 1 else "6285602739981"
    print(json.dumps(gen(ph), indent=1))
    # bukti deterministik
    print("deterministik:", fp_shopee_ccd(ph) == fp_shopee_ccd(ph))
    print("beda utk nomor lain:", fp_shopee_ccd(ph) != fp_shopee_ccd("6285602739982"))
