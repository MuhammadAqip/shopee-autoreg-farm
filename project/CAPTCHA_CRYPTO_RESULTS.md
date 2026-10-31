# Opsi C — Skema Enkripsi Captcha Shopee (KEY EXCHANGE + AES INLINE)

**Sumber:** `bundle.a95de02.js` module `2300` + `3098` + `1125`.
**Metode:** reverse statik (beautified).
**Tanggal:** 2026-10-14

---

## TL;DR

Captcha Shopee pakai **envelope encryption**:

1. Client generate **AES key random (16 byte)** + random string.
2. `encryptKeyValue` = **base64(AES key)** — dikirim ke server (key exchange).
3. Server pakai key itu untuk **enkripsi `generate`** (challenge).
4. Client dekripsi pakai key yang sama (AES kustom **inline**, bukan CryptoJS biasa).
5. Jawaban dienkripsi balik → POST `verify`.

**AES-nya di-INLINE** (tabel S-box + round key hardcoded di module 3098).
Bukan standard CryptoJS dari window → tidak bisa di-hook via `window.CryptoJS`.

---

## 🔑 Module 2300 — Key Exchange (baris 624-659)

```js
// generate session key
e = now_ms()                               // (v.Ln) — start timestamp
r = randomString(8, 12 chars)             // (v.nQ)((v.hw)(8,12)) — randomStrLength
i = randomBytes(16)                        // (v.nQ)(16) — AES KEY 16 byte
a = bytesToBase64(i)                       // (b.Gt)(i) — encryptKeyValue

// POST { randomString: r, encryptKeyValue: a, aesKey: i }  → server (d.F)
// server balas → i ditimpa:
i = resp.key;   o = resp.?               // key + payload
u = resp.?     (i[n(124)] = key, i[n(125)] = payload)
l = hash(o)                                // (m.h) — bodyhash (SHA)
c = now_ms() - e                           // bodyEncryTime
l = SM(l) + "||" + SM(Al(u))               // bodyhash||(hash of payload)
return { data: l, key: SM(o.subarray(0,12)) }   // key = 12 byte pertama → nonce/tag
```

**Interpretasi:** client kirim AES key ke server (base64). Server enkripsi challenge
pakai key itu. Client dekripsi. Endpoint exchange = module `3098.f` / module `3262`.

---

## 🔐 Module 3098 — AES Inline (baris 10658+)

- `l(t)` = fungsi enkripsi **AES-128 custom** dengan:
  - Round keys `i` = 11×4 matrix (hardcoded, baris 10673-10684)
  - T-tables `o` = 5×256 matrix (baris 10685-10690) — S-box di-expand
  - 10 round (`for b<10`)
  - Output = ciphertext + **4-byte length prefix** di akhir
- `d.F` (baris 10709) = fungsi exchange: `tP(o, Al(i))` → `l(o)` → `VE(Al(r), Al(a), o)`

**Kenapa AES inline:** anti-tamper. Mengganti CryptoJS dengan implementasi sendiri +
tabel hardcoded supaya tidak bisa di-hook/di-monkey-patch lewat `window.CryptoJS`.

---

## 🧰 Module 1125 — Helper Kripto (baris 10019+)

| Export | Fungsi |
|--------|--------|
| `Al` | string → Uint8Array (charCodeAt) |
| `Ln` | `Date.now()` (timestamp ms) |
| `nQ` | randomBytes(n) |
| `hw` | randomInt(min, max) |
| `tP` | concat Uint8Array |
| `VE` | concat/op bytes (cipher assemble) |
| `SM` | hash (SHA-family) |
| `SW` | bytes → string (chunked String.fromCharCode) |

---

## ✅ CARA SOLVE (langkah konkret)

### Metode utama — **panggil fungsi SDK asli dari browser** (RECOMMENDED)

Jangan reimplement AES. Ambil fungsi dari webpack runtime Shopee:

