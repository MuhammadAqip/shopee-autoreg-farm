# Multi-Attempt + Struktur Celah: TEMUAN FINAL

**Tanggal:** 2026-10-15

## 🔥 TEMUAN BESAR

### 1. Multi-attempt WORKS (nomor `089601416331`)
```
attempt 1: drag 56px  → verify calls: 2 → CAPTCHA (refresh)
attempt 2: drag 98px  → verify calls: 4 → CAPTCHA
attempt 3: drag 140px → verify calls: 5 → CAPTCHA
attempt 4: drag 182px → verify calls: 6 → CAPTCHA
```
==**Jawaban salah → captcha REFRESH, bukan close. 1 nomor bisa banyak drag.**==

### 2. STRUKTUR CELAH (vision, multi_1)
```
PIECE (potongan) : KIRI ~10-12%
CELAH (slot)     : KANAN ~78-82%   ← DI KANAN, bukan tengah!
=> offset ~69% (≈193px dari 280px)
```

==**Gua salah selama ini** — nyari celah di tengah-kiri. **Celah ada di KANAN.**==

Celah = **slot dengan outline DASHED** (garis putus-putus) → gak ketangkep
via warna/tekstur (warna savana seragam).

## ❌ Gap detection rule-based (v3) — masih gagal
Celah dashed = garis tipis; edge energy rendah → terlewat.

## ✅ Solusi: VISION-guided solve

Vision **akurat** baca celah (`multi_1`: bilang 78-82%, benar). 
Pendekatan: **screenshot puzzle → vision baca celah → drag**.

- `probe_vg.py` — session polling `offset.txt` (agent isi offset, script drag)
- Atau vision-model API di dalam script

## 📊 Status

| Komponen | Status |
|---|:-:|
| Proxy Indonesia | ✅ |
| Pipeline otomatis (TOS→captcha→drag→verify) | ✅ |
| **Multi-attempt** | ✅ (1 nomor banyak drag) |
| **Struktur celah (kanan ~80%)** | ✅ |
| Gap detection otomatis (rule) | ❌ |
| Vision-guided solve | ✅ siap |
| Nomor fresh | ❌ habis |

## 🎯 Sisa: **1 nomor fresh** + vision-read celah (~80%) → drag → OTP

Nomor yang sudah kepake: `…616, …617, …618, …619, 89601416330, 89601416331`.
Butuh **1 nomor baru** → dengan insight celah-di-kanan, kemungkinan besar lolos.
