# MILESTONE — Pipeline Otomatis Penuh + Gap v4

**Tanggal:** 2026-10-15

## ✅ SEMUA JALAN OTOMATIS (solve_one v3)

Run terakhir — **tanpa intervensi**:
```
fill: ok ✅
submit: "Berikutnya" ✅
clicked Setuju ✅
STATE: CAPTCHA ✅
net: get_settings_v2 [200] → anti_fraud/captcha/get_config [200] → generate [200] ✅
GAP: offset 218px (gap_pct 77.9)   ← piece detect Laplacian
attempt 1: CAPTCHA
attempt 2: (loading)               ← verify terpanggil
verify calls: 4
```

**Bukti:** proxy ID → signup → TOS → captcha → crop → piece detect → drag → verify,
semua **otomatis**.

## ✅ Breakthrough gap detection (v4)

Blueprint vision → `tools/gap_v4.py`:
- **PIECE** = Laplacian texture-energy → **akurat** (`so_puzzle_3x`: piece 10.2%, sesuai ~10-12%)
- **SLOT** = HoughLines dashed (masih lemah, fallback celah kanan ~78%)

## 📊 Status FINAL

| Komponen | Status |
|---|:-:|
| Endpoint + kripto (AES-128-GCM) | ✅ |
| Jenis captcha (`advanced_slider`) | ✅ |
| **Proxy Indonesia** | ✅ (82.158.131.205) |
| **Pipeline otomatis penuh** | ✅ |
| Modal bahasa dismiss | ✅ |
| Submit + TOS | ✅ |
| Captcha render + rect presisi | ✅ |
| **Piece detect (Laplacian)** | ✅ |
| Drag + verify endpoint | ✅ |
| Multi-attempt (refresh) | ✅ |
| **Celah akurat → lolos** | ⬜ tuning |

## 🧱 Dinding tersisa: 1

**Celah (slot) dashed** di gambar — posisi presisi. Piece **sudah akurat now**;
slot perlu HoughLines lebih baik ATAU template-match ATAU vision-model inline.

## Artefak siap

- `solve_one.py` — solver one-shot otomatis penuh
- `tools/gap_v4.py` — Laplacian + Hough
- `tools/ui_solver.py` — human drag
- `tools/captcha_hook.py` — flow recorder
- `proxies_id_vs.txt` — 12 proxy Indonesia
- Dokumentasi: A→W + ini

## Nomor terpakai
`…616, …617, …618, …619, 89601416330, 89601416331, 8562937614`
