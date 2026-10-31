# Shopee anti_fraud captcha — RE (Opsi A) + Hook (Opsi B)

**Sumber:** `deo.shopeemobile.com/shopee/captcha/jenkins/pc/bundle.a95de02.js` (800 KB, obfuscated → 21.714 baris beautified)
**Metode:** reverse statik bundle + hook `fetch`/`XHR` in-page (Playwright).
**Tanggal:** 2026-10-14

---

## TL;DR

Captcha Shopee = **SDK kustom sendiri** (bukan reCAPTCHA/geetest/hCaptcha).
- SDK generik; **endpoint di-inject** dari luar.
- `get_config` **plaintext**.
- `generate` (challenge) = **AES-encrypted** (`U2FsdGVkX1...` = CryptoJS AES base64).
- Jawaban verify = **koordinat + timing** (bukan token solver).

---

## 🔌 Endpoint (terekam live, hook in-page)

```
POST /api/v4/anti_fraud/captcha/get_config          → plaintext
POST /api/v4/anti_fraud/captcha/generate            → AES-encrypted
POST /api/v4/anti_fraud/captcha/verify             (belum terpicu — perlu jawab)
POST /api/v4/anti_fraud/captcha/feedback/questions  → plaintext
GET  deo.shopeemobile.com/shopee/captcha/jenkins/pc/bundle.a95de02.js   (SDK)
GET  deo.shopeemobile.com/shopee/captcha/jenkins/pc/bundle.a95de02.css
```

### get_config — PLAINTEXT

**Request:**
```json
{"app_key":"User.PC","scene":"signup","platform":"pc",
 "request_id":"zO6MyaQv1OYUqv7tmprCBEMpg2rUdcB1","captcha_id":""}
```
**Response:**
```json
{"bundle_url":"https://deo.shopeemobile.com/shopee/captcha/jenkins/pc/bundle.a95de02.js",
 "style_url":"https://deo.shopeemobile.com/shopee/captcha/jenkins/pc/bundle.a95de02.css",
 "error":0,"tracking_id":"xSJ6tNbwxtyXgUjGHiNybz9W6iX1xSGoo4WQ9j2YXlZK..."}
```

### generate — AES-ENCRYPTED

**Request & response:**
```json
{"encrypted_data":"U2FsdGVkX1/AxotNJrUZNaBtMyyUhZ6Iy5/xX9/00pB4rSILGdcUMKTd6qW3+kKV..."}
```
`U2FsdGVkX1` + base64 = **CryptoJS AES** (format: `base64("Salted__"+salt+ct)`).
Kunci AES ada di bundle SDK → **harus diambil runtime dari halaman** (bukan hardcode).

---

## 🧬 Struktur payload verify (dari bundle, baris ~2938)

```js
{
  captcha_id, captcha_source,
  // jawaban KLIK-objek:
  captcha_top_left_x, captcha_top_left_y,
  captcha_box_width, captcha_box_height,
  // jawaban GESER (slider):
  slider_start_pos, slider_start_x, slider_start_y,
  slider_box_width, slider_box_height, slider_end_pos,
  // behavioral:
  captcha_start_timestamp, captcha_end_timestamp,
  captcha_refresh_num,
  captcha_move_type            // "" kosong default
}
```

Kesimpulan: server menilai **posisi klik/geser + waktu + jumlah refresh** (anti-bot
behavioral), bukan token pihak-3.

## 🎭 Tipe captcha (dari bundle, case switch)

- `verifySliderCaptcha` — geser puzzle (slider)
- `verifySimpleClickCaptcha` — klik objek ("Klik untuk memverifikasi Anda")
- tipe input/teks (`inputPlaceholder`, `errorWrongInput`) — fallback

---

## 🛠 Hook (Opsi B) — `tools/captcha_hook.py`

Menyuntik wrapper `fetch` + `XHR` ke halaman, merekam:
- `get_config` (req/resp plaintext)
- `generate` (req/resp encrypted)
- `feedback/questions`
- (verify, saat terpicu)

**Bukti jalan:**
```
[capture] {'generate': 2, 'verify': 0, 'config': 2, 'feedback': 2, 'all': 10}
```

Dipakai dari `auto_reg.py` / `farm_browser.py`:
```python
from tools.captcha_hook import install_captcha_hook, dump_captcha_capture
install_captcha_hook(page)      # setelah goto, sebelum aksi
...
dump_captcha_capture(page)      # → captcha_re/captcha_flow.jsonl
```

---

## 🚧 Untuk MENJAWAB captcha (langkah lanjut)

1. **Ambil kunci AES** — hook CryptoJS (`CryptoJS.AES.decrypt`) di halaman, atau
   baca kunci dari localStorage/config saat init.
2. **Dekripsi** `generate` → JSON challenge (base64 gambar puzzle + posisi target).
3. **Hitung jawaban**:
   - klik → `captcha_top_left_x/y` (koordinat titik objek)
   - geser → `slider_end_pos` (offset puzzle)
4. **Enkripsi balik** payload jawaban → POST ke `verify`.
5. Ikuti `captcha_move_type` + timestamp asli (behavioral lolos).

**Belum selesai:** langkah 1-5 masih perlu implementasi. Hook sudah siap merekam.

---

## Konsekuensi untuk solver pihak-3

| Solver umum | Berlaku? |
|-------------|:-:|
| reCAPTCHA v2 task | ❌ tidak ada sitekey |
| geetest task | ❌ tidak ada gt/challenge |
| hCaptcha task | ❌ |
| **Kustom Shopee** | butuh reverse AES + logika jawab sendiri |
