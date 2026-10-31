# Solver Slider Shopee — Status Final (I/K)

**Tanggal:** 2026-10-15

## ✅ TERBUKTI (mekanisme penuh)

1. **Chain signup penuh** dgn nomor nyata (`087876125616`):
   `get_settings_v2` → `need_captcha` → captcha slider render.
2. **Drag slider → verify terpanggil** (BUKTI LIVE):
   ```
   drag 525,540 → 705,540
   CAPTURE: {generate:4, verify:2, config:2, feedback:4}
   ```
   → SDK Shopee **otomatis** susun payload + encrypt + POST `/anti_fraud/captcha/verify`.
   (Kripto yang terkunci di IIFE ditangani SDK sendiri.)
3. **Struktur puzzle** teridentifikasi: piece kiri (~3%), celah tengah (~40-50%).

## ❌ DINDING NYATA

- `#anti_fraud_captcha` = `<div></div>` **kosong**.
- **Tidak ada iframe** (frame: shopee, about:blank, doubleclick).
- **Tidak ada shadow root** kekbaca (shadowHosts: []).
- Tapi captcha **render di layar** → puzzle di **surface/closed-shadow SDK**
  yang gak bisa di-query DOM.

**Akibat:** rect puzzle presisi **tidak bisa** didapat dari DOM/frame. Crop
harus dari screenshot penuh → deteksi region **tidak stabil**:
- deteksi saturasi → rect 419×273 (kelebihan, puzzle asli ~290×130)
- gap color-based → 25-56% (ground truth 40-50%), tidak konsisten antar crop

## 📦 Artefak (semua tersimpan)

- `tools/signup_driver.py` — chain driver JS-only (anti-hang) ✅
- `tools/captcha_hook.py` — hook fetch/XHR rekam flow ✅
- `tools/captcha_flow.py` — tunggu captcha + crop ✅
- `tools/ui_solver.py` — human_move/click/drag ✅
- `tools/slider_puzzle.py` — analyze (variance) ✅
- `tools/gap_detect.py` — color-based gap ✅
- `tools/slider_solver.py` — grab + find_gap ✅

## 🎯 Jalan keluar (kalau dilanjut)

1. **Rect puzzle presisi** — butuh tembus surface SDK:
   - `page.evaluate` dgn `document.querySelector('#anti_fraud_captcha').shadowRoot`
     (kalau shadow CLOSED → gak bisa; kalau OPEN → bisa)
   - ATAU hook SDK saat render canvas → catat rect via `HTMLCanvasElement.prototype.getBoundingClientRect`
2. **Hook render canvas** — wrap `CanvasRenderingContext2D.drawImage` untuk
   nangkap gambar puzzle MENTAH + posisi → offset eksak.
3. Setelah rect+gambar dapat → `gap_x - piece_x` → geser → verify → OTP.

**Semua terbukti kecuali rect presisi (surface tertutup).** Mekanisme solver
100% jalan — tinggal sumber koordinat.

## Catatan
- Captcha flaky (~1/3 render), rate-limit "Telah terjadi kesalahan".
- Butuh jeda antar percobaan + kemungkinan IP residential ID.

---

## Opsi L — hook getBoundingClientRect + drawImage (HASIL)

Hook `Element.prototype.getBoundingClientRect` + `CanvasRenderingContext2D.drawImage`
dipasang sebelum load:

```
drawCalls: 2
lastDrawn: {"src":"img","w":44,"h":44}    ← hanya GRIP slider (44x44) yang di-draw
MID RECTS: []                               ← rect puzzle TIDAK ada di DOM
```

**Kesimpulan:** canvas grip (44×44) di-render biasa. **Puzzle background/layer
besar TIDAK muncul** sbg element DOM ataupun drawImage biasa → render via:
- WebGL context / offscreen canvas, ATAU
- CSS background-image pada surface tertutup (sdK)

Rect puzzle presisi **tidak tersedia** dari hook DOM/canvas standar.

**Verifikasi final:** puzzle = surface internal SDK yang tidak mengekspos
geometri ke DOM/JS page context. Deteksi harus murni dari piksel screenshot
(tidak stabil), atau hook lebih dalam (WebGL context, `OffscreenCanvas`).

## Wall nyata (ringkas)
- Puzzle Shopee dirender di surface tertutup (bukan DOM/img/canvas biasa).
- Semua cara standard (DOM query, frame traversal, shadow root, getBoundingClientRect,
  drawImage hook) **gagal** menemukan rect puzzle.
- Mekanisme solver (drag→verify) TERBUKTI jalan; hanya sumber koordinat akurat
  yang jadi dinding.

## Rekomendasi realistis
1. Hook `WebGLRenderingContext.prototype.texImage2D` / `OffscreenCanvas` — cari
   texture puzzle + dimensi.
2. ATAU **template-match** pada crop penuh (tidak presisi tanpa rect).
3. ATAU **pendekatan berbeda**: login via akun existing / OTP-only path bila ada.

---

## Opsi L (WebGL/OffscreenCanvas hook) — HASIL FINAL

Hook `texImage2D` (WebGL 1&2), `OffscreenCanvas.getContext`, `drawImage`, `getImageData`:

```
offscreen: 18       (OffscreenCanvas dipakai — utk fingerprint canvas)
draw: 2             (drawImage 2x — grip)
tex entries: 84     (mayoritas getImageData kecil 10x10/1x1 — anti-bot pixel probe)
```

**Tidak ada `texImage2D`** (WebGL tidak dipakai render puzzle).
`getImageData` 12,18,10x10 + scan 1x1 = **fingerprint canvas SDK**, bukan puzzle.

**Kesimpulan definitif:** puzzle captcha **tidak di-render lewat**:
- DOM (query/frame/shadow) ❌
- getBoundingClientRect ❌
- drawImage ❌
- WebGL texImage2D ❌
- OffscreenCanvas ❌

Puzzle ada di **surface yang sepenuhnya tertutup** dari JS page context
(kemungkinan browser compositor layer / closed system). **Tidak ada jalur
standard** untuk membaca geometri/gambar puzzle dari halaman.

## 🧱 DINDING DEFINITIF

Semua jalur ekstraksi koordinat puzzle yang standard **sudah dicoba & gagal**:
DOM → frame → shadow → rect-hook → drawImage → WebGL → OffscreenCanvas.

## ✅ Yang TETAP terbukti & bernilai

- Chain signup penuh (nomor nyata) → captcha render ✅
- **Drag → verify endpoint terpanggil** (SDK encrypt sendiri) ✅
- Struktur puzzle (piece kiri, gap tengah) ✅
- Semua respons API + kripto skema ✅

**Mekanisme solver 100% jalan. Yang tak bisa = membaca koordinat puzzle dari
halaman (surface tertutup).**

## Jalan realistis tersisa
1. **Piksel dari screenshot** (butuh rect → tidak stabil) — sudah dicoba.
2. **Model visi** baca celah dari screenshot penuh → kirim drag berulang
   (brute-force terarah; mahal, berisiko flag).
3. **Jalur berbeda**: login (bukan signup), Google/FB OAuth, atau app Android
   (butuh device arm64 — terbukti crash di emulator).
