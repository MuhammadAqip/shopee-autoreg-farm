# Opsi Y — Slot Detection Tuning: Hasil

**Tanggal:** 2026-10-15
**Nomor tes:** `085729884045` (fresh)

## ✅ Yang jalan (run ini)

```
fill ✅ → submit "Berikutnya" ✅ → Setuju ✅
STATE: CAPTCHA ✅
net: get_settings_v2 → get_config → generate → feedback/questions ✅
3 crop puzzle tersimpan (puz0/1/2)
verify calls: 6
```

Timing fix (tunggu "Memuat..." hilang) + crop-save → **3 puzzle tersimpan** buat analisis.

## 🔬 Insight baru (vision)

- **PIECE flush di KIRI (x≈0)** — semi-transparan, outline putih
- **CELAH = area GELAP (hole silhouette)** di tengah (~40-58%), bukan dashed
- Offset = hole_x (karena piece di 0)

**Koreksi:** celah BUKAN di 78% (yg gua kira). **Celah di tengah ~40-58%.**

## 📊 Detector evolution

| Versi | Metode | Hole detect |
|---|---|---|
| v1-v3 | variance/edge | 12-78% (ngawur) |
| v4 | Laplacian piece | piece akurat ✅ ; slot lemah |
| **v5** | **dark-blob** | **40-54%** (lebih masuk akal) |

`gap_v5` (dark mask): puz0=52.5%, puz1=39.6%, puz2=54.3%.

## ⚠️ Masih tidak presisi

Vision sendiri **tidak konsisten** (puz1: bilang 58% padahal detektor 39.6%).
Background kompleks (atol/batu/laut) → celah sulit diukur presisi dari downscale.

## 📊 Status FINAL (A→Y)

| Komponen | Status |
|---|:-:|
| Endpoint + kripto | ✅ |
| Proxy Indonesia | ✅ |
| **Pipeline otomatis penuh** | ✅ |
| Modal/TOS/submit | ✅ |
| Captcha + rect + load-wait | ✅ |
| **Piece detect** | ✅ akurat |
| **Celah detect** | ⚠️ ~40-54% (belum presisi) |
| Drag + verify multi-attempt | ✅ |
| Lolos → OTP | ⬜ |

## 🎯 Sisa: presisi celah

**1 dinding tersisa:** posisi celah presisi pada background kompleks.
Solusi lanjut:
1. **Loop multi-offset** (multi-attempt udah works) — drag grid 30-70%
2. Template-match hole-shape
3. Model vision inline

## Infrastruktur: LENGKAP

`solve_one.py` (otomatis) + `gap_v4/v5` + `ui_solver` + hook + 12 proxy ID.
Nomor terpakai: `…616-619, 89601416330/31, 8562937614, 85729884045`.
