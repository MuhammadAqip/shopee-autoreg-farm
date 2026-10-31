# SAP SDK — String Table & Signing Primitives (DIPECAH)

Dari `sfu-stable.<hash>.2023.js` (571KB). Semua string obfuscated via 2+ tabel.

## Dua string table + decoder

| Table | Fn | Alphabet | Jumlah |
|---|---|---|---|
| aj | `ak()` | `ofksgblrxcamqiunzpthjwydevYDSVHBOZKWEGFXCMINTJARQLPU1357249806+/=` | 1555 |
| ae | `ad()` | `evdqphkgrfmiotbyjlxczanswuTMBGWXRCAEPIZNHFLUDSVKOQJY4912758063+/=` | 1037 |

Decoder: b64(custom-alpha) → bytes → `%xx` → `decodeURIComponent` (handle blok parsial).
Reimpl: `ak_decode.py` / `decode_all_tables.py`. Hasil: `sdk/strings_decoded.txt` (2592 string).

## Header (nama literal di source)

```
b = "device_sz_fingerprint"
G = "sz-token"
D = "af-ac-enc-sz-token"
g = "x-sz-sdk-version"
I = "d-nonptcha-sync"
P = "/verify/traffic"      U = "/verify/traffic/error"
T = "/buyer/login"
+ "af-ac-enc-dat"
```

## Signing primitives (dari string table)

```
vmp_getChromeKeys              — ekstraksi public key
vmp_getPubKeyClientCapabilities
vmp_getWebdriverEvidence       — anti-bot (deteksi webdriver)
vmp_getNotiKeys
vmp_getLocalStorageKeys (unsupported/invalid key/exceeds Uint16)
vmp_getTlvEncodeErrors         * payload pakai TLV encoding!
vmp_getSupportFetchLater
cefSharp                       — signature fn (nama)
getUuidTrack / igetStorageUuid / igetSessionUuid / igetCookieUuid
createUUidV2 / randomUUID
b64UrlEncode / encodeUtf8 / decodeURI
mobileNetworkHash
__WIR_SZ_UNIQ_DC               — SZ unique device id
```

## Endpoint IVS/anti-fraud

```
api/v4/account/login_by_whatsapp
api/v4/account/signup_by_otp
api/v4/basic/signup_by_email_otp_token
api/v4/account/basic/login_ivs
api/v4/anti_fraud/ivs/token/verify
api/v4/anti_fraud/ivs/shopee-face-match/verify
```

## x-sap-ri (52 hex) — struktur

`[ts:4B][nonce:4B][seq:4B][marker 0x1201][signature:19B]` (BIG-ENDIAN). Terverifikasi 9 req.

## sz-token / riskToken — struktur

`b64(16B)|b64(64B SIGNATURE)|b64(12B nonce)|08|<platform>` — identik dgn riskToken.
Dari native bridge `callHandler("getRiskToken")` (modul 8094.js).

## af-ac-enc-sz-token — struktur

`b64(IV 16B)|b64(enc ~68B)|b64(GCM-nonce 12B)|08|<plat>`
= sz-token terenkripsi. Kunci dari handshake X25519 (`/verify/traffic`).

## Wrapper fetch

SAP membungkus `window.fetch` (bertanda `__sap_wrapped`, `__monitor_sap_fetch`),
menyuntik header via interceptor. Detail logic di VM (tidak plaintext).

## TEMBOK FINAL: VM (VMP) obfuscation

- Signer `_ = O[ad("0x393")](payload, cfg)` dijalankan VM bytecode (`ac[_++]`, `tO`, `tE`).
- 1 string table `ak` (aj, alph `ofks...`) = WebGL fingerprint collector
  (`getShaderPrecisionFormat`, VERTEX_SHADER) — BUKAN signer.
- Fungsi sensitif semua ber-prefix `vmp_`.
- Crypto signer TIDAK via WebCrypto (hook subtle tangkap 0 sign op).
- Sourcemap host `sourcemap.webfe.shopeemobile.com` → 502.

Reversing VM penuh = proyek berminggu (butuh emulasi bytecode interpreter + tiap opcode).

## Terverifikasi

- `decode_all_tables.py` → 2592 string, akurasi 100% (spot-check export/getShaderPrecisionFormat).
- `sap_signer_capture.py` → 9 req w/ x-sap-ri (timestamp cocok).