```js
// dari halaman Shopee (via Playwright page.evaluate)
// 1. cari webpack require
const rq = (() => {
  const chunks = Object.keys(window).filter(k => /^webpackChunk/.test(k));
  let req = null;
  window[chunks[0]].push([[Math.random()], {}, (r) => { req = r; }]);
  return req;
})();

// 2. module 1125 = helper, module 3098 = AES/exchange, module 2300 = keygen
const h = rq(1125);       // { Al, Ln, nQ, hw, tP, VE, SM, ... }
const f = rq(3098);       // { F }  → exchange+encrypt
const m = rq(some2300id); // { J }  → generate key pair

// 3. panggil exchange: bangun {randomString, encryptKeyValue, aesKey}
//    → hasil .F(...) berisi body (challenge terenkripsi) + key
```

**Alur penuh:**
1. `get_config` → dapat bundle + tracking_id.
2. Generate key pair (`rq(2300).J()` atau panggil `f.F`).
3. Kirim exchange → server balas challenge (AES-encrypted pakai key kita).
4. **Dekripsi dengan fungsi `l()` di module 3098** (atau inverse-nya kalau ada).
5. Baca challenge → hitung jawaban.
6. Encrypt jawaban → POST verify.

### Metode cadangan — reimplement AES

Tabel S-box `i` (round keys) + T-tables `o` ada di bundle (baris 10673-10690).
Ekstrak → port ke Python. **Rapuh** (harus cocok byte-for-byte), tapi mungkin.

### Metode ketiga — hook hasil dekripsi

Hook fungsi `l()` via webpack wrapper: bungkus module 3098 saat di-require,
log input/output → dapat plaintext challenge tanpa reimplement.

---

## 📊 Status Opsi C

| Langkah | Status |
|---------|:-:|
| Webpack chunk ter-hook | ✅ `webpackChunkshopee_pc` |
| Skema key-exchange dibongkar | ✅ (module 2300) |
| AES inline ditemukan | ✅ (module 3098) |
| Helper kripto dipetakan | ✅ (module 1125) |
| Ekstraksi key runtime | ⬜ (perlu panggil SDK live) |
| Dekripsi challenge | ⬜ (lanjut) |
| Auto-jawab | ⬜ (lanjut) |

**Inti:** kunci TIDAK statis — **key exchange per-session** + AES inline.
Cara paling praktis = **panggil fungsi SDK asli dari dalam browser** (metode utama).

---

## ✅ BUKTI: Webpack require bisa diakses dari luar (terobosan)

Probe live (Playwright `page.evaluate`):

```json
{
  "chunks": ["webpackChunkshopee_pc"],
  "req": true,
  "mods": {
    "1125": "ERR:...reading 'call'",   ← module di-require, butuh dep runtime
    ...
  }
}
```

**Arti:** kita **BERHASIL merebut `__webpack_require__`** Shopee dari luar.
Module bisa di-require; error `reading 'call'` = butuh webpack runtime
sudah init penuh (module lazy-loaded). Fix: require SETELAH bundle init,
atau bungkus pakai `Object.assign` dep.

**Konsekuensi:** metode utama (panggil fungsi SDK asli untuk dekripsi/encrypt)
**layak** — tidak perlu reimplement AES inline.

### Cara ambil module dgn benar (final):

```js
// tunggu sampai chunk ter-init (chunk[0] berisi module runtime)
const stack = []; 
const req = (() => {
  const k = Object.keys(window).find(x => /^webpackChunk/.test(x));
  let r;
  window[k].push([[1e9], {
    // inject module sebagai dep biar runtime init
  }, (__req) => { r = __req; }]);
  return r;
})();
// sekarang req bisa panggil module dgn dep tersedia
```

---

## 🎯 RENCANA SOLVE FINAL (urut prioritas)

1. **Rebut webpack require** (✅ terbukti) → `req(1125)`, `req(3098)`.
2. **Konversi helper** → bikin objek `{Al, nQ, tP, VE, SM, Ln}` dari module 1125.
3. **Generate key pair** → pakai `hw(8,12)`, `nQ(16)`, base64.
4. **Exchange** → panggil fungsi exchange (module 3098 `.F` / 2300 `.J`).
5. **Dekripsi challenge** → pakai fungsi AES inline (module 3098) — input `encrypted_data` dari `generate`.
6. **Susun jawaban** menyesuaikan challenge (klik koordinat / geser offset) + behavioral (timestamp, move_type).
7. **Encrypt jawaban** → POST `verify`.

