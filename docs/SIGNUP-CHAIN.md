# SIGNUP-CHAIN — Chain Registrasi & Payload Asli

Referensi request/response asli hasil capture live. Dipakai untuk debugging
dan verifikasi implementasi.

Semua data kredensial di dokumen ini sudah diganti placeholder. Contoh session
asli ada di `reference/captures/`.

---

## 1. Urutan Lengkap

```
 1  GET  https://shopee.co.id/buyer/signup
 2  UI   gate bahasa
 3  UI   input nomor
 4  UI   TOS
 5  UI   modal ketentuan
 6  POST /api/v4/otp/get_settings_v2
 7  UI   captcha render
 8  POST (captcha verify, ditangani SDK)
 9  POST /api/v4/otp/send_otp
10  OTP  terima SMS/WA
11  POST /api/v4/otp/verify_otp
12  POST /api/v4/account/login_by_password   (opsional)
```

---

## 2. Langkah 1 — Halaman Signup

```
GET https://shopee.co.id/buyer/signup
```

Yang harus ada setelah load:

```js
document.querySelector("input[type='tel']")        // field nomor
document.querySelector("button:has-text('Berikutnya')")
document.cookie.includes("csrftoken")
```

Kalau `input[type='tel']` tidak ada setelah 10 detik, halaman belum selesai
render. Tunggu `wait_until="load"` lalu tambah jeda 5 detik.

---

## 3. Langkah 2 — Gate Bahasa

Modal pertama yang muncul:

```
Pilih Bahasa Anda
  [English]  [Bahasa Indonesia]
```

Klik `Bahasa Indonesia`. Tanpa ini, field nomor tidak aktif atau format
nomor berbeda (`+62` vs `08`).

```python
page.locator("text=Bahasa Indonesia").first.click(force=True)
```

---

## 4. Langkah 3 — Input Nomor

```html
<input type="tel" placeholder="Nomor HP" ...>
```

Format yang diterima:

```
081234567890        ← lokal, diterima
+6281234567890      ← internasional, diterima
6281234567890       ← tanpa plus, diterima
```

Kirim sebagai string. Jangan format ulang setelah diketik — Shopee menyimpan
apa yang di-parse saat blur.

---

## 5. Langkah 4–5 — TOS & Modal

```python
page.locator("input[type='checkbox']").first.check()
page.locator("button:has-text('Berikutnya')").first.click(force=True)
time.sleep(1.5)
page.locator("text=Setuju").first.click(force=True)
```

Modal `Simak Ketentuan Akun Shopee` muncul setelah "Berikutnya". Tombolnya
`Setuju`, bukan `Berikutnya` atau `OK`.

---

## 6. Langkah 6 — `get_settings_v2`

### Request

```
POST /api/v4/otp/get_settings_v2
Content-Type: application/json
x-api-source: pc
x-requested-with: XMLHttpRequest
x-csrftoken: <cookie csrftoken>
af-ac-enc-dat: b0c9718544dc2712
referer: https://shopee.co.id/buyer/signup
```

Body:

```json
{
  "operation": 8,
  "phone": "6281234567890",
  "supported_channels": [1, 2, 3, 6, 0, 5],
  "client_identifier": {
    "security_device_fingerprint": "gq2qri+snOezkf56H6Mk6g==|dZ2s8nLw...|3gfOxLDWFjGqHOl0|08|3"
  }
}
```

`af-ac-enc-dat` **tidak** dikirim manual. Browser/SDK menambahkannya otomatis
saat `fetch()` dipanggil.

### Response sukses

```json
{
  "error": 0,
  "data": {
    "need_captcha": true,
    "captcha_scene": "signup",
    "available_channels": [3, 2, 1]
  }
}
```

### Response gagal yang umum

| `error` | Arti |
|---|---|
| `-1` | phone invalid |
| `3` | rate limit per nomor |
| `4108` | anti-fraud flag |

Kalau `need_captcha: false`, captcha tidak muncul — langsung ke `send_otp`.
Ini jarang tapi mungkin untuk nomor yang sudah "dipercaya".

---

## 7. Langkah 7–8 — Captcha

`captcha_scene: "signup"` menentukan jenis yang dirender:

| Scene | Jenis |
|---|---|
| `signup` (desktop) | reCAPTCHA v2 |
| `signup` (mobile web) | slider geetest |
| `anti_fraud` | image crawl |

Setelah captcha diselesaikan, SDK memanggil:

```
POST /anti_fraud/captcha/verify
```

Body **dienkripsi SDK sendiri**. Kita tidak perlu menyusun payload — cukup
selesaikan captcha-nya di UI, SDK yang melakukan sisanya.

---

## 8. Langkah 9 — `send_otp`

### Request

```
POST /api/v4/otp/send_otp
```

```json
{
  "phone": "6281234567890",
  "operation": 8,
  "channel": 3
}
```

`channel` dipilih dari `available_channels` di response sebelumnya:

| Nilai | Kanal |
|---|---|
| `1` | SMS |
| `2` | WhatsApp |
| `3` | SMS (alternatif) |
| `6` | voice call |

### Response

