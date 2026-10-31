# Hasil SNIFF A — Endpoint Shopee Signup (LIVE, terverifikasi)

Tanggal probe: 2026-10-14 · Target: `shopee.co.id/buyer/signup` · Metode: Playwright headless (Chromium 156)

---

## 🔗 Chain Lengkap (terekam nyata)

```
1. GET  /buyer/signup                     → SPA render (197KB shell)
2. [gate] "Pilih bahasa Anda" → Oke
3. isi input[type=tel]  → format (+62) ...
4. ceklis TOS checkbox
5. klik "Berikutnya"                       → modal TOS kedua muncul
6. klik "Setuju"                           → TRIGGER OTP CALL ↓
─────────────────────────────────────────────────────────────
7. POST /api/v4/otp/get_settings_v2        → 200
   └─ butuh: phone, operation, client_identifier.security_device_fingerprint
   └─ balik: need_captcha:true, captcha_scene:"signup"
─────────────────────────────────────────────────────────────
8. [CAPTCHA] "Geser untuk menyelesaikan puzzle"
   └─ ID:zBB0mepN6adrdBU0HB2ipsy1RTeadEn7   (captcha session token)
─────────────────────────────────────────────────────────────
9. POST /api/v4/otp/send_otp (dgn captcha token)  → SMS/WA
```

---

## 📡 Endpoint Terverifikasi

### ✅ `/api/v4/otp/get_settings_v2` — HIDUP (200)
**POST** payload asli (terekam):
```json
{
  "operation": 8,
  "encrypted_phone": "",
  "phone": "6281234567890",
  "supported_channels": [1, 2, 3, 6, 0, 5],
  "support_session": true,
  "client_identifier": {
    "security_device_fingerprint": "AbAmEzrJirbQRGGWx8/Tig==|I9h2AKXoD9kk1XhC8oaRLLLCpI+CEHlO/JT5cCTDDRqMe74Xrkybm49l4zdndsG/h7ip3FyppVSlVwukzbfp3WIB|3ZIylJae3wbkJgu2..."
  }
}
```
**Respons:**
```json
{
  "error": 0,
  "data": {
    "need_login": false,
    "need_captcha": true,
    "captcha_scene": "signup",
    "preferred_channel": 3,
    "available_channels": [3, 2, 1],
    "hidden_available_channels": [2],
    "flow_name": "default_flow",
    "session_info": { "seed": "703eb58b-a2..." }
  }
}
```

### ✅ `/api/v4/account/login_by_password` — HIDUP (200)
error 10002 = param kosong (path valid).

### ✅ Endpoint support (200, terekam)
| Endpoint | Fungsi |
|---|---|
| `/api/v4/platform/get_ft_v2` | feature flags |
| `/api/v4/account/basic/get_account_info` | cek sesi (error 19 = belum login) |
| `/api/v4/account/subaccount` | subaccount |
| `/api/v4/account/get_banner_text` | teks banner signup |
| `/api/v4/abtest/traffic/get_web_experiments` | A/B (kirim device_fingerprint) |
| `/api/v4/experiment/config` | → URL bundle browser-signals |
| `/api/v4/account/get_tos_urls` | link TOS/privacy |
| `/api/v4/web/subcart` | cart |
| `/api/v4/otp/get_settings_v2` | **OTP settings (kunci)** |

---

## 🔑 Header Wajib (terekam di semua request)

```
x-api-source: rweb
x-requested-with: XMLHttpRequest
content-type: application/json
x-csrftoken: <dari cookie csrftoken>
af-ac-enc-dat: <hex 16 char, PER-REQUEST, terenkripsi>
referer: https://shopee.co.id/buyer/signup
```

- **`x-csrftoken`** → dari cookie `csrftoken` (set saat GET halaman).
- **`af-ac-enc-dat`** → ==per-request encrypted header== dari bundle `browser-signals` (anti-bot).
- **`security_device_fingerprint`** → token terenkripsi format `base64|base64|base64`.

---

## 🚧 Blocker Teridentifikasi

### 1. CAPTCHA slider (geetest-style)
Saat step get_settings_v2, server balik `need_captcha: true`. UI menampilkan:
> **"Geser untuk menyelesaikan puzzle"** + `ID:zBB0mepN6adrdBU0HB2ipsy1RTeadEn7`