Semua langkah bisa **di-eksekusi di dalam browser** (Playwright `add_init_script`
+ `evaluate`) tanpa reimplementasi kripto.

---

## 🧪 BUKTI E — Eksekusi lanjut (hasil & temuan keras)

### 1. Webpack require global terbukti bisa direbut
```
chunks: ["webpackChunkshopee_pc"]   req: true   hasM: true   modCount: 563
```

### 2. Chunk tumbuh saat captcha aktif
```
BEFORE captcha: count_all = 563
AFTER  captcha: count_all = 741     ← +178 modul lazy-load
```

### 3. TAPI id bundle (1125/3098/2300) TIDAK ADA di runtime webpack
Scan 741 module runtime → `crypto_hits: []` (nol). Artinya:
- **id di `bundle.pretty.js` ≠ id runtime webpack.** Id bundle.pretty = id
  internal bundle captcha (jenkins build), bukan module id `webpackChunkshopee_pc`.
- **SDK captcha = bundle webpack TERPISAH**, runtime-nya sendiri, di-load
  sebagai script mandiri (`bundle.a95de02.js`) — IIFE tertutup.

### 4. SDK tidak ekspos global
```
interesting: []   hasCaptchaGlobal: false   win_globals_sample: []
```
Tidak ada `window.CaptchaSDK`, tidak ada objek global crypto yang bisa di-hook.

---

## 🧱 KESIMPULAN KERAS (jujur)

| Yang bisa | Yang tidak bisa |
|-----------|-----------------|
| Rebut `webpackChunkshopee_pc` (app) | Require module crypto captcha dari situ |
| Rekam semua request/response captcha | Ambil `AES key` / fungsi `l()` dari global |
| Lihat struktur payload + endpoint | Panggil fungsi enkripsi SDK langsung |

**Fungsi crypto (keygen + AES inline) terkunci di dalam IIFE SDK captcha** —
tidak ada export, tidak ada global, tidak ada hook point.

---

## ✅ JALUR PRAKTIS YANG BENAR-BENAR JALAN

Kalau fungsi internal tak bisa dipanggil, **jangan panggil — biarkan SDK sendiri yang kerja**:

1. **Kendalikan browser** (Playwright) sampai captcha tampil.
2. **Biarkan SDK captcha** generate key, exchange, dekripsi challenge
   (semua otomatis di dalam bundle).
3. **Isi jawaban via UI/DOM** — simulasi interaksi pada elemen captcha:
   - klik → dispatch `mousedown/mousemove/mouseup` di koordinat objek
   - geser → `mousedown` di slider, gerak bertahap, `mouseup`
4. **SDK yang menyusun payload jawaban + encrypt + POST `verify`** — otomatis.
5. Loop sampai `send_otp` terpicu → OTP → verify akun.

**Intinya:** jawab captcha seperti **manusia** (input event nyata), bukan
memanggil kripto. SDK menangani sisanya. `tools/captcha_hook.py` sudah
merekam flow untuk memverifikasi tiap langkah.

### Kalau mau otomatis penuh (solver):
- Pakai **vision model** (OCR/deteksi) pada challenge gambar → tentukan koordinat.
- Kirim event mouse bertahap (dengan timing + jitter → lolos cek behavioral).
- Bukan lewat kripto — lewat **interaksi UI**.

---

## 📊 Status akhir E

| Item | Status |
|------|:-:|
| require app-chunk | ✅ |
| Skema crypto dipahami (bundle) | ✅ |
| Module crypto di-require dari runtime | ❌ (IIFE terpisah) |
| Global hook point | ❌ (tidak ada) |
| Jalur praktis (UI-driven) | ✅ direkomendasikan |
