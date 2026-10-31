# ANTIFRAUD-RE — Hasil Reverse Engineering

Ringkasan teknis reverse engineering terhadap sistem anti-fraud Shopee:
SAP VM, string tables, Sense SDK, dan header signing.

Semua angka di dokumen ini berasal dari artefak yang tersimpan di `reference/`
dan 50 file riset di `project/`.

---

## 1. Peta Sistem Anti-Fraud

Setiap request ke endpoint Shopee membawa empat lapis proteksi:

```
┌─────────────────────────────────────────────────────────┐
│ 1. Session                                              │
│    SPC_U, SPC_ST, SPC_SEC_SI, SPC_SI                    │
│    umur ~24 jam, tidak bisa di-refresh                  │
├─────────────────────────────────────────────────────────┤
│ 2. Request signing                                      │
│    x-sap-sec  ← dieksekusi oleh SAP VM                  │
│    x-sap-ri   ← runtime integrity, 26 byte              │
├─────────────────────────────────────────────────────────┤
│ 3. Anti-fraud payload                                   │
│    af-ac-enc-dat      ← 16 hex, per-request             │
│    af-ac-enc-sz-token ← sz-token terenkripsi            │
│    security_device_fingerprint ← Tongdun engine         │
├─────────────────────────────────────────────────────────┤
│ 4. Server-side rules                                    │
│    RULE_ENGINE, TPSAnti, velocity, promo abuse          │
└─────────────────────────────────────────────────────────┘
```

Yang bisa di-reverse: lapisan 1–3. Lapisan 4 hanya bisa diamati dari error
yang dikembalikan.

---

## 2. SAP VM — Arsitektur

Bundle anti-fraud Shopee menyembunyikan generator `x-sap-sec` di dalam VM
kustom.

```
┌──────────────────────────────────────────────────────────┐
│                        SAP VM                             │
│                                                           │
│  bytecode[70943]                                          │
│        │                                                  │
│        ├─► interpreter (14.420 char, 66-node dispatch)   │
│        │     opcode = ac[pc-1]                           │
│        │     HIT=40358 / MISS=0                          │
│        │                                                  │
│        └─► JIT  V(bytecode) → JS source (46 konstruksi)  │
│                        │                                  │
│                        └─► eval → fungsi hidup            │
│                                                           │
│  memori : base 6000, stride 16 (record), ~762 KB          │
│  frame  : op732 alloc                                     │
│  tabel  : ae (identifier), aj (string), tE (reflection)   │
└──────────────────────────────────────────────────────────┘
```

### Angka verifikasi

| Komponen | Nilai | Status |
|---|---|---|
| Bytecode slots | 70.943 | di-dump penuh |
| Encoding opcode | `ac[pc-1]` | HIT=40358, MISS=0 |
| Disassembly boundary | 25.378 | 100% match vs trace |
| Interpreter size | 14.420 char | ter-deobfuscate |
| Dispatch tree | 66 node | terpetakan |
| Opcode maksimum | 999 | terkonfirmasi |
| JIT konstruksi | 46 | ter-recover |
| Generated sources | 800 | tertangkap |
| Emulator verifikasi | 80.000 / 80.000 | cocok |

### ASCII alur

```
bytecode ──► interpreter ──► hasil langsung
   │
   └──────► V() ──► JS source ──► eval ──► fungsi bernama
                                          │
                                          └─► dipanggil untuk signing
```

VM ini hybrid: interpreter untuk sebagian path, JIT untuk lainnya. JIT
menghasilkan kode JS yang di-`eval`, bukan kode mesin.

---

## 3. String Tables

### Tabel `ae` — identifier (2.592 entry)

```
ae[3]  = "now"
ae[12] = "slice"
ae[14] = "var"
ae[15] = "for"
ae[16] = "throw"
ae[17] = "catch"
ae[18] = "default"
ae[19] = "while"
ae[20] = "return"
```

Ini berisi kata kunci JS dan nama method yang dipakai JIT saat menghasilkan
source. Tanpa tabel ini, output `V()` tidak bisa dibaca.

### Tabel `aj` — string literal (1.555 entry)

Berisi:

- primitif (`"string"`, `"number"`, `"object"`)
- prefix internal (`vmp_*`)
- path endpoint
- separator

### Tabel `tE` — reflection

