# Opsi I — Image-Diff Slider Solver: Hasil

**Tanggal:** 2026-10-15

---

## ✅ Yang terbukti

### 1. Nomor nyata → captcha slider render PENUH (berulang)
Dengan `087876125616`, chain jalan sampai: modal **"Verifikasi untuk melanjutkan"**
+ slider puzzle ("Geser untuk menyelesaikan puzzle") + `ID:` unik per sesi.
(bukti: `shots/h1_captcha.png`, `shots/i1_full.png`, `shots/i2_full.png`, `shots/i3_full.png`)

### 2. Hook capture flow lengkap
```
generate: 2   config: 2   feedback: 2   all: 10
get_settings_v2 → need_captcha:true
anti_fraud/captcha/generate → encrypted_data
```

---

## ❌ HAMBATAN: DOM captcha TIDAK tembus

### Temuan teknis (penting)
```
#anti_fraud_captcha  →  <div id="anti_fraud_captcha"></div>   (KOSONG, len 35)
imgs/canvases/bgimgs di dalamnya → []
BYTEXT (cari "Verifikasi"/"Geser") → []
```

**Kesimpulan:** walau screenshot menunjukkan captcha penuh, **DOM `#anti_fraud_captcha`
kosong**. Puzzle render di **tempat terisolasi** — kemungkinan:
- **iframe** cross-origin (SDK captcha) — `querySelectorAll` gak tembus
- **shadow DOM tertutup** (closed shadowRoot) — gak terlihat

Karena itu ekstraksi gambar via DOM query **gagal** (kanvas/img/puzzle gak ketemu).

### 3. Flaky
Captcha render penuh hanya ~1 dari 3 run. Sisanya `captcha: dom` (container ada
tapi challenge belum render). Perlu retry + tunggu sinyal.

---

## 🎯 Solusi yang benar (untuk iterasi berikut)

Karena DOM gak tembus:

1. **Retry sampai challenge render** — deteksi via:
   - `window.__shcap.generate.length >= 1` (API terpanggil)
   - ATAU modal visible via pixel/`document.elementFromPoint`
   - ATAU tunggu 3-5 detik setelah generate
2. **Screenshot region puzzle** (bukan DOM query) — crop layar di area modal
   captcha (tengah layar ~1280×900 → crop ~250×500 center).
3. **Image-diff dari crop:**
   - konversi grayscale
   - cari kolom dengan edge vertikal kuat (batas celah) di 15-95% dari kiri
   - `gap_x` = posisi celah
4. **Hitung offset** = `gap_x * (display_scale)`.
5. **Geser grip** via `human_drag` (5. `tools/ui_solver.py` — sudah siap).
6. SDK Shopee **encrypt + POST verify** otomatis.
7. `send_otp` → OTP SMS → akun.

**Semua komponen ada:** `tools/slider_solver.py` (grab + find_gap_x),
`tools/ui_solver.py` (human_drag), `tools/captcha_hook.py` (capture).
Yang perlu: ganti ekstraksi DOM → **screenshot-region + retry**.

---

## 📊 Status I

| Komponen | Status |
|----------|:-:|
| Chain → captcha penuh (nomor nyata) | ✅ |
| Hook capture flow | ✅ |
| `slider_solver.py` (find_gap_x, grab) | ✅ kode siap |
| `ui_solver.py` human_drag | ✅ |
| Ekstraksi gambar via DOM | ❌ (captcha di iframe/shadow) |
| Ekstraksi via screenshot-region | ⬜ next |
| Retry/anti-flaky | ⬜ next |
| Geser → verify → OTP | ⬜ |

---

## Kesimpulan

Chain **terbukti penuh** dengan nomor nyata. Captcha = **slider puzzle**.
Kendala teknis: challenge di **iframe/shadow terisolasi** → ekstraksi harus via
**screenshot-region** (bukan DOM), plus retry anti-flaky. Solver logic
(image-diff + drag) **sudah ditulis**, tinggal switch sumber gambar.
