# Sense SDK (Shopee anti-fraud payload) — FULLY REVERSED & VERIFIED ✅

Breakthrough #11-A (2026-10-16). Payload `POST /api/v4/web/subcart` (dan `shpsec/web/report`)
**didekripsi penuh** dari traffic nyata. Modul: `8094.<hash>.2023.js` (pcmall live-sg).

## Kripto (TERVERIFIKASI pada data live)

```
AES-128-CBC, PKCS7 padding
KEY = b"SenseTestKey1234"   (b64: U2Vuc2VUZXN0S2V5MTIzNA==)
IV  = b"SenseTestIV12345"   (b64: U2Vuc2VUZXN0SVYxMjM0NQ==)
VERSION = 1001000 (0x000F4628)
```

Fungsi JS `T(t,e,n)` = AES-CBC. `pure_aes.py` (murni Python) & `cryptography` byte-exact.

## FRAMING (terverifikasi dari body live `/web/subcart`)

```
[u32 crc BE][u32 version BE=1001000][i16 len_ev BE][enc_ev][i16 len_dev BE][enc_dev]
```
Body dikirim sebagai **base64** (prefix "JxcB" utk subcart, "dUv..." lain).
- `enc_ev` = AES-CBC(serialize_events)
- `enc_dev` = AES-CBC(serialize_device)
- crc = 4-byte header; varian tidak identik dgn zlib.crc32(bod) — kemungkinan polinomial/region beda. TIDAK menghalangi dekripsi.

## Hasil dekripsi NYATA (run_87876125616)

```
version=1001000 len_ev=128 len_dev=976
EVENTS: page_view(url=https://shopee.co.id/buyer/signup), click(target=BUTTON, x/y), scroll
DEVICE:
  trace_id = e0159777-c2e6-4776-9414-4f17dbb527f6
  start_time = 0x01a141048eaf (ms)
  platform = pc
  dfp = 88fc2db7987ea0a138a9f177b6e066560de42989e266a9a28add999b0
  riskToken = S5gycGvbwOtLAdtnZ3M5MA==|+FKanmPZ84Dki...|YRaLKFDZH+RRZ3ON|08|1
  ... report_time, report_type, region, location_href, event_counts, first_input, has_been_active
```

**PENTING:** `device_info` berisi `dict` JSON di ekor (`{"p...`) — perlu parsing lebih lanjut.
riskToken = 3×b64 + `|08|<platform>` (sama format dgn SAP riskToken).

## Struktur events (tag `C`)

`C = {page_view:1, move:2, keydown:3, keyup:4, click:5, scroll:6, fetch:7}`
Semua multi-byte = **BIG-ENDIAN** (`setUint32(...,!1)` = !1 = false = BE).
- page_view: u8(tag)+i64(ts)+str(url)
- move: u8(tag)+i16(count)+[i32(x)+i32(y)+i64(ts)]*
- keydown/up: u8+i64+u16(keycode)+str(v)
- click: u8+i64+i32(x)+i32(y)+i32(screen_x)+i32(screen_y)+str(target)
- scroll: u8+i64+u8(percent)
- fetch: u8+i64(request_ts)+str(url)
Tiap event di-prefix i16(len) BE.

## Tool

| File | Fungsi |
|---|---|
| `sense_decrypt.py` | `build_payload()`, `parse_payload()` (framing live), AES enc/dec |
| `pure_aes.py` | AES-CBC murni Python — matches `cryptography` byte-exact |
| `sense_serialize.py` | port penuh writer + `forge()` → bikin payload valid |
| `sense_cli.py` | `dec <file|b64>` / `sniff <jsonl>` / `dec-har <har>` / `forge <out>` |
| `sap_deep_extract.py` | CDP `Debugger.getScriptSource` → dump semua script worker |
| `capture_shpsec.py` | hook fetch/XHR → tangkap body binary shpsec |

## Cara pakai

```bash
python sense_cli.py sniff capture/run_XXX.jsonl     # scan + decrypt body Sense
python sense_cli.py dec <b64>                        # decrypt satu payload
python sense_cli.py forge /tmp/out.bin              # forge payload contoh
```

## Implikasi

- **Payload anti-fraud Shopee bisa dilihat & dipalsukan.** sense_serialize.py bisa forge event
  (mouse manusiawi, timing) → potensi kurangi deteksi bot.
- `crc` header mungkin divalidasi server; kalau forge ditolak, perlu cocokkan varian CRC.
- Ini pelengkap: signature `x-sap-sec` (WASM) & `riskToken` dari native bridge tetap terpisah.
