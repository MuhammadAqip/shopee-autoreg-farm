#!/usr/bin/env python3
"""sense_decrypt.py — reimplementasi Sense SDK (Shopee anti-fraud) di Python.

Dari reverse 8094.<hash>.2023.js:
  - AES-128-CBC, key="SenseTestKey1234", iv="SenseTestIV12345", PKCS7
  - payload = byte(crc32(payload)&0xFF) + u32(version) + s16(len(enc_ev)) + enc_ev + s16(len(enc_dev)) + enc_dev
  - enc_ev/enc_dev = AES-CBC(serialized protobuf binary)

Kemampuan:
  decrypt(payload_bytes) → {version, events_bytes, device_bytes}  (utk inspeksi)
  encrypt(events, device, version) → payload_bytes                (utk forge request)
"""
import sys, os, struct, zlib, json
from base64 import b64encode

KEY = b"SenseTestKey1234"
IV = b"SenseTestIV12345"
VERSION = 1001000

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as _pad
    HAVE_CRYPTO = True
except Exception:
    HAVE_CRYPTO = False


def _pkcs7_pad(b, blk=16):
    p = blk - (len(b) % blk)
    return b + bytes([p]) * p


def _pkcs7_unpad(b, blk=16):
    if not b:
        return b
    p = b[-1]
    if 1 <= p <= blk and b[-p:] == bytes([p]) * p:
        return b[:-p]
    return b


def aes_cbc_encrypt(data, key=KEY, iv=IV):
    if HAVE_CRYPTO:
        padder = _pad.PKCS7(128).padder(); d = padder.update(data) + padder.finalize()
        enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        return enc.update(d) + enc.finalize()
    # fallback tanpa cryptography → pakai pure-python AES (lihat pure_aes.py)
    from pure_aes import aes_cbc_encrypt as pa
    return pa(data, key, iv)


def aes_cbc_decrypt(data, key=KEY, iv=IV):
    if HAVE_CRYPTO:
        dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        d = dec.update(data) + dec.finalize()
        return _pkcs7_unpad(d)
    from pure_aes import aes_cbc_decrypt as pa
    return pa(data, key, iv)


PREFIX = b"\x75\xab\x5a"   # magic 3-byte (konstan di semua body live)


def build_payload(events_bytes, device_bytes, version=VERSION):
    enc_ev = aes_cbc_encrypt(events_bytes)
    enc_dev = aes_cbc_encrypt(device_bytes)
    body = struct.pack(">I", version) + struct.pack(">h", len(enc_ev)) + enc_ev \
           + struct.pack(">h", len(enc_dev)) + enc_dev
    crc_lo = zlib.crc32(body) & 0xFF
    return PREFIX + bytes([crc_lo]) + body


def parse_payload(payload):
    """Framing TERVERIFIKASI (28/28 body live /web/subcart):
    [3B magic 75 ab 5a][1B crc32(body)&0xFF][u32 version BE][i16 len_ev BE][enc_ev][i16 len_dev BE][enc_dev]
    """
    out = {"prefix": payload[:3].hex() if len(payload) >= 3 else None}
    if len(payload) < 12:
        return out
    out["magic_ok"] = (payload[:3] == PREFIX)
    out["crc_byte"] = payload[3]
    body = payload[4:]
    out["crc_ok"] = (zlib.crc32(body) & 0xFF) == out["crc_byte"]
    version = struct.unpack(">I", body[:4])[0]
    le = struct.unpack(">h", body[4:6])[0]
    enc_ev = body[6:6+le]
    rest = body[6+le:]
    ld = struct.unpack(">h", rest[:2])[0] if len(rest) >= 2 else 0
    enc_dev = rest[2:2+ld]
    out.update({"version": version, "len_events": le, "len_device": ld})
    try:
        out["events_bytes"] = enc_ev
        out["device_bytes"] = enc_dev
        out["events_plain_len"] = len(aes_cbc_decrypt(enc_ev))
        out["device_plain_len"] = len(aes_cbc_decrypt(enc_dev))
    except Exception as e:
        out["decrypt_err"] = str(e)
    return out


if __name__ == "__main__":
    print("KEY:", KEY, "IV:", IV, "HAVE_CRYPTO:", HAVE_CRYPTO)
    # self-test: encrypt sample lalu decrypt balik
    ev = b"\x01" + struct.pack("<q", 1792094590) + b"https://shopee.co.id/buyer/signup"
    dev = b"test_device_info_blob"
    p = build_payload(ev, dev)
    print("payload len:", len(p), "head:", p[:8].hex())
    pr = parse_payload(p)
    print("parse:", {k: pr[k] for k in pr if k not in ("events_bytes", "device_bytes")})
    print("roundtrip events ok:", aes_cbc_decrypt(aes_cbc_encrypt(ev)) == ev)
    print("-> encrypt/decrypt WORKS" if pr.get("crc_ok") else "-> CRC mismatch")
