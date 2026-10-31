# INDEX — Peta Semua Dokumen

Daftar seluruh file `.md` dalam package ini, dikelompokkan berdasarkan fungsi.

---

## Root

| File | Untuk siapa | Isi |
|---|---|---|
| `README.md` | **manusia** | Apa project ini, kenapa, fitur, cara pakai, hasil |
| `AGENTS.md` | **AI agent** | Invariant, titik masuk kode, aturan operasional |
| `INDEX.md` | keduanya | File ini |

Baca `README.md` dulu kalau kamu manusia. Baca `AGENTS.md` dulu kalau kamu agent.

---

## `docs/` — Dokumentasi Teknis (ditulis ulang)

Tujuh dokumen yang dirancang sebagai referensi lengkap, bukan catatan mentah.

| File | Isi | Panjang |
|---|---|---|
| `PROJECT-DEEP-DIVE.md` | Semua detail project: peta repo, lapisan, chain, captcha, cache, key, reputasi, RE, keputusan, jalan buntu, angka | paling lengkap |
| `ARCHITECTURE.md` | Aliran data, tanggung jawab modul, konkurensi, state machine | struktur |
| `SIGNUP-CHAIN.md` | Request/response asli tiap langkah, header, klasifikasi | payload |
| `CAPTCHA-SYSTEM.md` | Tiga jenis captcha, protokol SadCaptcha, trajectory, release, cache | protokol |
| `ANTIFRAUD-RE.md` | VM SAP, string tables, JIT, Sense SDK, sz-token, fingerprint | hasil RE |
| `OPERATIONS.md` | Runbook harian: cek, plan, run, cron, pemulihan, backup | operasional |
| `TROUBLESHOOTING.md` | Gejala → penyebab → fix, plus daftar "bukan bug" | debugging |

### Urutan baca yang disarankan

**Pertama kali:**

```
1. README.md
2. docs/ARCHITECTURE.md
3. docs/PROJECT-DEEP-DIVE.md   (bagian 1–5 dulu)
```

**Mau mengubah kode:**

```
1. AGENTS.md                  ← wajib
2. docs/ARCHITECTURE.md
3. docs/SIGNUP-CHAIN.md
4. docs/CAPTCHA-SYSTEM.md
```

**Sedang debug:**

```
1. docs/TROUBLESHOOTING.md
2. docs/OPERATIONS.md         (bagian pemulihan)
```

**Mau paham reverse engineering:**

```
1. docs/ANTIFRAUD-RE.md
2. project/VM_100_PERCENT.md
3. project/REFINGERPRINT.md → RE_FINGERPRINT.md
4. project/VM_JIT_BREAKTHROUGH.md
```

---

## `project/` — 50 Dokumen Riset Asli

Dokumen ini ditulis selama proses pengembangan. Isinya data mentah, hasil
uji, dan catatan sesi. Lebih detail dari `docs/` tapi kurang terstruktur.

### Status & Kesimpulan

| File | Isi |
|---|---|
| `KESIMPULAN_PROJECT.md` | Ringkasan arsitektur + roadmap + verdict cache |
| `LAPORAN_AKHIR.md` | Laporan akhir misi RE |
| `REVERSE_STATUS.md` | Status lengkap reverse engineering |
| `SESSION_UPDATE.md` | Update sesi pengembangan |
| `SESSION_2026-10-15-FINAL.md` | Sesi final pure-API reverse |
| `P1_P2_P3_SELESAI.md` | Produksi stabil: cache v2, reputasi, worker pool |
| `OPTION_A_STATUS.md` | Status opsi produksi A |
| `MILESTONE_RESULTS.md` | Pipeline otomatis penuh |

### VM SAP (reverse engine anti-fraud)

| File | Isi |
|---|---|
| `VM_100_PERCENT.md` | Status final: 100% ter-reverse |
| `VM_JIT_BREAKTHROUGH.md` | Temuan bahwa VM = JIT source generator |
| `VM_DEOBF_COMPLETE.md` | Deobfuscation interpreter selesai |
| `VM_ANALYSIS.md` | Analisis encoding & dispatch |
| `VM_MEMORY_MODEL.md` | Model memori + frame |
| `VM_EMULATOR_STATUS.md` | Status emulator |
| `LAPORAN_VM_NIGHT.md` | Laporan sesi malam |
| `LAPORAN_VM_SESI2.md` | Laporan sesi 2 |
| `SESSION_REPORT_3TASK.md` | Laporan 3 task RE |

### Captcha & Crypto

| File | Isi |
|---|---|
| `CAPTCHA_RE_RESULTS.md` | RE bundle captcha (800 KB → 21.714 baris) |
| `CAPTCHA_CRYPTO_RESULTS.md` | Skema enkripsi captcha |
| `CRYPTO_RSA_RESULTS.md` | RSA-1024 reverse |
| `CRYPTO_REIMPL_RESULTS.md` | Reimplementasi crypto |
| `SADCAPTCHA_API_BREAKTHROUGH.md` | Fix error 400 (trajectory) |
| `SADCAPTCHA_RESULTS.md` | Hasil integrasi SadCaptcha |
| `API_SOLVER_README.md` | Dokumentasi solver API |
| `SOLVER_E2E_RESULTS.md` | Solver end-to-end |
| `SOLVER_FINAL_STATUS.md` | Status final: dinding surface tertutup |
| `UI_SOLVER_RESULTS.md` | Solver UI-driven |
| `VISION_LOOP_RESULTS.md` | Visi loop + dekripsi |
| `TEMPLATE_MATCH_RESULTS.md` | Template match |
| `SLIDER_SOLVER_RESULTS.md` | Image-diff slider |
| `GAP_V2_RESULTS.md` | Gap detection v2 |
| `MULTI_GRID_RESULTS.md` | Multi-offset grid |
| `MULTI_ATTEMPT_RESULTS.md` | Multi-attempt + struktur celah |
| `SLOT_TUNING_RESULTS.md` | Tuning deteksi slot |
| `ONESHOT_RESULTS.md` | One-shot solver |
| `BREAKTHROUGH_RESULTS.md` | Captcha tembus |

