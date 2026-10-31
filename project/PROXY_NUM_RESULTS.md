# Opsi S + R (Penuh): Hasil FINAL

**Tanggal:** 2026-10-15

## ✅ S — Scan Proxy (989)

Sample 260 proxy → distribusi negara:
```
FR 9+, CA 8+, GB 6+, AU 4+, US 3+
ID/SG/MY/TH/VN/PH = 0
```
==**Floppydata = Western murni. Tidak ada exit Indonesia.**==
`proxies_id.txt` kosong.

## ✅ R — Tes Nomor Baru `087876125617`

### 🔥 BREAKTHROUGH BESAR

Percobaan **PERTAMA** (proxy FR, nomor `087876125617`):
```
stage: captcha  ✅
canvases:
  EkGpDI  @ (500, 353)  280×150   ← PUZZLE
  _0N0-Dn @ (500, 429)  44×44     ← GRIP
```

==**Rect canvas PRESISI ketangkep di run ini** (500,353,280,150) — berbeda dari run sebelumnya (surface tertutup).==

Crop presisi → analisis:

| Item | Nilai |
|---|---|
| Puzzle rect | (500, 353, 280, 150) |
| Piece | kiri ~3% |
| **Gap** | **~18-25% (pusat 21%)** |
| **Offset** | **~50px** |

**Gap detection BERHASIL** pada crop presisi (canvas rect).

### ❌ Percobaan ke-2+
```
TEXT: "Telah terjadi kesalahan. Mohon coba lagi nanti."
get_settings_v2 → rejected
```

==**Shopee menerima setiap nomor HANYA di percobaan PERTAMA.**==
- `087876125616`: attempt 1 → captcha ✅ ; attempt 2+ ❌
- `087876125617`: attempt 1 → captcha ✅ ; attempt 2+ ❌

## 🧱 Aturan final (terbukti)

**One-shot per nomor:**
1. Nomor baru (belum pernah submit) → **captcha render di attempt 1**
2. Attempt ke-2+ → ditolak (rate-limit nomor)

**Konsekuensi farm:** butuh **stok nomor baru** tiap percobaan. Solver harus
jalan **penuh dalam satu run** (tidak bisa retry nomor yang sama).

## 📊 Komponen solver (semua terbukti terpisah)

| Komponen | Status |
|---|:-:|
| Chain → captcha (nomor fresh) | ✅ |
| **Rect canvas presisi** (proxy) | ✅ (500,353,280,150) |
| Crop + gap detect | ✅ (~21%) |
| Human drag | ✅ |
| Drag → verify endpoint | ✅ (bukti K) |
| OTP | ⬜ butuh 1 clean shot |

## 🎯 Sisa: 1 clean shot

Butuh **1 nomor baru** (belum pernah dicoba) + proxy → solver jalan otomatis:
proxy → nomor → captcha → crop → gap → drag → verify → OTP.

Semua bahan siap. Tinggal nomor fresh.
