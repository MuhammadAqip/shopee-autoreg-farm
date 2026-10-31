# SAP / sz-sdk Anti-Fraud — Reverse (FINAL, 2026-10-16)

Ringkasan tuntas: apa yg dipecah, apa yg terbuka, apa yg masih VM.

## Rantai lengkap

```
Page → worker (blob + af388a21...worker.js)
  → SAP SDK (module 30914, "shopee__web_enhance_sap", di-load via initNewSAPSDK)
  → createSecureFetchUtils → request interceptor inject header:
        x-sap-ri / x-sap-sec / sz-token / af-ac-enc-sz-token /
        af-ac-enc-dat / x-sz-sdk-version / device_sz_fingerprint
  → POST df.infra.sz.shopee.co.id/v2/shpsec/web/report  (payload binary)
  → verify: /verify/traffic , /verify/traffic/error
```

## Header (SEMUA ketemu)

```
x-sap-ri             = 52 hex (timestamp+nonce+seq+marker+sig)
x-sap-sec            = b64 ~2400-2640B (signed blob)
sz-token             = b64|b64|b64|08|<plat>  == SAMA dgn riskToken!
af-ac-enc-sz-token   = b64(16B IV)|b64(~68B enc)|b64(12B GCM nonce)|08|<plat>
af-ac-enc-dat        = header terenkripsi lain
device_sz_fingerprint = nama header
x-sz-sdk-version     = versi SDK
```

## x-sap-ri — STRUKTUR ✅ (verified 9 req, timestamp cocok)

```
52 hex = 26 bytes (BIG-ENDIAN utk multi-byte):
[0:4]  = unix timestamp (detik)
[4:8]  = nonce/acak
[8:12] = seq/counter
[12:14]= marker 0x1201
[14:26]= signature (19 byte, dari VM signer)
```
Contoh: `793ad16a`→04:41:29, `7e3ad16a`→04:41:34, `833ad16a`→04:41:39 (naik konsisten).

## sz-token / riskToken — STRUKTUR ✅

```
b64(16B)|b64(64B)|b64(12B)|08|<platform>
[0] 16B = id/hash
[1] 64B = SIGNATURE (SHA-512 / Ed25519)
[2] 12B = nonce/MAC
[3] "08" marker  [4] platform 1/2/3
```
`sz-token` == `riskToken` == nilai di device_info (Sense) — IDENTIK.
riskToken berasal dari native bridge `callHandler("getRiskToken")` (modul 8094.js).

## af-ac-enc-sz-token — struktur

`b64(IV:16B)|b64(enc:~68B)|b64(GCM-nonce:12B)|08|<plat>`
= sz-token terenkripsi (AES, kemungkinan GCM: ada 12B nonce). Kunci dari SAP handshake.

## Aset (semua tersimpan di /root/shopee-farm/sdk/)

| Modul | URL | Catatan |
|---|---|---|
| **SAP SDK** | `sfu-stable.<hash>.2023.js` | createSecureFetchUtils + initNewSAPSDK + semua header string |
| SAP module | `shopee__web_enhance_sap/2.48.632-r` | 411KB, obfuscated |
| Sense SDK | `8094.<hash>.2023.js` | payload AES (SUDAH dipecah) |
| browser-signals | `bundle.<hash>.js` | WebGL fingerprint collector (readable) |
| DynamicCollector | `DynamicCollectorSDK.<hash>.2023.js` | WebGL fp |
| Worker | `af388a216703068c.worker.js` | importScripts(ruleSetName) |

## String decoder — DIPECAH ✅

File `sfu-stable` pakai string table `aj()` (1555 string) + decoder `ak()`:
- alphabet kustom: `ofksgblrxcamqiunzpthjwydevYDSVHBOZKWEGFXCMINTJARQLPU1357249806+/=`
- reimpl Python: `ak_decode.py` (`ak_decode()`, `load_table()`). Terverifikasi 100%.
- dump semua string: `sdk/strings_sfu.txt`
- string penting: `cefSharp`, `vmp_getPubKeyClientCapabilities`, `pubKeyCredParams`,
  `__WIR_SZ_UNIQ_DC`, `vmp_getWebdriverEvidence`, endpoints IVS.

## TEMBOK: VMP (VM obfuscation)

Signer `_ = O[ad("0x393")](payload, config)` dijalankan via **VM bytecode interpreter**
(`ac[_++]`, `tO`, `tE` — virtual machine). Fungsi sensitif dinamai `vmp_*`
(vmp_getPubKeyClientCapabilities, vmp_getWebdriverEvidence, vmp_truncateUtf8String).
Reversing VM penuh = proyek besar. `ad()`/`X()` pakai offset table terpisah dari `ak()`.

TAPI: struktur x-sap-ri & sz-token sudah pecah. Yang tersisa hanya 19-byte signature
di dalam x-sap-ri (di-generate VM) — tidak perlu untuk banyak use-case.

## Verifikasi

- `sap_hook.py` → 8 req w/ x-sap-ri/sec ✅
- `sap_signer_capture.py` → 9 req, timestamp x-sap-ri cocok ✅
- `ak_decode.py` → decode string table 100% akurat ✅
- `sense_decrypt.py` → CRC varian + magic + AES ✅
