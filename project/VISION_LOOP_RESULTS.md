# Opsi O — Visi Loop + Dekripsi generate: Hasil

**Tanggal:** 2026-10-15

## ✅ Bukti baru (API body lengkap akhirnya ketangkep)

Fix hook (`window.__shcap`) → **semua body API terekam** (`captcha_re/captcha_bodies.json`):

| Endpoint | Body |
|---|---|
| `get_config` (req) | `{"app_key":"User.PC","scene":"signup","platform":"pc","request_id":"…","captcha_id":""}` |
| `get_config` (resp) | `{"bundle_url":"…bundle.a95de02.js","style_url":"…","error":0,"tracking_id":"B-9KBL…(88 char)"}` |
| `generate` (req) | `{"encrypted_data":"U2FsdGVkX1+Sulyv…"}` |
| `generate` (resp) | `{"encrypted_data":"U2FsdGVkX1/AKzmr…"}` |
| `feedback/questions` (req) | `{"app_key":"User.PC","scene":"signup","captcha_id":"YWR2YW5jZWRfc2xpZGVyOjE3OTIwMTg1NjUxMzkzNTcxNDY5MzIzODY3","tracking_id":"…","audio":false}` |

**`captcha_id` base64-decode → `advanced_slider:17920185651393571469323867`.**
→ Jenis captcha = **`advanced_slider`** (slider versi lanjutan).

## ✅ Skema kripto lengkap (RE, baris 629-660 + 10660-10735)

`d.F` (key-exchange) + `l` (AES inline):

```
client:   e=Ln()  r=randomStr(8..12)  i=randomBytes(16)   a=base64(i)
          POST {randomString:r, encryptKeyValue:a, aesKey:i}
server:   → { key: <16B>, data: <enc> }
client:   i = resp.key                     # kunci sesi
          o = decrypt(resp.data)           # plaintext sesi
          l = SM(o)                         # SHA(plaintext)
          u = Yf()                          # nonce acak
          data = SM(l) || "||" || SM(Al(u))
          key  = SM(o.subarray(0,12))       # 12-byte nonce (GCM)
```
- AES-128 **inline** (S-box + 5×256 T-tables, 10 round, ciphertext + 4-byte length suffix).
- Format wire `U2FsdGVkX1…` = base64(`Salted__` + salt + ciphertext) — pola CryptoJS OpenSSL.

## ❌ Dinding

1. **Dekripsi `generate`** butuh **key sesi mentah** (`aesKey`) yang dibuat di IIFE
   webpack (module ID statik ≠ runtime ID; sudah dikonfirmasi probe E).
   Hook `crypto.getRandomValues` belum kebagian run sukses (flaky).
2. **Gap detection visual GAGAL** — celah puzzle **ter-camouflage** di gambar
   bertekstur (edge/Canny kena noise batu/pohon; variance/warna tidak konsisten:
   25% vs 40-50% ground truth).
3. Captcha masih **flaky** (~1/3) + rate-limit.

## 📊 Status O

| Komponen | Status |
|---|:-:|
| Body API lengkap (hook fix) | ✅ |
| captcha_id → `advanced_slider` | ✅ |
| Skema kripto (AES-128 GCM inline) | ✅ RE |
| Dekripsi generate (key mentah) | ❌ IIFE |
| Gap detection visual | ❌ camouflaged |
| Retry / anti-flaky | ⬜ |

## 🎯 Jalan realistis tersisa

1. **Reimplement AES-128-GCM inline** (dari T-tables yang sudah terbaca) +
   gegat `aesKey` via hook `crypto.getRandomValues`/`subtle` yang stabil
   → dekripsi `generate` → mungkin dapat **data challenge (posisi jawaban)**.
2. **Jalur lebih longgar**: login (bukan signup) / mobile-web SDK / Google-FB OAuth.
3. **Model ML image** (bukan rule-based) buat baca celah dari screenshot.

**Semua API + kripto ternyata bisa direach — tapi butuh reimplementasi crypto penuh.
Dinding terakhir bukan "tidak mungkin", tapi "butuh lebih dalam".**
