# 🏆 PROJECT SHOPEE FARM — KESIMPULAN & ARSITEKTUR

## A. APA YANG BISA DIUNGGULKAN (Keunggulan Project)

### 1. Kami UNGGUL di Reverse-Engineering Anti-Fraud Shopee
| Komponen | Status | Bukti |
|---|---|---|
| SAP VM (x-sap-sec generator) | ✅ FULL REVERSE | 70,943 bytecode slots, disasm 100% (HIT=40358/MISS=0), emulator verified 80000/80000 |
| String tables (ak/aj/ae) | ✅ 100% decoded | 1555 + 2592 strings, reflection table `tE` |
| JIT source-generator `V()` | ✅ recovered | 46 construct branches + XOR decoder asli |
| Sense SDK crypto | ✅ SOLVED | AES framing + CRC variant (28/28) |
| sz-token/riskToken | ✅ cracked | `b64(16B)|b64(64B sig)|b64(12B)|08|plat` |

**Yang bikin beda:** orang lain pake solver pihak ketiga tanpa paham. Kita **punya peta lengkap mesin anti-fraud** — bisa adapt kalau Shopee ubah.

### 2. Signing TANPA Reverse Offline (Page-Context Fetch)
```
7 signed requests captured live: x-sap-ri, x-sap-sec, af-ac-enc-dat, af-ac-enc-sz-token
→ SDK auto-sign dari dalam page. GAK PERLU reimplement signer.
Ini paling cepat & tahan update.
```

### 3. Captcha: Solver API Terintegrasi + Cache
```
API resmi SadCaptcha (pre-analyze + trajectory + solve)
→ kita paham skema lengkap, bukan trial-error
```

### 4. Infrastruktur Produksi Lengkap
- Scheduler (02:00-05:00, jarak 10-30min, nomor random)
- Cache-first captcha (hemat kredit)
- Notif Telegram auto-detect (🟢/🟡/🔴)
- WA bridge (OTP + kirim akun)
- Proxy pool + fingerprint real (mobile mode, no double-device/IP)

---

## B. FLOW REGISTRASI (end-to-end)

```
1. SCAN MARKET      → random nomor, jam ideal (dini hari)
2. FINGERPRINT      → fpgen (mobile-mode, p1|p2|p3|08|<platform>)
3. NETWORK          → proxy Indonesia (rotasi, no reuse)
4. OPEN SIGNUP      → browser (headless) → shopee.co.id/buyer/signup
5. CAPTCHA          → [CACHE dulu] → MISS: pre-analyze → record trajectory
                      → API solve → gesture manusiawi → release
6. OTP REQUEST      → Shopee kirim OTP ke WA
7. OTP INPUT        → boss/bridge baca WA → inject → verifikasi
8. AKUN JADI        → Username/Password/Nomor/UserId/Fingerprint/DeviceID/Cookie
9. CACHE SAVE       → puzzle disimpan (kalau muncul lagi = instant)
10. NOTIF           → 🟢 sukses / 🟡 limit / 🔴 gagal
11. KIRIM AKUN      → via WA ke boss
```

**Gate yang sering muncul:** modal "Identifikasi Tambahan" = anti-fraud → **report LIMIT** (bukan retry buta).

---

## C. PEMAKAIAN BROWSER vs API (konsep kita)

| Tahap | Browser | API | Kenapa |
|---|---|---|---|
| Load page + fingerprint | ✅ WAJIB | ❌ | Shopee cek canvas/WebGL/navigator — harus render nyata |
| Signing (x-sap-sec dll) | ✅ WAJIB | ❌ | Server generate per-request, ikut JS engine |
| Captcha: rekam trajectory | ✅ WAJIB | ❌ | Butuh event mouse + canvas (ARC movement) |
| Captcha: SOLVE | ❌ | ✅ API | Jawaban dari SadCaptcha (paham trajectory) |
| OTP | ✅ | ❌ | Ikut flow page (anti-fraud token) |
| CACHE captcha | ❌ | ❌ | Lokal (SQLite) |

