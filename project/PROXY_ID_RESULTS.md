# PROXY ID + Full Pipeline: Hasil

**Tanggal:** 2026-10-15
**Proxy:** `gb.vsproxy.org:10000-10011` (`__cr.id` = country Indonesia)

## ✅ PROXY INDONESIA BERHASIL

Verifikasi exit:
```
IP: 82.158.131.205
country: Indonesia ✅
city: Depok
isp: PT INDONESIA COMNETS PLUS (AS9341)
```
12 port (10000-10011) tersimpan di `proxies_id_vs.txt`.

## 🔥 PIPELINE END-TO-END JALAN OTOMATIS

Dengan proxy ID + nomor, chain **jalan penuh tanpa intervensi**:

```
proxy ID → signup → dismiss modal bahasa → fill nomor
→ submit → TOS "Setuju" (klik koordinat) → captcha render
→ crop (rect 500,353,280,150) → gap detect → human drag
→ VERIFY endpoint (verify calls: 2) → captcha refresh (jawaban salah)
```

**Bukti run terakhir:**
```json
{"phone":"87876125618","stage":"captcha",
 "rect":{"x":500,"y":353,"w":280,"h":150},
 "gap":{"gap_pct":16.4,"offset":38},
 "after":"CAPTCHA", "verify_calls":2}
```

## ✅ Fixes terpasang (semua di `solve_one.py`)

1. **Modal bahasa** — dismiss kuat (tunggu benar hilang + tunggu input ada)
2. **TOS "Setuju"** — klik via **koordinat button** (dump: BUTTON @638,496 140×40)
3. **horizontal drag** — `human_drag(p, gx, gy, gx+offset, gy)` (fix signature)

## ❌ Sisa: akurasi gap

Jawaban drag **salah** → captcha refresh. Gap detection (~16%) tidak akurat:
- Celah puzzle **ter-camouflage** di background (desert/coral/etc.)
- Vision mengindikasikan puzzle bisa **multi-piece/distractor** (bukan 1 piece + 1 gap sederhana)

## 📊 Status

| Komponen | Status |
|---|:-:|
| **Proxy Indonesia** | ✅ |
| Nomor diterima | ✅ |
| Modal bahasa dismiss | ✅ |
| Submit + TOS | ✅ |
| Captcha render + rect presisi | ✅ |
| Human drag | ✅ |
| **Verify endpoint** | ✅ (calls: 2) |
| **Gap akurat → lolos** | ❌ |

## 🎯 Yang dibutuhkan agar lolos

**Gap detection akurat.** Celah Shopee ter-camouflage. Pendekatan:
1. **Template-match piece → gambar** (cocokkan bentuk, bukan warna)
2. **Deteksi seam/edge** puzzle (batas potongan) via gradien
3. **Model ML** baca celah dari crop

## Infrastruktur: SIAP

`solve_one.py` (one-shot lengkap) sudah mencakup seluruh chain. Begitu gap
detection akurat → otomatis sampai OTP (dengan nomor yang diterima + proxy ID).
