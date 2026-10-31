# Opsi H — Nomor HP Nyata: HASIL (SUKSES BESAR)

**Tanggal:** 2026-10-15
**Nomor:** `087876125616` (nyata, OTP via SMS)
**Verifikasi:** nomor dummy ditolak, nomor nyata DITERIMA.

---

## 🎯 TEMUAN KUNCI

Dengan **nomor HP Indonesia nyata**, chain berjalan **PENUH sampai captcha**:

```
POST /api/v4/otp/get_settings_v2   [200]
  → {"error":0,"data":{"need_captcha":true,"captcha_scene":"signup",
       "preferred_channel":3,"available_channels":[3,2,1],
       "hidden_available_channels":[2], ...}}

POST /api/v4/anti_fraud/captcha/get_config   [200]
  → {"bundle_url":".../bundle.a95de02.js","tracking_id":"uOZOemmnRGQFYcNE6T...","error":0}

POST /api/v4/anti_fraud/captcha/generate     [200]
  → {"encrypted_data":"U2FsdGVkX19HNZBaY67VK7ekQMPl+qJnzNtMTYqb0Xfauo0c..."}

POST /api/v4/anti_fraud/captcha/feedback/questions   [200]
  → {"questions":[{"id":0,"key":"label_captcha_report_issue_9"}, ...]}
```

**Captcha render penuh:**
- `#anti_fraud_captcha`: container ✅, 2 canvas:
  - `EkGpDI` 280×150 (gambar puzzle)
  - `_0N0-Dn` 44×44 (grip/slider)
- Modal "Verifikasi untuk melanjutkan"
- Instruksi: **"Geser untuk menyelesaikan puzzle"**
- `ID:wWZpWktuol2xLlvTfpLkWm81GwrOQrf0`

---

## 🧩 Jenis captcha TERKONFIRMASI

**Slider puzzle** (persis prediksi RE `verifySliderCaptcha`):
- Gambar: keranjang rotan berisi apel
- Potongan puzzle harus digeser ke celah kosong
- Grip oranye (→) di kiri bar

**Matching dengan struktur verify (dari bundle):**
```
slider_start_pos, slider_start_x, slider_start_y,
slider_box_width, slider_box_height, slider_end_pos,
captcha_start_timestamp, captcha_end_timestamp, captcha_move_type
```

---

## ✅ Yang terbukti vs ❌ sisa

| Item | Status |
|------|:-:|
| Nomor nyata → submit diterima | ✅ |
| `get_settings_v2` 200 + need_captcha | ✅ |
| `anti_fraud/captcha/*` terpanggil | ✅ |
| Captcha slider render PENUH (2 canvas) | ✅ |
| Hook rekam semua flow | ✅ (generate:2, config:2, feedback:2) |
| Solver BACA posisi celah | ⬜ (vision kurang akurat) |
| Auto-geser → verify | ⬜ |

---

## ⚠️ Catatan flaky

Kadang captcha muncul penuh (h1 ✅), kadang container kosong (`captcha: dom`,
canvas 0). Kemungkinan:
- Timing: SDK perlu waktu lebih untuk load + render canvas
- Fingerprint/track: retry butuh fingerprint matang
- Variasi: kadang challenge beda

**Fix:** retry loop + tunggu canvas muncul (`wait_for_selector('canvas')`) sebelum
ekstrak.

---

## 🎯 Langkah jawab slider (yang tersisa)

1. **Ekstrak** 2 canvas → gambar (canvas.toDataURL) ATAU ambil src img puzzle.
2. **Hitung offset celah** — image diff: bandingkan potongan vs background,
   cari kolom dengan perbedaan (celah). (Vision kurang akurat: "15-20%" kira-kira)
3. **Geser** grip sejauh offset (via `human_drag` di ui_solver).
4. **SDK encrypt + POST verify** otomatis.
5. `send_otp` → OTP SMS → akun.

**Bottleneck yang bisa diselesaikan kode:** ekstraksi canvas + image-diff
(akurat, bukan tebakan vision). Solver `human_drag` sudah siap.

---

## 📋 Kesimpulan A→H

| Opsi | Hasil |
|------|-------|
| A reverse bundle | ✅ endpoint + struktur + AES |
| B hook | ✅ rekam flow |
| C kunci AES | ✅ key-exchange + AES inline |
| D endpoint | ✅ anti_fraud/captcha/* |
| E require | ✅ app-chunk; crypto IIFE ❌ |
| F solver UI | ✅ driver mouse |
| G Xvfb | ✅ form stabil |
| **H nomor nyata** | ✅ **chain penuh → captcha slider render** |

**Pembuktian lengkap A→H:** endpoint, kripto, captcha jenis, chain, semua
terverifikasi live. Yang tersisa = image-diff solver untuk slider (kode, bukan
kendala eksternal).