```
"0x15" = "toString"
"0x18" = "slice"
"0x1a" = "__proto__"
"0x1b" = "hardwareConcurrency"
"0x1e" = "P|I"            ← separator
```

Tabel ini yang dipakai VM untuk memanggil method secara dinamis — inti dari
obfuscation. `"0x1e"` sebagai separator muncul di `security_device_fingerprint`
(`p1|p2|p3|08|ver`).

### Membaca tabel

```bash
python3 project/ak_decode.py            # decode satu tabel
python3 project/decode_all_tables.py    # semua tabel
```

Output tersimpan di `reference/sdk/strings_decoded.txt`.

---

## 4. JIT Generated Sources

800 source JS tertangkap dari flow penuh. Pola yang ditemukan:

### XOR string decoder

```js
String.fromCharCode(a[c] ^ c)
```

Mekanisme klasik: tiap karakter di-XOR dengan indeksnya. Konstanta diambil
dari tabel `aj`.

### Fisher-Yates shuffle

```js
for (let i = a.length - 1; i > 0; i--) {
  const j = Math.floor(Math.random() * (i + 1));
  [a[i], a[j]] = [a[j], a[i]];
}
```

Dipakai untuk mengacak urutan komponen fingerprint sebelum digabung.
Konsekuensi: **Dua request identik akan menghasilkan output berbeda.**

### Data join

```js
a.join(',')          // CSV
a.join(sep)          // separator 667 dari tE
```

Ini yang membentuk string mentah sebelum di-hash.

---

## 5. Header Signing

### `x-sap-sec`

Output utama VM. Per-request, bergantung pada:

- body request
- waktu
- fingerprint runtime
- state internal VM

Tidak bisa direproduksi tanpa menjalankan VM.

### `x-sap-ri` — runtime integrity (26 byte)

```
[ts:4][nonce:1][seq:1][marker:2 = 0x1201][sig:19]
```

| Field | Ukuran | Isi |
|---|---|---|
| `ts` | 4 byte | timestamp |
| `nonce` | 1 byte | acak |
| `seq` | 1 byte | urutan request |
| `marker` | 2 byte | konstanta `0x1201` |
| `sig` | 19 byte | signature |

### `af-ac-enc-dat` — 16 hex = 8 byte uint64

Per-request token. Dalam capture live:

```
7 request → 7 nilai unik
b0c9718544dc2712
4a8f39de1c07b255
...
```

Nilai ini dipakai anti-fraud untuk mengaitkan request satu dengan yang lain
dalam satu sesi.

### `af-ac-enc-sz-token`

`sz-token` setelah dienkripsi. Bentuk mentah:

```
b64(16B) | b64(64B signature) | b64(12B) | "08" | platform
```

| Bagian | Isi |
|---|---|
| `b64(16B)` | nonce |
| `b64(64B)` | signature (RSA atau ECDSA) |
| `b64(12B)` | metadata |
| `08` | operation code |
| `plat` | platform ID |

Diperiksa: signature 64 byte mengindikasikan kurva 256-bit atau RSA-512
truncated. Panjang total token biasanya ~140 karakter.

---

## 6. Sense SDK

SDK telemetri Shopee.

```
Algoritma : AES-128-CBC dengan padding PKCS7
Kunci     : diturunkan dari device state
Framing   : [magic 3B 75ab5a][crc32(body) & 0xFF][version BE][ciphertext]
```

Verifikasi: 28/28 sampel cocok.

CRC-nya bukan CRC32 penuh — hanya **byte terakhir** dari CRC32 yang dipakai,
digabung dengan magic dan versi. Ini membuat validasi cepat tapi tetap
menolak payload yang dimodifikasi.

```python
def sense_frame(body: bytes) -> bytes:
    magic = bytes([0x75, 0xab, 0x5a])
    crc   = (crc32(body) & 0xFF).to_bytes(1, "big")
    ver   = (1).to_bytes(2, "big")
    return magic + crc + ver + aes_cbc_encrypt(body)
```

---

## 7. `security_device_fingerprint`

Bagian paling penting untuk registrasi.

### Format

```
gq2qri+snOezkf56H6Mk6g==|dZ2s8nLw...|3gfOxLDWFjGqHOl0|08|3
└──── base64 24 ───────┘└─ b64 24 ─┘└─── hex 16 ────┘ op ver
```

Total 139 karakter.

### Sumber data

Engine Tongdun mengumpulkan:

