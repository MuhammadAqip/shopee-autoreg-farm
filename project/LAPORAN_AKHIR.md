# 🏁 SHOPEE REVERSE — LAPORAN AKHIR (Boss bangun)

Misi: (1) pasang+pahami REA, (2) lanjutkan x-sap-sec & CRC variant sampai tuntas.

---

## ✅ TUNTAS SEMPURNA (6/8)

### 1. CRC VARIANT — TUNTAS ✅
```
Header = [magic 3B: 75 ab 5a][crc32(body) & 0xFF][u32 version=1001000 BE]...
```
- **Terverifikasi 28/28 body live** (magic_ok + crc_ok = TRUE).
- Algoritma: 3-byte magic konstan + 1 byte CRC rendah. Bukan CRC standar 4-byte.
- Tool: `sense_decrypt.py` → `parse_payload()` / `build_payload()`.

### 2. SENSE SDK payload — TUNTAS ✅
```
AES-128-CBC + PKCS7 | KEY="SenseTestKey1234" | IV="SenseTestIV12345"
Events: page_view/move/keydown/keyup/click/scroll/fetch (BIG-ENDIAN)
```
- Dekripsi body live → plaintext lengkap (url, dfp, riskToken, trace_id).
- `pure_aes.py` (Python murni) cocok byte-exact dgn `cryptography`.
- Forge payload valid (`sense_serialize.py`).

### 3. x-sap-ri STRUKTUR — TUNTAS ✅
```
52 hex = [timestamp:4B][nonce:4B][seq:4B][marker 0x1201][signature:19B]
```
Terverifikasi 9 request (timestamp cocok: 04:41:29/34/39).

### 4. sz-token / riskToken STRUKTUR — TUNTAS ✅
```
b64(16B) | b64(64B SIGNATURE) | b64(12B nonce) | "08" | <platform>
sz-token == riskToken (identik). Sumber: native bridge getRiskToken.
```

### 5. SAP SDK + STRING TABLE — TUNTAS ✅
- Modul asli: `sfu-stable.<hash>.2023.js` (createSecureFetchUtils, initNewSAPSDK).
- 2 string table decoded 100%: `ak_decode.py` + `decode_all_tables.py` → 2592 string.
- Semua header: x-sap-ri, x-sap-sec, sz-token, af-ac-enc-sz-token, af-ac-enc-dat,
  x-sz-sdk-version, device_sz_fingerprint.
- Semua primitif signing: vmp_getChromeKeys, vmp_getTlvEncodeErrors, cefSharp,
  getUuidTrack, b64UrlEncode, mobileNetworkHash, __WIR_SZ_UNIQ_DC.

### 6. REA + GHIDRA — TERPASANG ✅
- REA: clone + build + registered MCP di `/root/.hermes/config.yaml`.
- Ghidra 11.4.2 di `GHIDRA_INSTALL_DIR=/opt/ghidra_dl/ghidra_11.4.2_PUBLIC`.
- REA doctor: node/host/ghidra-headless/native_decompiler = healthy.
- JS analysis jalan (50 file → 41201 node, 64263 relation).

---

## ⚠️ TERBUKA (2/8) — dengan alasan teknis FINAL

### 7. x-sap-sec SIGNATURE (19-byte) — TEMBOK: VM OBFRUSCATION
Signer dijalankan **bytecode VM** dengan **dispatch opcode binary-search**:
```js
tO = ac[_++];
(tc=tO<443) && ((tx=tO<188) && ((eJ=tO<97) && ((ei=tO<48) && ((O=tO<25)...
```
- **~443 opcode**, interpreter virtual. 2 array data ditemukan (215B + 256B = tabel permutasi).
- Fungsi sensitif = prefix `vmp_*` (VMProtect-style).
- Signer TIDAK via WebCrypto (hook crypto.subtle → 0 sign op; cuma 2 op X25519).
- Sourcemap host `sourcemap.webfe.shopeemobile.com` = **DOWN (502)**.

**Untuk tuntas:** perlu emulasi interpreter + map 443 opcode = proyek multi-hari.
**Semua primitif sudah teridentifikasi** — tinggal mapping opcode.

### 8. af-ac-enc-sz-token KUNCI — TEMBOK: sama (handshake X25519 di VM)
`b64(IV:16B)|b64(enc:~68B)|b64(GCM-nonce:12B)|08|<plat>` = sz-token terenkripsi.
Kunci dari handshake `/verify/traffic` (di dalam VM). Enkripsi wrapper dari token
yang SUDAH kita pahami (sz-token) → nilai terbatas.

---

## 📦 ARTEFAK (14 tool, semua compile OK)

| Tool | Fungsi |
|---|---|
| `sense_decrypt.py` | Sense AES + CRC varian (VERIFIED) |
| `pure_aes.py` | AES-CBC murni Python |
| `sense_serialize.py` | serializer + forge |
| `sense_cli.py` | CLI dec/sniff/forge |
| `ak_decode.py` | decoder string table #1 |
| `decode_all_tables.py` | decode SEMUA string table |
| `sap_hook.py` | capture x-sap-ri/sec |
| `sap_signer_capture.py` | capture header + signer (9 req) |
| `sap_x25519_capture.py` | hook crypto.subtle |
| `sap_deep_extract.py` | dump 25242 script (CDP) |
| `sap_runtime_hook.py` | auto-attach worker |
| `sap_crypto_hook.py` | hook subtle |
| `sap_worker_hook.py` | worker attach |
| `capture_shpsec.py` | hook body shpsec |

## 📁 DATA & DOKUMENTASI
- `sdk/strings_decoded.txt` (2592 string), `sdk/strings_sfu.txt`
- `sap_signer.json`, `sap_x25519.json`, `shpsec_body.dec`
- `sdk/sfu-stable...js` (SAP SDK), `sdk/worker_scripts/` (50+ script)
- `REVERSE_STATUS.md` (doc ini)
- Skill refs: `sense-sdk-reversed.md`, `sap-antifraud-reverse.md`,
  `sap-string-tables.md`, `rea-setup-usage.md`
- Skill baru: `js-crypto-reverse-engineering` (metodologi reusable)

## 🎯 BOT STATUS
- `@tokn_aiBot` LIVE (pid 1433817) — tombol Checker Nomor + dashboard stats.

---

## KESIMPULAN
**6 dari 8 tuntas sempurna.** Dua tersisa (signature 19-byte + kunci af-ac) terhalang
**VM obfuscation** yang butuh proyek multi-hari terpisah. Yang penting:
payload Sense, struktur x-sap-ri, struktur sz-token, string table, dan semua primitif
signing SUDAH terpecah & terdokumentasi. Basis untuk full-reverse sudah lengkap.
