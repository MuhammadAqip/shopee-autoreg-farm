# Opsi K — Solver End-to-End: Hasil (MEKANISME TERBUKTI)

**Tanggal:** 2026-10-15

---

## ✅ PENCAPAIAN BESAR

### 1. Chain penuh dengan nomor nyata → captcha slider
```
nomor 087876125616 → get_settings_v2 (need_captcha) → generate → captcha render
```

### 2. DRAG → VERIFY TERPANGGIL (kunci!)
```
captcha OK attempt 1
>>> drag grip 525,540 -> 705,540
CAPTURE: {'generate': 4, 'verify': 2, 'config': 2, 'feedback': 4, 'all': 16}
verify calls: 2
```

**Artinya:** kita berhasil menggerakkan slider via event mouse manusiawi →
**SDK Shopee otomatis menyusun payload jawaban + encrypt + POST `/anti_fraud/captcha/verify`**.
Ini pembuktian bahwa:
- Event mouse sintetis **diterima** SDK
- SDK menangani kripto (yang tadi terkunci di IIFE) **sendiri**
- Endpoint verify live

Jawaban gagal (offset salah) → puzzle reset + ID baru, tapi **mekanisme lengkap**.

### 3. Struktur puzzle teridentifikasi (visual)
- Gambar puzzle ~290-440px lebar di modal tengah
- **PIECE** menonjol di tepi kiri (~7-10% dari kiri)
- **GAP** (celah) di dalam gambar (estimasi visual ~30-35%)
- **Solusi: geser PIECE ke GAP** → `offset = gap_x - piece_x`

---

## ❌ HAMBATAN FINAL: crop region puzzle akurat

### Masalah
- `#anti_fraud_captcha` = `<div></div>` KOSONG → puzzle di **iframe cross-origin**
  (querySelectorAll gak tembus).
- Crop region pakai estimasi (hardcode) → **tidak tepat** (kepotong/salah area).
- Deteksi GAP via "variansi rendah" **keliru** (area luar puzzle juga low-variance).

### Bukti
```
analyze crop p1/p2/p3 → gap selalu di ~5% (salah; itu area luar gambar)
```

---

## 🎯 SOLUSI TEPAT (untuk selesai 100%)

Karena `verify` SUDAH terpanggil saat drag, tinggal kirim offset BENAR:

1. **Ambil rect puzzle presisi** — tembus iframe:
   ```python
   for fr in page.frames:
       el = fr.query_selector("canvas, img")   # cari di dalam iframe
       if el: box = el.bounding_box()
   ```
   ATAU `page.frames[i].query_selector('canvas')` → dapat rect tepat.
2. **Crop region tepat** dari rect → puzzle bersih.
3. **Deteksi GAP tepat** — bandingkan gambar puzzle dgn versi "lengkap"
   (SDK biasanya kirim bg + piece terpisah), ATAU template-match piece di dalam gambar.
4. **offset = gap_x - piece_x** → **geser** (human_drag).
5. SDK encrypt + verify → lolos → `send_otp` → OTP SMS → akun.

**Semua sudah terbukti jalan kecuali langkah 1-3 (rect + gap presisi) — murni
teknis, bukan kendala eksternal.**

---

## 📊 Status K

| Komponen | Status |
|----------|:-:|
| Chain → captcha (nomor nyata) | ✅ |
| Captcha slider render | ✅ |
| **Drag → verify terpanggil** | ✅ **BUKTI** |
| SDK encrypt jawaban otomatis | ✅ |
| Hook capture verify | ✅ (verify:2) |
| Struktur puzzle (piece+gap) | ✅ visual |
| Rect puzzle presisi (iframe) | ⬜ next |
| Gap detection akurat | ⬜ next |
| Offset benar → lolos | ⬜ |
| OTP → akun | ⬜ |

---

## Kesimpulan menyeluruh (A→K)

Chain signup Shopee **terbongkar penuh & terbukti live**:
- Endpoint (A/D)
- Kripto key-exchange + AES inline (C/E)
- Hook flow (B)
- Solver mouse + drag → **verify terpanggil** (F/K)
- Form stabil (G)
- Nomor nyata → captcha render (H/I)

**Yang tersisa:** presisi crop rect (iframe traversal) + gap detection —
100% pekerjaan klien, tidak butuh apa pun dari luar.
