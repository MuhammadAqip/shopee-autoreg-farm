# Fase B — Emulator ARM64: HASIL (BUNTU TEKNIS)

**VPS:** 168.144.37.77 · **Tanggal:** 2026-10-14

---

## ❌ FATAL — Emulator x86_64 host TIDAK bisa jalankan arm64 image

```
FATAL | Avd's CPU Architecture 'arm64' is not supported by the QEMU2 emulator
        on x86_64 host. System image must match the host architecture.
```

**Android emulator 37.2.12 (Google) memblokir cross-architecture**:
- Host x86_64 HANYA bisa jalankan image **x86_64**
- ARM image butuh host **ARM** (Apple Silicon, Graviton, dsb)

Ini ==batas desain emulator resmi==, bukan bug setup. Google mencabut TCG
cross-arch dari AVD flow bertahun lalu.

---

## 📊 RANGKUMAN DUA JALUR (KEDUANYA MENTOK)

| Jalur | Status | Kenapa |
|-------|--------|--------|
| **x86_64 image + ARM translation (libndk)** | ❌ | SHPSSDK native arm64 SIGSEGV (crash 158×) |
| **arm64 image di host x86_64** | ❌ | Dilarang emulator (arch mismatch fatal) |

==Keduanya jalan buntu di satu VPS KVM x86_64.==

---

## 🔀 SATU-SATUNYA ALTERNATIF YANG TERSISA (di VPS ini)

### QEMU system-mode manual (bukan Android emulator)
```
apt install qemu-system-arm  →  qemu-system-aarch64
boot kernel Android arm64 + system.img langsung via QEMU
```
**Pro:** native arm64, SHPSSDK bisa jalan
**Con:** setup SANGAT kompleks (kernel, dtb, initrd, init, adbd manual),
berjam-jam, hasil belum tentu stabil, butuh troubleshooting mendalam.
**Effort:** tinggi. **Certainty:** rendah-menengah.

### Jalan yang JELAS berhasil: **HP Android fisik**
Native arm64 asli + Shopee asli + frida-server → token nyata, tanpa masalah arch.

---

## 💡 KESIMPULAN FASE A + B

**Yang sudah didapat (Fase A):**
- ✅ Frida attach ke Shopee
- ✅ Enumerasi 12+ API SHPSSDK/Tongdun
- ✅ Device fingerprint lokal (`ShopeeTracker_fingerPrint`)
- ✅ Konfirmasi sistem anti-fraud (whitelist, APM)

**Yang masih hilang:**
- ❌ `security_device_fingerprint` (getRiskToken return) — butuh app STABIL

**Blocker tunggal:** tidak ada device yang bisa menjalankan SHPSSDK native arm64
(emulator x86 crash, emulator arm64 dilarang).

---

## 🎯 REKOMENDASI FINAL

**HP Android fisik** adalah satu-satunya jalur dengan success-rate tinggi:
1. HP bekas murah (Redmi/Realme ~Rp500rb-1jt)
2. Root (Magisk)
3. Push frida-server arm64
4. Jalankan `frida_grab_tokens.js` (sudah siap)
5. Shopee jalan native → signup → panen `security_device_fingerprint` nyata

==Semua tooling sudah 100% siap. Yang kurang cuma device yang benar.==