Butuh solver (2Captcha/anti-captcha/capsolver) ATAU Frida bypass di app native.

### 2. Encrypted headers
- `af-ac-enc-dat` — per-request, dari JS bundle. Butuh eksekusi bundle ATAU hook.
- `security_device_fingerprint` — token terenkripsi, di-generate client-side.

### 3. Device fingerprint
`abtest` kirim `device_fingerprint` (contoh: `6lYRZ6EJe4JCYTNZsQ048cz14DKV2Eaz`, `xk8E5lJkuIwES8UxySg01Lu8QIowY2tE`) — 32-char acak per sesi.

---

## 📦 Artefak Tersimpan

| File | Isi |
|---|---|
| `sniff_A.json` | API calls awal (halaman load) |
| `sniff_A2.json` | calls saat interaksi awal |
| `sniff_A3.json` | setelah fill nomor |
| `sniff_A4.json` | setelah ceklis TOS |
| `sniff_A6.json` | setelah klik Berikutnya (kosong — modal blokir) |
| `sniff_A7.json` | **FULL FLOW — 27 calls termasuk get_settings_v2** |
| `/root/shopee-signup-form.png` | screenshot form (language gate) |
| `/root/shopee-signup-after.png` | screenshot (modal TOS) |
| `/root/shopee-otp-screen.png` | screenshot (captcha puzzle) |

---

## 🎯 Implikasi ke `shopee_client.py`

Tebakan path lama **salah**. Yang benar:

```
OTP settings : POST /api/v4/otp/get_settings_v2
Login        : POST /api/v4/account/login_by_password
```

Yang **wajib** ditambahkan:
1. `x-csrftoken` dari cookie
2. `af-ac-enc-dat` header (encrypted — butuh JS/hook)
3. `security_device_fingerprint` (encrypted — butuh JS/hook)
4. Solver captcha slider

---

## Next (opsi B & C)

- **B (mitmproxy):** rekam flow asli dari HP/Chrome → dapat header encrypted apa adanya + capture captcha token
- **C (Frida):** hook app Shopee Android → lihat cara app generate `af-ac-enc-dat` + `security_device_fingerprint`, dan mungkin bypass captcha

---

## 🛑 KOREKSI + TEMUAN BARU (2026-10-14, probe lanjutan)

### Captcha BUKAN reCAPTCHA / geetest — KUSTOM SHOPEE

Scan DOM setelah `get_settings_v2` (Playwright):

```
Vendor pihak-3: SEMUA FALSE
  recaptcha=false grecaptcha=false hcaptcha=false geetest=false
  gt4=false cf-turnstile=false arkose=false funcaptcha=false
  datadome=false kasada=false perimeterx=false _px=false shield=false

DOM elements:
  <link id="captchaStyle">
  <div id="anti_fraud_captcha">          ← KUSTOM

Network (terekam):
  /api/v4/anti_fraud/captcha/get_config
  /api/v4/anti_fraud/captcha/generate
  /api/v4/anti_fraud/captcha/feedback/questions
  deo.shopeemobile.com/shopee/captcha/jenkins/pc/bundle.a95de02.js
  deo.shopeemobile.com/shopee/captcha/jenkins/pc/bundle.a95de02.css
```

**Verdict:** Shopee pakai captcha **buatan sendiri** (`anti_fraud_captcha`),
di-serve dari CDN Shopee (`deo.shopeemobile.com/shopee/captcha/`).
Bukan reCAPTCHA v2, bukan geetest.

**Implikasi solver:**
- ❌ Tidak ada sitekey reCAPTCHA → `solve_recaptcha_v2` **tidak berlaku**.
- ❌ Tidak ada `gt`/`challenge` geetest → `solve_geetest_slider` **tidak berlaku**.
- ✅ Solver pihak-3 umum **tidak bisa** langsung. Butuh:
  - (a) reverse bundle `bundle.a95de02.js` untuk format challenge/answer, ATAU
  - (b) hook di browser (Playwright CDP) untuk baca/menjawab challenge, ATAU
  - (c) token solver custom (jarang didukung 2captcha/capsolver).

**UI:** overlay "Verifikasi untuk melanjutkan", gambar "Klik untuk memverifikasi Anda"
(klik-titik / pilih objek), ikon refresh+audio, kode verifikasi.
