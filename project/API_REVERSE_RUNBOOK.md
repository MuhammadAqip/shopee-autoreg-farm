# Shopee Signup — FULL API REVERSE (pure-API replikasi)

**Sumber:** capture live `captures/session_87764912714_1792045581.json` (17 request)
**Nomor uji:** 6287764912714 · Proxy ID `gb.vsproxy.org:10000`

---

## Arsitektur: kenapa captcha butuh browser

Shopee **mengunci 2 layer**:
1. **Payload `encrypted_data`** — AES-CBC/`U2FsdGVkX1` (CryptoJS OpenSSL format) di-sign oleh bundle SDK
2. **Captcha geometry** — puzzle dirender di **surface tertutup SDK** (bukan DOM/img/canvas biasa)

`U2FsdGVkX1...` = **CryptoJS `CryptoJS.AES.encrypt`** default (OpenSSL salted format: `Salted__` + 8-byte salt). Key diturunkan `EVP_BytesToKey(MD5, salt, passphrase)`.

→ Tanpa browser, kita musti re-implement AES key-exchange + signature. Endpoint sisanya (get_settings_v2) **cukup plaintext** — yang terenkripsi cuma `captcha/generate` + `captcha/verify`.

---

## Chain API (pure-API, browser hanya untuk captcha drag)

### 1. `POST /api/v4/otp/get_settings_v2` — PLAINTEXT ✅
```json
{
  "operation": 8,
  "encrypted_phone": "",
  "phone": "6287764912714",
  "supported_channels": [1,2,3,6,0,5],
  "support_session": true,
  "client_identifier": {
    "security_device_fingerprint": "<b64|b64|b64_short>|<ver>|<ver>"
  }
}
```
Respons:
```json
{"error":0,"data":{
  "need_login":false,"need_captcha":true,"captcha_scene":"signup",
  "masked_phone":"","preferred_channel":3,
  "available_channels":[3,2,1],"hidden_available_channels":[2],
  "skip_channel_confirmation":false,"flow_name":"default_flow",
  "session_info":{"seed":"ecf47c00-...","remaining_resend_cooldown_sec":0,"remaining_switch_cooldown_sec":0},
  "captcha_app_key":"User.PC","captcha_id":""}}
```

**Fingerprint format:** `<b64>|<b64>|<b64>|<int>|<int>` — 3 komponen base64 + 2 angka. Generate dari SDK device fingerprint. Bisa di-reuse selama ga di-flag.

### 2. `POST /api/v4/anti_fraud/captcha/get_config` — PLAINTEXT ✅
```json
{"app_key":"User.PC","scene":"signup","platform":"pc",
 "request_id":"<24-char alnum>","captcha_id":""}
```
Respons: `bundle_url` + `style_url` + `tracking_id` (server-side session).

### 3. `POST /api/v4/anti_fraud/captcha/generate` — **ENCRYPTED** 🔒
```json
{"encrypted_data":"U2FsdGVkX1..."}
```
Respons: `encrypted_data` (berisi gambar puzzle + captcha_id).

**Crypto:** CryptoJS AES (OpenSSL KDF). Key material dari `bundle.a95de02.js`.

### 4. `POST /api/v4/anti_fraud/captcha/feedback/questions` — PLAINTEXT ✅
```json
{"app_key":"User.PC","scene":"signup","captcha_id":"YWR2YW5jZWRfc2xpZGVyOjE3...","tracking_id":"...","audio":false}
```
`captcha_id` = base64 dari `advanced_slider:<epoch_nanos><random>`.

### 5. `POST /api/v4/anti_fraud/captcha/verify` — **ENCRYPTED** 🔒
(solve → token) — dapet dari drag.

### 6. `POST /api/v4/otp/send_otp` — dengan captcha token
Trigger WA/SMS.

---

## 🔑 Crypto re-implementation note

`bundle.a95de02.js` — cari: `CryptoJS`, `AES`, `encrypt`, `sig`, `secret`, `key`.

Format `U2FsdGVkX1` (base64 "Salted__"):
```
decoded = base64decode(data)   # "Salted__" | 8-byte salt | ciphertext
key, iv = EVP_BytesToKey(MD5, passphrase, salt, keyLen=32, ivLen=16)
plaintext = AES-256-CBC(key, iv).decrypt(ciphertext)
```

**Passphrase** = didapat dari bundle (kemungkinan hardcoded atau dari `get_config` tracking_id).

---

## Yang browser masih dibutuhkan

| Layer | Pure-API? | Catatan |
|---|---|---|
| get_settings_v2 | ✅ | plaintext penuh |
| get_config | ✅ | plaintext |
| captcha/generate | 🔒 | AES — perlu key dari bundle |
| **captcha geometry (drag)** | ❌ | surface tertutup — wajib browser |
| captcha/verify | 🔒 | AES + trajectory |
| send_otp | ✅* | butuh captcha token dari solve |

→ **Hybrid optimal:** browser HANYA untuk solve captcha (SadCaptcha API + drag), sisanya API langsung. Ini yang bikin "ga pake browser" ga fully possible — tapi bisa **90% API**.

---

## Artefak capture

- `captures/session_*.json` — 17 endpoint (method, url, post, status, response, headers)
- `sniff_A.json` / `sniff_A7.json` — capture lama (device_fingerprint, experiments)
- `captured_tokens.json` — token tersimpan

## Update v6 (patched sesi ini)
- Full network capture built-in → `captures/session_<phone>_<ts>.json`
- `fill_otp` / `fill_password` / `click_lanjut` — step OTP+password otomatis
- `--otp=` / `--pw=` args
- `skipRecommended` → lanjut anyway (jangan berhenti)
- `JS_STATE` deteksi OTP/PASSWORD