```json
{
  "error": 0,
  "data": {
    "channel": 3,
    "resend_cooldown": 60
  }
}
```

---

## 9. Langkah 10 — OTP

Nomor menerima SMS/WA 6 digit.

Sink yang tersedia:

```python
class ManualOTP:
    """baca dari otp.txt, format: 62812xxx:123456"""

class HTTPOTP:
    """adapter provider SMS-activation generik"""

class WAOTP:
    """WA bridge — baca dari session WA"""
```

Masa berlaku OTP biasanya 5 menit. Timeout → harus `send_otp` ulang (dengan
cooldown 60 detik).

---

## 10. Langkah 11 — `verify_otp`

```
POST /api/v4/otp/verify_otp
```

```json
{
  "phone": "6281234567890",
  "otp": "123456",
  "operation": 8
}
```

### Response sukses

```json
{
  "error": 0,
  "data": {
    "userid": 16823513404,
    "username": "k8lm9h2i5u",
    "phone": "6281234567890"
  }
}
```

Cookie yang di-set:

```
SPC_U   = <userid>
SPC_ST  = <session token>
SPC_F   = <fingerprint token>
SPC_SI  = <session info>
```

**Ini titik di mana akun dianggap jadi.** Simpan cookie + userid.

---

## 11. Langkah 12 — `login_by_password` (opsional)

Setelah OTP verify, sesi sudah aktif. `login_by_password` hanya dipakai kalau
butuh sesi baru belakangan (cookie sudah mati).

```
POST /api/v4/account/login_by_password
```

```json
{
  "phone": "6281234567890",
  "password": "[REDACTED]",
  "support_ivs": true,
  "country_code": "ID"
}
```

### Tabel hasil

| `error` | Arti | Tindakan |
|---|---|---|
| `0` | sukses | simpan cookie |
| `2` | password salah | cek kredensial |
| `89` | format hash ditolak | butuh `shpsec` SDK (browser) |
| `98` | password **benar**, perlu IVS | butuh akses email/WA |

`98` mengembalikan:

```json
{
  "error": 98,
  "data": {
    "ivs_flow_no": "7fb35513-2027-4772-a8f0-48ac0eef1a25",
    "ivs_token": "U2FsdGVkX19/8dGwoEVh8TSmr/ZqbkYQ..."
  }
}
```

Verifikasi IVS hanya lewat link ke email/WA terdaftar. Tidak ada jalur
bypass.

---

## 12. Header yang Dipakai SDK

Semua header ini **tidak** diset manual. SDK menambahkannya saat `fetch()`
dipanggil dari dalam halaman.

```
af-ac-enc-dat       : 16 hex, per-request
af-ac-enc-sz-token  : sz-token terenkripsi
x-sap-sec           : output VM
x-sap-ri            : 26 byte runtime integrity
x-csrftoken         : dari cookie
x-api-source        : pc | rweb
x-requested-with    : XMLHttpRequest
referer             : https://shopee.co.id/buyer/signup
```

Kalau header ini disusun manual dari luar browser → request ditolak. Itu
alasan arsitektur memakai browser.

---

## 13. Contoh Implementasi

```python
async def page_fetch(page, url, body):
    return await page.evaluate("""
        async ({url, body}) => {
            const r = await fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body),
            });
            return {status: r.status, json: await r.json()};
        }
    """, {"url": url, "body": body})
```

Pemakaian:

```python
settings = await page_fetch(
    page,
    "/api/v4/otp/get_settings_v2",
    {
        "operation": 8,
        "phone": "6281234567890",
        "supported_channels": [1, 2, 3, 6, 0, 5],
        "client_identifier": {
            "security_device_fingerprint": fp,
        },
    },
)
```

---

## 14. Klasifikasi Hasil

```python
def classify(resp, page):
    text = resp.get("error_msg", "") + page.inner_text("body")

    if "Identifikasi Tambahan" in text:
        return "limit"

    if "sudah terdaftar" in text.lower():
        return "limit"

    data = resp.get("data") or {}
    if data.get("userid"):
        return "ready"

    return "failed"
```

Urutan prioritas **tidak boleh** diubah:

```
limit  >  ready  >  failed
```

Kalau `limit` dicek setelah `ready`, akun yang sebenarnya ditandai akan
tercatat sebagai sukses dan merusak statistik.

---

## 15. Error Chain

| Gejala | Penyebab | Fix |
|---|---|---|
| field nomor tidak ada | halaman belum render | `wait_until=load` + jeda 5 s |
| modal tidak muncul | TOS belum diceklis | ceklis sebelum "Berikutnya" |
| `get_settings_v2` → `-1` | format nomor salah | pakai `62812…` |
| `need_captcha` tapi kosong | captcha tidak render | refresh halaman |
| `send_otp` → rate limit | nomor sudah dipakai | ganti nomor |
| OTP kedaluwarsa | > 5 menit | kirim ulang |
| `verify_otp` → `error` | OTP salah | cek sink |
| `login_by_password` → `89` | dipanggil dari luar browser | pakai page-context |
| `login_by_password` → `98` | device baru | butuh IVS |
