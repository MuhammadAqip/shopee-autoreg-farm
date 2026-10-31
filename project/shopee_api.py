#!/usr/bin/env python3
"""Shopee Captcha — Pure-API flow (RSA-1024).

Replikasi chain signup TANPA browser kecuali geometry puzzle.
RSA public key dari bundle → encrypt payload sendiri.

Usage: shopee_api.py <PHONE> <DEVICE_FINGERPRINT>
"""
import sys, time, json, base64, requests

BASE = "https://shopee.co.id"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# ---- RSA-1024 dari bundle.a95de02.js ----
MOD_HEX = open("/root/shopee-farm/rsa_modulus.txt").read().strip()
N = int(MOD_HEX, 16)
E = 65537
K = (N.bit_length() + 7) // 8


def rsa_encrypt(data: bytes) -> str:
    """PKCS#1 v1.5 encrypt → base64 (kompatibel jsencrypt)."""
    if len(data) > K - 11:
        raise ValueError(f"payload too long: {len(data)} > {K-11}")
    ps = b'\xff' * (K - len(data) - 3)
    em = b'\x00\x01' + ps + b'\x00' + data
    c = pow(int.from_bytes(em, 'big'), E, N)
    return base64.b64encode(c.to_bytes(K, 'big')).decode()


class ShopeeAPI:
    def __init__(self, fingerprint: str):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://shopee.co.id/buyer/signup",
        })
        self.s.cookies.set("shopee_webLanguage", "id", domain=".shopee.co.id")
        self.fp = fingerprint
        self.tracking_id = None
        self.captcha_id = None

    def get_settings_v2(self, phone: str):
        payload = {
            "operation": 8, "encrypted_phone": "", "phone": phone,
            "supported_channels": [1, 2, 3, 6, 0, 5], "support_session": True,
            "client_identifier": {"security_device_fingerprint": self.fp},
        }
        r = self.s.post(f"{BASE}/api/v4/otp/get_settings_v2", json=payload)
        return r.json()

    def get_captcha_config(self, request_id: str):
        payload = {"app_key": "User.PC", "scene": "signup", "platform": "pc",
                   "request_id": request_id, "captcha_id": ""}
        r = self.s.post(f"{BASE}/api/v4/anti_fraud/captcha/get_config", json=payload)
        j = r.json()
        self.tracking_id = j.get("tracking_id")
        return j

    def captcha_generate(self, inner: dict):
        """inner = plaintext dict → RSA encrypt → POST"""
        enc = rsa_encrypt(json.dumps(inner, separators=(",", ":")).encode())
        r = self.s.post(f"{BASE}/api/v4/anti_fraud/captcha/generate",
                        json={"encrypted_data": enc})
        return r.json()


if __name__ == "__main__":
    phone = sys.argv[1] if len(sys.argv) > 1 else "6287764912714"
    fp = sys.argv[2] if len(sys.argv) > 2 else "0eYAWjMQ5cKpMWN37UxHVjyitqpxRp9h"
    api = ShopeeAPI(fp)
    print("== get_settings_v2 ==")
    j = api.get_settings_v2(phone)
    print(json.dumps(j, indent=1)[:600])
    print("\n== get_captcha_config ==")
    req_id = base64.urlsafe_b64encode(__import__("os").urandom(18)).decode().rstrip("=")
    j2 = api.get_captcha_config(req_id)
    print(json.dumps(j2, indent=1)[:400])
    print("\ntracking_id:", (api.tracking_id or "")[:50])
    print("RSA ready: modulus", N.bit_length(), "bits")