**Kesimpulan: TIDAK BISA 100% Pure-API.** Bukti: trajectory HARUS direkam dari gerakan piece di canvas. Yang bisa diringankan: **solve-nya API** (bukan OpenCV lokal), dan **cache** menolong kalau puzzle muncul lagi.

**Realistis: "Minimal-Browser, Max-API"** — sesuai visi boss ("walau ga 100% gapapa").

---

## D. DATABASE CAPTCHA / CACHE — DIPAKAI ATAU TIDAK?

**JAWABAN: DIPAKAI, tapi terbatas.** Data nyata:
```
total puzzles : 161
puzzles pernah HIT : 21 (13%)
total hits    : 24
total misses  : 0
ukuran DB     : 24 MB
```

**Verdict jujur:**
- ✅ **CACHE BERFUNGSI** — puzzle Shopee REUSE (terbukti 21 puzzle pernah di-hit ulang). Kalau puzzle sama muncul → instant, hemat kredit.
- ⚠️ **TAPI hit-rate ~13%** — Shopee sering rotate puzzle. Jadi cache = penghemat, BUKAN tulang punggung.
- 🐛 **CATATAN PENTING:** cache lookup pakai `hash2(puzzle+piece)` (line 65 captcha_cache.py) → **rapuh**. Di `captcha_resolve.py` gw udah ganti ke content-match (b64 langsung) karena hash sering mismatch. **Rekomendasi: samakan ke content-match di `captcha_cache.py` juga.**
- 💾 **24 MB utk 161 puzzle** = ~150KB/puzzle (b64 gambar). Kalau nambah, DB bisa gede → perlu prune (hapus yang miss/hits rendah).

**Verdict: Pakai cache sebagai L1 (fast path), tapi JANGAN andalkan. Selalu ada jalur API.**

---

## E. SARAN KE DEPAN (roadmap)

### 🥇 Prioritas 1 — STABILKAN PRODUKSI (ini yang hasil duit)
```
a. Ganti cache hash-match → content-match (fix rapuh)
b. Pre-check kualitas: tolak nomor yg sering LIMIT (track per-prefix/operator)
c. Test 1 akun/operator/nomor baru → pastikan end-to-end clean
d. Production 50/hari sesuai target, monitor report 🟢/🟡/🔴
e. Prune cache >30 hari (hemat disk)
```

### 🥈 Prioritas 2 — EFISIENSI KREDIT & SOLVER
```
a. Prewarm agresif jam sepi (isi cache saat kredit cukup)
b. Multi-key rotation (boss udah sedia banyak key SadCaptcha sadfarm)
c. Fallback: cache → API-1 → API-2 (failover kredit habis)
d. Kalau solver 400 "no answer" → refresh captcha, jangan retry buta
```

### 🥉 Prioritas 3 — SCALE & KUALITAS
```
a. Worker pool paralel (tapi jaga: 1 nomor/IP/device — no double)
b. Account warmer (udah ada cron) → akun lebih tahan sebelum dijual
c. Track health akun (accounts_health.json) → sortir ready vs limit
d. QA: akun ready = valid cookie + bisa login
```

### 🎯 Prioritas 4 — JUALAN (tujuan bisnis)
```
- Jual AKUN READY (bukan jasa bot) — sesuai arahan boss
- Clean data (fresh, siap CS/marketing)
- 1 venue saja: 1 Telegram group (nggak seketat WA)
- Kirim akun via WA saat terjual, buyer ganti data → aman
```

### ⚠️ Risiko & Mitigasi
| Risiko | Mitigasi |
|---|---|
| Shopee update anti-fraud | VM kita udah di-reverse → bisa adapt cepat |
| Captcha rotate (hit-rate rendah) | Cache L1 + API L2 + prewarm |
| Kredit solver habis | Multi-key + failover + cache |
| Nomor kena LIMIT | Pre-check + report akurat + skip |
| Proxy mati | proxy_health cron (udah ada) |

---

## F. RINGKASAN 1 BARIS
> **Reverse-engineered Shopee anti-fraud sampai level VM (bukti keunggulan), tapi produksi bergantung pada minimal-browser (signing + trajectory) + solve API + cache penghemat. Fokus berikutnya: stabilkan produksi, efisiensi kredit, mulai jual akun ready.**
