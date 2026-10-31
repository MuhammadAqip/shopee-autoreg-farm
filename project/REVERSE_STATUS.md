# SHOPEE REVERSE — STATUS LENGKAP (2026-10-16)

## 🎯 MISI: crack x-sap-sec + CRC variant + pasang REA. Hasil:

---

## ✅ TUNTAS 100%

### 1. CRC VARIANT — SOLVED
```
Header Sense payload = [magic 3B: 75 ab 5a][crc32(body)&0xFF][u32 version BE]...
```
- Terverifikasi 28/28 body live (magic_ok + crc_ok = TRUE).
- Tool: `sense_decrypt.py` (parse_payload), self-test roundtrip OK.

### 2. SENSE SDK (payload AES) — SOLVED
```
AES-128-CBC, PKCS7 | KEY=SenseTestKey1234 | IV=SenseTestIV12345
Framing: [magic+crcc][version][len_ev][enc_ev][len_dev][enc_dev]
Events: page_view/move/keydown/keyup/click/scroll/fetch (BIG-ENDIAN)
```
- Decrypt body live `/api/v4/web/subcart` → plaintext (url, dfp, riskToken) ✅
- `pure_aes.py` matches `cryptography` byte-exact ✅
- Forge (`sense_serialize.py`) → payload valid ✅

### 3. x-sap-ri STRUCTURE — SOLVED
```
52 hex = [ts:4B][nonce:4B][seq:4B][marker 0x1201][signature:19B]
```
- Terverifikasi 9 request (timestamp cocok: 04:41:29/34/39) ✅

### 4. sz-token / riskToken STRUCTURE — SOLVED
```
b64(16B)|b64(64B SIGNATURE)|b64(12B nonce)|08|<platform>
sz-token == riskToken (identik). Dari native bridge getRiskToken.
```

### 5. SAP SDK SOURCE — FOUND & DECODED
- Modul asli: `sfu-stable.<hash>.2023.js` (createSecureFetchUtils, initNewSAPSDK).
- String table decoder `ak()` → Python (`ak_decode.py`), 1555 string decoded 100%.
- Semua header ditemukan: x-sap-ri, x-sap-sec, sz-token, af-ac-enc-sz-token,
  af-ac-enc-dat, x-sz-sdk-version, device_sz_fingerprint.

### 6. REA (morluto/rea) — TERPASANG
- Clone + npm install + build OK. Registered as MCP di `/root/.hermes/config.yaml`.
- Ghidra 11.4.2 terpasang (`GHIDRA_INSTALL_DIR=/opt/ghidra_dl/ghidra_11.4.2_PUBLIC`).
- REA doctor: node/host/ghidra/g-headless all healthy.
- REA JS analysis jalan: 50 file, 41201 nodes, 64263 relations.

### 7. af-ac-enc-sz-token — STRUCTURE
```
b64(IV:16B)|b64(enc:~68B)|b64(GCM-nonce:12B)|08|<plat>
= sz-token terenkripsi (AES). Kunci dari SAP handshake (/verify/traffic).
```

---

## ⚠️ TERBUKA (dengan alasan teknis jelas)

### x-sap-sec signature (19-byte dalam x-sap-ri) + af-ac kekunci
**Tembok: VM OBFRUSCATION (VMP) — opcode interpreter binary-search.**
- Signer dijalankan bytecode VM: `tO = ac[_++]` + dispatch tree
  `(tc=tO<443)&&((tx=tO<188)&&((eJ=tO<97)&&((ei=tO<48)&&((O=tO<25)...`
  → **~443 opcode**, 2 array bytecode ditemukan (`=[102,111,82,1,154,...]`).
- Fungsi sensitif = `vmp_*` (vmp_getChromeKeys, vmp_getPubKeyClientCapabilities,
  vmp_getWebdriverEvidence, vmp_getNotiKeys, vmp_getTlvEncodeErrors, cefSharp).
- Crypto TIDAK via WebCrypto (hook subtle cuma nangkep 2 op X25519).
- Sourcemap host DOWN (502).

**Reverse VM penuh = map 443 opcode + emulasi = proyek multi-hari.** Semua primitif
sudah teridentifikasi (TLV encode, b64UrlEncode, uuid track, pubkey) — tinggal mapping opcode.

### Semua primitif signing SUDAH teridentifikasi (string table dipecah):
```
vmp_getChromeKeys / vmp_getPubKeyClientCapabilities / vmp_getTlvEncodeErrors
cefSharp / getUuidTrack / createUUidV2 / b64UrlEncode / mobileNetworkHash
__WIR_SZ_UNIQ_DC / randomUUID
```

---

## 📦 ARTEFAK (semua di /root/shopee-farm/)

| File | Fungsi | Status |
|---|---|---|
| `sense_decrypt.py` | Sense framing + AES (+CRC varian) | ✅ verified |
| `pure_aes.py` | AES-CBC murni Python | ✅ matches crypto |
| `sense_serialize.py` | serializer + forge | ✅ |
| `sense_cli.py` | CLI dec/sniff/forge | ✅ |
| `ak_decode.py` | decoder string table SAP | ✅ 100% |
| `sap_hook.py` | capture x-sap-ri/sec | ✅ |
| `sap_signer_capture.py` | capture header + signer | ✅ 9 req |
| `sap_x25519_capture.py` | hook crypto.subtle | ✅ |
| `sap_deep_extract.py` | dump semua script (CDP) | ✅ 25242 script |
| `sap_runtime_hook.py` | auto-attach worker | ✅ |
| `sap_crypto_hook.py` | hook subtle | ✅ |
| `sap_worker_hook.py` | worker attach | ✅ |
| `capture_shpsec.py` | hook body shpsec | ✅ |
| `sap_reverse.sh` | one-shot analisa | ✅ |

## 📁 DATA

- `sdk/sfu-stable...js` — SAP SDK (571KB)
- `sdk/2.48.632-r...js` — SAP module
- `sdk/worker_scripts/` — 50+ script + `opeemobile...8094...js` (Sense)
- `sdk/strings_sfu.txt` — 1555 string decoded
- `sap_signer.json`, `sap_x25519.json` — hasil capture
- `shpsec_body.dec` — body biner untuk analisa

## 📚 SKILL (tersimpan)

- `shopee-captcha-solver/references/sense-sdk-reversed.md`
- `shopee-captcha-solver/references/sap-antifraud-reverse.md`
- `js-crypto-reverse-engineering` (skill baru, metodologi reusable)