### API & Fingerprint

| File | Isi |
|---|---|
| `RE_FINGERPRINT.md` | Cara `security_device_fingerprint` bekerja |
| `FULL_API_REVERSE.md` | RE API penuh (endpoint + crypto) |
| `API_REVERSE_RUNBOOK.md` | Runbook replikasi pure-API |
| `SNIFF_A_RESULTS.md` | Endpoint signup (live, terverifikasi) |
| `FRIDA_HOOK_RESULTS.md` | Hook SHPSSDK via Frida |

### Emulator & Infrastructure

| File | Isi |
|---|---|
| `EMULATOR_E2E_RESULTS.md` | Emulator end-to-end |
| `EMULATOR_ARM64_RESULTS.md` | Emulator ARM64 (buntu) |
| `XVFB_RESULTS.md` | Xvfb non-headless |
| `PROXY_ID_RESULTS.md` | Proxy Indonesia + pipeline |
| `PROXY_NUM_RESULTS.md` | Proxy + nomor |
| `REAL_PHONE_RESULTS.md` | Nomor HP nyata |
| `FARM_RUNNER_RESULTS.md` | Runner farm + tes OTP |
| `RESTORE_GUIDE.md` | Backup & restore |

---

## `skill/` — 13 Skill

Skill operasional dalam format `SKILL.md`. Dipakai agent untuk muat konteks
saat mengerjakan tugas terkait.

### Inti Shopee

| Skill | Isi |
|---|---|
| `shopee-captcha-solver/` | Solver captcha Shopee + 5 references (source SadCaptcha, REA setup, SAP reverse, string tables, Sense SDK) |
| `sadcaptcha-shopee-api/` | Protokol SadCaptcha: schema, algoritma, pitfall, cache-first |
| `shopee-antifraud-reversing/` | RE x-sap-sec / Sense SDK / sz-token |
| `shopee-sms-otp-bypass/` | Registrasi via OTP SMS tanpa captcha |
| `shopee-va-digital-order/` | Ekstraksi VA produk digital |
| `shopee-bank-va-channels/` | Matriks channel bank untuk VA |
| `shopee-token-war-stack/` | War token PLN + `references/pln-order-flow.md` |

### Farm & Infrastruktur

| Skill | Isi |
|---|---|
| `browser-signup-farming/` | Farm signup via browser + proxy |
| `app-account-farming/` | Bypass deteksi new-user dengan device spoofing |
| `captcha-solver-api-integration/` | Integrasi API solver captcha |
| `farmed-account-validation/` | Membuktikan akun hasil farm benar-benar jalan |
| `proxy-pool-operations/` | Bangun, validasi, dan rotasi proxy pool |
| `browser-pool-concurrency/` | Scaling headless browser |

---

## `reference/` — Artefak Reverse Engineering

Data mentah. Jangan dihapus, butuh berhari-hari untuk dibuat ulang.

| Folder | Isi |
|---|---|
| `captcha_re/` | `bundle.js`, `bundle.pretty.js`, `aes_keys.json`, `captcha_bodies.json`, `captcha_flow.jsonl`, `hook_inject.js` |
| `captures/` | Session capture asli (request + response lengkap) |
| `sdk/strings_decoded.txt` | 1.555 + 2.592 string ter-decode |
| `sdk/strings_sfu.txt` | String untuk signing |
| `sdk/vm_dispatch_full.txt` | Dispatcher VM |
| `sdk/sadcaptcha_ref/` | Referensi extension SadCaptcha (script.ts, api.py, api-docs.json) |

---

## Cara Mencari Sesuatu

### Cari kata kunci di semua dokumen

```bash
grep -rn "slide_piece_trajectory" --include="*.md" .
grep -rn "Identifikasi Tambahan" --include="*.md" .
grep -rn "8003001" --include="*.md" .
```

### Cari di kode

```bash
grep -rn "def hold_account" project/
grep -rn "proxy_lock" project/
```

### Cari di hasil riset

```bash
ls project/*.md | xargs grep -l "cache" | head
```

---

## Ringkasan Cepat

| Kalau kamu butuh… | Buka |
|---|---|
| Paham project dalam 10 menit | `README.md` |
| Edit kode tanpa merusak | `AGENTS.md` |
| Payload request yang benar | `docs/SIGNUP-CHAIN.md` |
| Protokol captcha lengkap | `docs/CAPTCHA-SYSTEM.md` |
| Hasil reverse VM | `docs/ANTIFRAUD-RE.md` |
| Jalankan batch | `docs/OPERATIONS.md` |
| Perbaiki error | `docs/TROUBLESHOOTING.md` |
| Konteks historis keputusan | `project/KESIMPULAN_PROJECT.md` |
| Angka mentah tiap eksperimen | `project/*_RESULTS.md` |
| Prosedur operasional agent | `skill/*/SKILL.md` |