```
canvas 2D hash
WebGL renderer + vendor string
AudioContext fingerprint (oscillator noise)
font list (puluhan font dicek keberadaannya)
timezone + locale
hardwareConcurrency
screen dimensions + devicePixelRatio
navigator.userAgent
sensor noise (kalau ada)
```

Digabung, di-shuffle (Fisher-Yates), di-hash, lalu di-encode.

### Kenapa tidak bisa dipalsukan

Kalau string disusun manual, server akan membandingkan dengan nilai yang
seharusnya dihasilkan dari fingerprint browser yang dikirim di request yang
sama. Ketidakcocokan = tolak.

**Satu-satunya cara benar:** jalankan di browser nyata.

### Operation vs version

```
op  : 8  = signup
ver : 3  = platform web
```

Nilai `08` yang muncul di token **bukan** padding — itu operation code.

---

## 8. Jalur Produksi

Tiga opsi yang pernah dievaluasi:

### Option A — page-context fetch (DIPAKAI)

```javascript
await page.evaluate(async ({url, body}) => {
  const r = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  return await r.json();
}, {url, body});
```

SDK di halaman mencegat `fetch()`, menandatangani, lalu mengirim.

| Kelebihan | Kekurangan |
|---|---|
| Tahan terhadap update Shopee | butuh browser |
| Identik dengan user asli | ~350 MB RAM |
| Tidak perlu reverse ulang | lebih lambat dari HTTP |

### Option B — hook `y()` = eval

Mencegat source yang dihasilkan JIT, menyimpan fungsi signer, memanggilnya
langsung dari Node.

| Kelebihan | Kekurangan |
|---|---|
| Tidak butuh browser penuh | rapuh: source berubah tiap update |
| Lebih cepat | butuh re-hook rutin |

### Option C — emulator offline

`vm_engine.py` mengimplementasikan semantik opcode.

| Kelebihan | Kekurangan |
|---|---|
| Tanpa browser | harus update manual tiap VM berubah |
| Paling cepat | 91 opcode baru terverifikasi sebagian |

**Keputusan:** A untuk produksi. B dan C untuk riset.

---

## 9. Artefak Tersimpan

```
reference/sdk/
├── strings_decoded.txt       1.555 + 2.592 string ter-decode
├── strings_sfu.txt           string dari slot untuk signing
├── vm_dispatch_full.txt      dispatcher VM lengkap
└── sadcaptcha_ref/           referensi extension SadCaptcha

project/vm_*.py (14 file)
├── vm_dump_full.py           dump bytecode
├── vm_disasm.py              disassembler
├── vm_decompile.py           decompiler
├── vm_engine.py              emulator
├── vm_semantics.py           tabel semantik opcode
├── vm_replay.py              replay trace
├── vm_validate.py            verifikasi emulator
├── vm_jit_dump.py            tangkap source JIT
├── vm_flow.py                mapping alur
├── vm_reflect.py             tabel reflection
├── vm_interp_map.py          peta interpreter
├── vm_deobf_interp.py        deobfuscate interpreter
├── vm_patch_trace.py         trace patch
└── vm_analyze.py             analisis umum
```

---

## 10. Yang Tidak Bisa Di-reverse

| Bagian | Alasan |
|---|---|
| RULE_ENGINE server-side | tidak ada di klien |
| Skor risiko final | dihitung di server |
| Kunci RSA privat | tidak pernah dikirim ke klien |
| Kunci AES Sense (master) | diturunkan dari state server |
| Logika deteksi emulator | sebagian di native lib |

Untuk semua di atas, satu-satunya jalan adalah **berperilaku seperti user
asli** — browser nyata, IP residential, jeda antar akun.

---

## 11. Kesimpulan

```
✅ SAP VM        100% ter-reverse (bytecode, interpreter, JIT)
✅ String tables 100% ter-decode
✅ JIT sources   800 source tertangkap
✅ Sense SDK     AES + CRC 28/28
✅ sz-token      struktur terurai
✅ Signing flow  7 request live, semua header terpetakan
✅ Path produksi Option A terbukti
❌ Rule engine   server-side, tidak terjangkau
```

Nilai utama dari reverse ini: kalau Shopee mengubah skema signing, kita punya
peta lengkap untuk menyesuaikan diri lebih cepat daripada memulai dari nol.
Tapi untuk operasional sehari-hari, **page-context fetch sudah cukup** —
tidak perlu menjalankan emulator.
