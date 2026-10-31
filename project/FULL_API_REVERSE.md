# Shopee Captcha — FULL REVERSE (endpoint + crypto)

**Sumber:** `captures/session_83181186013_1792046730.json` (31 request) + `session_87764912714_*.json` (17 req)

---

## Chain API lengkap (terverifikasi live)

```
 1. GET  /api/v4/account/subaccount            200  {"data":"OK"}
 2. POST /api/v4/abtest/traffic/get_web_experiments   (device_fingerprint)
 3. POST /api/v4/web/subcart                   200  (anti-bot beacon, berulang)
 4. POST /api/v4/otp/get_settings_v2           200  plaintext → need_captcha
 5. POST /api/v4/anti_fraud/captcha/get_config 200  plaintext → bundle_url, tracking_id
 6. GET  bundle.a95de02.js                     200  (SDK 799KB)
 7. POST /api/v4/anti_fraud/captcha/generate   200  {encrypted_data: "U2FsdGVkX1..."}
 8. POST /api/v4/anti_fraud/captcha/feedback/questions  200
 9. POST /api/v4/anti_fraud/captcha/verify_v2  200  {security_data: "ByQBAAAA..."}  ← KUNCI!
10. POST /api/v4/otp/send_otp                           (setelah verify sukses)
```

## Dua format kripto BERBEDA

| Field | Format | Isi |
|---|---|---|
| `encrypted_data` (generate) | `U2FsdGVkX1...` = base64 "Salted__" | AES CryptoJS |
| `security_data` (verify_v2) | `ByQBAAAA...` = byte `07 24 01 00 00 00...` | TLV wrapper + AES nested |

### `security_data` structure (decode from base64)
```
offset 0:  07 24 01 00 00 00     magic 0x07, ver 0x0124 (LE)
offset 6:  01 00 00 00             field A (int)
offset 10: 80 00 00 00             field B (int)
offset 14: <varint fields...>      protobuf-like TLV
offset 36: 0d "U2FsdGVkX1..."      AES blob (tag 0x0d + length)
```
**Header = custom protobuf TLV**, payload AES ter-nest.

### `encrypted_data` (generate) — CryptoJS AES
```python
raw = base64.b64decode(encrypted_data)
assert raw[:8] == b"Salted__"
salt = raw[8:16]
ct   = raw[16:]
key, iv = EVP_BytesToKey(MD5, passphrase, salt, 32, 16)
plaintext = AES-256-CBC(key, iv).decrypt(ct)
```

### RSA-1024 (bundle)
Fungsi `D(t)` di bundle = RSA encrypt (public):
```
modulus 1024-bit → rsa_modulus.txt
exponent 0x010001
```

---

## ⚠️ KENAPA PURE-API PENUH = MUSTAHIL (temuan final)

Bukan sekadar "AES obfuscated". Akar masalahnya **3 lapis anti-bot**:

### (1) AES key RANDOM per-request, dikirim ter-RSA
Decompile `bundle.js` offset 295520:
```js
randomString: r = hw(8,12)          // random 8-12 char
aesKey:       i = nQ(16)            // AES key RANDOM 16 byte
encryptKeyValue: a = Gt(i)          // = D(i) = RSA-encrypt(aesKey)
// payload = AES-CBC(data, aesKey)  ← key TIDAK diketahui client luar
```
RSA publik bikin enkripsi bisa direplikasi, **tapi AES key di-generate acak saat runtime** dan hanya dikirim ter-enkripsi. Tanpa private key server → mustahil decrypt/replika.

### (2) SAP anti-fraud headers (sz-sdk native)
```
af-ac-enc-sz-token : token dari sz-sdk (browser fingerprint native)
x-sap-ri           : 52 hex  = request signature
x-sap-sec          : 120 char base64 = signature
x-sap-ri + x-sap-sec di-generate oleh sz-sdk (JS + WASM)
```
Tanpa header ini → anti_fraud endpoint balikin 400. **Tak bisa dilipat tanpa port sz-sdk.**

### (3) Geometry captcha = surface tertutup
Puzzle digambar di SDK internal; butuh render browser + SadCaptcha.

### Kesimpulan persentase
| Bagian | Bisa API murni? |
|---|---|
| get_settings_v2 | ✅ |
| get_captcha_config | ✅ |
| feedback/questions | ✅ |
| captcha/generate | ❌ (AES+random key+SAP) |
| captcha/verify_v2 | ❌ (AES+random key+SAP) |
| geometry solve | ❌ (browser) |
| send_otp | ⚠️ butuh captcha_token valid (dari verify) |

→ **Sebagian besar chain (generate→verify) WAJIB lewat browser** karena butuh proof-of-execution sz-sdk.

---

## Artefak
- `shopee_api.py` — pure-API client (get_settings_v2 + get_config JALAN, no browser)
- `rsa_modulus.txt` — RSA public key (1024-bit)
- `bundle.js` — SDK asli
- `captures/session_*.json` — semua endpoint (48 total dari 2 sesi)
- `API_REVERSE_RUNBOOK.md`, `CRYPTO_RSA_RESULTS.md`

## Status pure-API (B)
- [x] get_settings_v2 tanpa browser ✅
- [x] get_config tanpa browser ✅
- [x] RSA modulus diekstrak ✅
- [x] Struktur security_data decoded ✅
- [ ] AES passphrase (perlu deobfuscate bundle) ⬜
- [ ] TLV schema (perlu sample lebih banyak) ⬜
- [ ] Full send_otp tanpa browser ⬜
