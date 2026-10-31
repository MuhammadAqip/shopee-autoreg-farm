---
name: shopee-token-war-stack
description: Use when driving Shopee digital-product orders.
---

# Shopee Token War Stack — v2 Engine

Warehouse of the `shopee_war_stack` project (`/root/shopee-war`): Playwright-driven
Shopee digital-product orders (PLN prepaid token flash-sale war, pulsa, paket data,
e-money, game, tickets). The whole trick is **fetch from inside the browser page** —
`page.evaluate` with `credentials:'include'` — so the real Shopee WAF/mTLS/fingerprint
stack signs every request exactly as a human session would.

## Architecture (v2.py, ~1200 lines)

| Piece | Role |
|---|---|
| `BrowserAPI` | sync_playwright chromium headless; loads `.shopee.co.id`, injects `sz_fingerprint` into localStorage; `fetch()` runs JS `fetch()` inside page context |
| `ShopeeAPI` | static methods: `get_account_info`, `check_account_exist`, `get_pln_token_list`, `get_bill_info`, `create_order`, `pay_order`, `get_payment_instruction`, `get_order_list` |
| `execute_checkout_worker` | regular war: one account, denom main + backup, retry loop |
| `execute_special_war_worker` | promo war: one account cloned across N proxy threads sharing one fingerprint |
| `v2_bulk.py` | cookie checker — plain HTTP fast path (~50-200ms/cookie, 40 threads) |

## The WAF-bypass principle (why it works)

`BrowserAPI.fetch()` never uses `requests`. It builds a JS snippet and runs it with
`self.page.evaluate(js_code)`. The request therefore carries the browser's own TLS
fingerprint, HTTP/2 settings, cookies, and — critically — the anti-fraud headers that
Shopee's `af-ac-enc-*` / `sz-token` SDK injects via its service worker / XHR hook.
A plain `requests` call to the same endpoint returns 403. Read
`shopee-antifraud-reversing` for the signer internals.

Required headers on every in-page fetch (browser adds the rest):
```js
headers: {'Content-Type':'application/json','Accept':'application/json','x-api-source':'pc','x-csrftoken': csrf}
```
`csrf` is parsed from `document.cookie` (`csrftoken=...`) at call time — hardcoding an
old value gives 403.

## Cookie format

A Shopee session cookie string. Auth = these keys present with real values:
```
csrftoken, SPC_CLIENTID, SPC_U (user id), SPC_ST (session token),
SPC_SI, SPC_SEC_SI, SPC_F (fingerprint x_y_unknown), SPC_T_ID, SPC_T_IV
```
`SPC_U` + `SPC_ST` + `SPC_CLIENTID` missing ⇒ account never logged in (error=19 on
get_account_info) — cookie is tracking residue, NOT a session. No repair possible.

## Endpoints (all relative to `https://shopee.co.id`)

**Auth / account**
- `POST /api/v4/account/basic/check_account_exist` body `{"phone":"62...","scenario":3}` → oracle: is this number registered
- `GET  /api/v4/account/basic/get_account_info` → `{error:0, data:{username,userid}}` — the canonical cookie-validity probe

**PLN prepaid (category_id 20103, carrier_id 20)**
- `GET /digital-product/api/item/pln-prepaid/inquiry?customer_id=<ID>&carrier_id=20`
- `GET /digital-product/api/item/v2/list?category_id=20103&carrier_id=20&need_pcp_info=false` → items with `activity_item_priority_promotion_info.flash_sale_info{price,stock,promotion_activity_id}` and `.priority_promotion_info` — this is the flash-sale oracle
- `GET /digital-product/api/item/v2/bill_info?customer_id=<ID>&category_id=20103&carrier_id=20&item_id=<ID>` → `provider_additional_fee.admin_fee`, `bill_amount`, `provider_id`

**Order lifecycle**
- `POST /digital-product/api/order/create` — PLN/2-step flow
- `POST /digital-product/api/order/pay`
- `POST /digital-product/api/order/merge_pay` — pulsa 1-step (create+pay)
- `POST /digital-product/api/order/cancel` body `{"order_id":"<ID>","category_id":<CAT>}` — clean cancel while status OR1
- `GET  /digital-product/api/order/v2/list?page=1&categories=&order_status=<N>&page_size=40&last_create_time=0` → orders. **N = 11 (unpaid/OR1) | 44 (selesai/OR4) | 55 (SEMUA)**. BUKAN 1/3/22 — int itu balikin total 0 walau ada order!
- **⚠️ FILTER 44 TIDAK LENGKAP (verified live 2026-10-28, akun mdfha_df2j):** `order_status=44` cuma match OR4. Akun dgn order paid berstatus **OR5/OR6** (`order_showstatus` 22/33) → filter 44 balik **n=0** padahal ada 2 order paid. **ATURAN: tarik `order_status=55` (SEMUA) lalu saring `payment_status != "P0"`.** JANGAN andelin kode 44 buat "paid".
- **`payment_status` paid = P2 JUGA, bukan cuma P5.** Live: `P0`=unpaid, `P2`=lunas/dibayar, `P5`=lunas/selesai. Filter paid yang benar: `payment_status in ("P2","P5")` atau `order_status not in ("OR1",)`.
- **`order_status` range: OR1 (unpaid) .. OR5/OR6 (bayar/proses).** Bukan cuma OR1-OR4.
- Field: `order_status` ("OR1".."OR6"), `order_showstatus` ("11"/"22"/"33"/"44"), `payment_status` ("P0" unpaid / "P2" paid / "P5" lunas-selesai), `customer_id`, `customer_name`, `phone_number`, `game_account`, `epin_pin`, `epin_serial`, `provider_serial`, `topup_serial_number`, `items[].denomination`, `total_amount`, `final_price`, `payment_deadline`, `create_time`, `cancel_time`.
- `GET  /digital-product/api/order/v2/detail?order_id=<OID>` → `{err_code, data:{order:{...}}}` — **unwrap `.data.order`** (bukan `.data.data`). Berisi `customer_name` (masked DED****), `admin_fee`, `cancel_time` (non-zero = DIBATALKAN). err 1175 = bukan punya akun.
- **VA pesanan unpaid**: TIDAK ada di list/detail kalau order dibuat dgn channel_id 0 (tanpa sesi bayar). VA cuma muncul setelah `create_payment`→`init_payment`, yang butuh signed flow (raw fetch → 90309999). Jangan janji VA dari order pending lama.

**Payment / VA**
- `POST https://gw1.wsa.spm.shopee.co.id/api/payment/transaction/init_payment` body `{"encrypted_transaction_id":"<TRREF>","app_type":1,"status":3}` → `transify_data.virtual_account` + `components[component_type==7].account_number`

**Catalog discovery**
- `GET /digital-product/api/entrance/groups?source_system=3` → full category tree with `services[].url` and `category_ids`
- `GET /digital-product/api/item/v2/list?category_id=<CID>&carrier_id=<CARRID>` → per-category catalog

## Category map (verified live)

| category_id | product |
|---|---|
| 10101 | Paket data |
| 10102 | Pulsa |
| 10103 | Roaming |
| 20101 | BPJS |
| 20102 | PDAM |
| 20103 | PLN non-taglis (token) |
| 20104 | Telepon rumah |
| 20105 | Fiber |
| 20201+ | E-money |
| 30101/30201 | Game vouchers / top-up |
| 40101-40106 | Tiket (train/flight/hotel) |
| 50101-50107 | Donasi |

## X-Sign algorithm (REVERSED from DEX + VERIFIED LIVE 2026-10-21)

App request header `X-Sign` = **MD5 lowercase hex** of `url-without-scheme + STATIC_SECRET`:

```python
import hashlib
X_SIGN_SECRET = "KOSNJQFIUXR6Z9A6"
def x_sign(url: str) -> str:
    body = url[url.index(":") + 3:]          # strip "https://" / "http://"
    return hashlib.md5((body + X_SIGN_SECRET).encode()).hexdigest()
```

Recovered from `classes3.dex` → `com/shopee/httpdns/utils/j.java`:
```java
static String a(String str, String str2, String str3) {
    str = str.substring(str.indexOf(":") + 3);   // strip scheme
    if (!TextUtils.isEmpty(str2)) str = concat(str, str2);   // + secret
    if (!TextUtils.isEmpty(str3)) str = concat(str, str3);
    return f.b(str.getBytes("UTF-8"));           // MD5 -> lowercase hex
}
// caller in com/shopee/app/network/cronet/quic/rules/f.java:
//   url.addHeader("X-Sign", j.a(str, "KOSNJQFIUXR6Z9A6", null));
```
`f.b` = `MessageDigest.getInstance("MD5")` then lowercase hex table `0123456789abcdef`.
VERIFIED: app sent `664f6fb73294d3df01253633ec17f646` for
`remote-config.gslb.sgw.shopeemobile.com/apis/remote-config/v1/shopee/getRemoteConfig?keys=dns_httpdns&...`
and computed md5 matched exactly.
Other app headers: `X-Device-Fingerprint` (from `U4.l0()`, e.g. `6e73668bab783c95_unknown`),
`X-User-Token` (= userId or `NO_IMAGE` when guest), `X-User-Agent` (json: app_version/os_version/device_type).
Secret `KOSNJQFIUXR6Z9A6` doubles as the HttpDNS init secret (`httpdns/h.java`).

## Anti-fraud keys (from 30+ trials)

| Symptom | Cause | Fix |
|---|---|---|
| `4108` ORDER_PAY_TPS_RULE_ENGINE_512 / ORDER_CREATE_TPSAnti_512 | fingerprint mismatch / spam | Send `device_fingerprint:""` and `security_device_fingerprint:""` **EMPTY** for create/pay digital. The real headless browser fingerprint gets REJECTED; empty passes. |
| `2096` place order too fast | burst | ≥10s between attempts; 1 clean attempt per account |
| `2112` exist_order_id | pending order on same item+number | clear/cancel first, or another account |
| `2302` failed to change order status | cancel on non-OR1 order | let it expire (24h) |
| `5106` maintenance | biller | retry 5s |
| `1515` check-mobile | fake number pattern | use real `62` numbers, never `081234567890` |

Note the engine injects `sz_fingerprint` from localStorage as `device_fingerprint`
(`INJECT_FINGERPRINT` placeholder), while the standalone `digital_api.py` sends empty.
Both can pass; empty is the more reliable default for fresh accounts.

## Fees (micro: 100000 = Rp1)

- Bank VA option `89052001`..`89052006` → Rp1.000 (100000000)
- Indomaret ch 8003001/8003200 → Rp2.500 (250000000)
- SeaBank `89052007` → 0
## 🏆 RESEP VA FINAL — SEABANK 781 (VERIFIED 2026-10-30, live 2×)

VA **HANYA** dari pulsa (`10102`). PLN (`20103`) = bill-flow, `encrypt_payment_id` selalu kosong → `init_payment` ec=7. Jangan buang waktu.

**Script siap pakai:** `/root/va_getter_final.py` (`--cookie-file ck.txt --phone 08xx --bank seabank --denom 2000`).

**Resep persis yang jalan (SeaBank):**
```
warm: goto /produk-digital/pulsa, tunggu __sap_hook_fetch === true (~9s)
1. GET  /digital-product/api/item/v2/list?category_id=10102&carrier_id=26   → cari denomination==2000
2. GET  /digital-product/api/item/check-mobile?item_id=<id>&category_id=10102&carrier_id=26&phone_number=<08xx>
3. POST /digital-product/api/order/merge_pay  ← body di bawah
4. POST https://gw1.wsa.spm.shopee.co.id/api/payment/transaction/init_payment {encrypted_transaction_id:<tid>,app_type:1,status:3}
   → transify_data.virtual_account  /  components[component_type==7].account_number
```

**merge_pay body (SeaBank — fee 0, TANPA `is_new_fee`):**
```json
{"items":[{"id":157481,"item_name":"Telkomsel 2.000","quantity":1,"market_price":330000000,
  "discount_price":330000000,"carrier_id":26,"category_id":10102,"promotion_activity_id":0,
  "snapshot_id":<live>,"original_discount_price":330000000,"promotion_quantity":1}],
 "phone_number":"08xxxx","language":"id-ID",
 "device_fingerprint":"","security_device_fingerprint":"",
 "channel_id":8005200,"channel_name":"Transfer Bank",
 "channel_item_option_info":"{\"option_info\":\"89052007\"}",
 "call_back_url":"https://shopee.co.id/produk-digital/m/checkout-result/channel/8005200/order/__ORDER_ID__?fromSource=checkoutH5&categoryId=10102&orderIdType=payment",
 "total_amount":330000000,"final_price":330000000,"payment_handling_fee":0,
 "h5_version":"id/live@release-2026.10.v2","order_extend_info":{"bit1":false,"bit2":false},
 "is_service_fee_flow":true,"category_id":10102,"carrier_id":26,"system_version":"Windows-10"}
```
→ `{err_code:0,data:{order_id_list:[...],pay_order_id:"379...",payment_url:"...transaction/<tid>?..."}}`
→ init_payment(tid) → `virtual_account:"781 085198576223"`, `amount:"Rp3.300"`, `bank_name:"SeaBank"`

**Kunci anti-2080:** SeaBank **waJIB fee 0 + TANPA `is_new_fee`**. `is_new_fee:true` + fee 1k → `2080 ORDER_PAY_PROMO_511`.
**2112 `exist_order_id`:** ada order menggantung di item+nomor yg sama. `exist_order_id` ada di **`err_msg` sbg STRING JSON**, bukan `data`. Parse: `json.loads(err_msg)["exist_order_id"]` → `POST /order/cancel {order_id,category_id:10102}` → ulang merge_pay. **VA tetap sama** (VA di-bind ke nomor HP, bukan order).
## 🏦 TABEL BANK VA — 8/8 VERIFIED LIVE (2026-10-30, jalur bot `BrowserAPI` headless)

Semua via `channel_id: 8005200` / "Transfer Bank", `category_id: 10102` (pulsa), `device_fingerprint` & `security_device_fingerprint` = `""`, `h5_version: id/live@release-2026.10.v2`.

| bank | `option_info` | fee | `is_new_fee` | min denom | VA prefix | VA sample |
|---|---|---|---|---|---|---|
| SeaBank | `89052007` | **0** | **ABSEN** | 2.000 | `781` | `78118047666118904` |
| BCA | `89052001` | 1.000 | ya | **10.000** | `126` | `126 085198576223` |
| Mandiri | `89052002` | 1.000 | ya | 2.000 | `896` | `896 085198576223` |
| BNI | `89052003` | 1.000 | ya | 2.000 | `8806` | `8806 085198576223` |
| BRI | `89052004` | 1.000 | ya | 2.000 | `128` | `128 085198576223` |
| BSI | `89052005` | 1.000 | ya | 2.000 | `600` | `600 085198576223` |
| Permata | `89052006` | 1.000 | ya | 2.000 | `704` | `704 085198576223` |
| Bank lain | `89052902` | 1.000 | ya | 2.000 | `788` | `788 085198576223` |

**Tiga jebakan yang sudah dipetakan:**
1. **SeaBank + `is_new_fee:true` (atau fee 1.000) -> `2080 ORDER_PAY_PROMO_511`.** SeaBank satu-satunya yang fee 0 DAN tanpa flag.
2. **BCA nominal < Rp10.000 -> `error_code: 16` di `init_payment`** ("Minimum payment amount of Rp10.000,00 is required"), bukan di merge_pay. `merge_pay` sukses, tapi VA kosong. Naikkan denom ke >=10.000.
3. **Promo `38028` meracuni SEMUA item denom 10.000** jadi `price: 100000` (Rp1). Kalau dipakai, `merge_pay` -> `9012 promotion detail not matched` / `2080`. Deteksi: `promo_price < 5% * denom * 100000` -> buang `activity_item_priority_promotion_info` dari item, set `promotion_activity_id: 0`, pakai `discount_price` normal.

Implementasi produksi: `/root/shopee-war/digital_api.py` (`BANK_OPTS`, `H5_VERSION`, `fee_for`, `needs_new_fee`, `order_pulsa`, `get_va`, `va_error`). `get_va` return **dict** `{va, amount, receiver, bank, transaction_ref}`, bukan string.

## Flash-sale war

Target item ids: 100206 (20k token, target Rp1), 100208 (50k, Rp30k), 100203 (100k, Rp80k).
`execute_special_war_worker`: same account, one fingerprint cloned to N proxy threads,
poll `get_pln_token_list` until `final_promo_price == target_price` and `stock > 0`, then create+pay.
Wait room uses wall-clock; on NAT'd VPS use a time-signal source instead.

## Voucher check multi-tab (async) + Tor
- Playwright SYNC API TIDAK thread-safe: paralel via thread → EPIPE crash + response `error`. Serial works, thread-parallel fails.
- Multi-tab sejati = `playwright.async_api` + `asyncio.gather` (1 event loop, N page). Bukan thread.
- 1 browser, N context (isolasi cookie jar per context), ganti cookie per akun, reload, evaluate.
- Shopee voucher endpoint butuh signed header — bypass dengan fetch DI DALAM page (SAP SDK auto-sign), bukan pure HTTP.
- Tor routing: SOCKS5 eksplisit `proxy={"server":"socks5://127.0.0.1:9050"}` LEBIH STABIL dari system-wide iptables (transparent proxy rapuh untuk headless browser streaming).
- Tor lambat + 1 circuit → request paralel bisa socket-reset. Selalu retry err=error 2x dengan jeda.
- tab=8 = titik manis (30 akun ~35s via Tor).

## Voucher check — bottleneck sejati
- Endpoint voucher (`get_user_voucher_list`) WAJIB browser: di-sign x-sap-sec oleh SAP SDK di NETWORK LAYER (service worker/native hook), gak kebaca JS. Replay header identik dari luar → 403 error=90309999 (baik direct maupun Tor). Jangan buang waktu coba pure-HTTP.
- Parallelism via Tor TIDAK menambah throughput: 1×8 = 25 worker sama-sama ~1 akun/detik. Naikin worker malah lebih lambat (Tor + RAM jenuh).
- Bottleneck = Shopee rate-limit per akun/IP, bukan CPU/browser/Tor.
- Multi-SOCKS Tor (`SocksPort 9060 IsolateSOCKSAuth` dst) kasih exit IP beda per port — pakai kalau ada proxy pool nyata, bukan buat skala via Tor saja.
- Konfigurasi optimal via Tor: 1 browser × 8 tab (~1 akun/detik = 3600/jam).
- Output WAJIB semua akun (N in → N out), tiap akun dijelasin vouchernya, bukan cuma yang punya target.

## PAID vs UNPAID — DUA FLOW BEDA (koreksi Maker 2026-10-28)
- **PAID order = READ-ONLY. TIDAK ADA VA.** Ambil `order/v2/detail` → baca hasil. Selesai. Jangan panggil `gen_va_for_order` untuk order paid.
- **UNPAID order = flow VA.** `gen_va_for_order()` (merge_pay / init_payment) → `transify_data.virtual_account`. VA HANYA muncul di sini.
- Di bot: `cp_mode:paid` → token/hasil; `cp_mode:unpaid` → VA. Jangan silang. Kalau paid di-generate VA = salah total (order udah lunas, gak ada sesi bayar).

## 🔑 HASIL PAID — DUA BLOK BEDA DI ENDPOINT DETAIL (bug "cuma 1 kedeteksi")
Rantai bug nyata (2026-10-28, order Indomaret qty 3 → bot nampil 1): parser cuma baca endpoint **LIST** (`order/v2/list`) yg `epin_serial`-nya KOSONG utk voucher, dan **gak pernah nyentuh `data.deal_voucher`** di DETAIL. 1 order qty N = 1 baris render → N kode ke-buang.

**Isi hasil beda per jenis — ambil dari endpoint DETAIL `order/v2/detail`:**
| Jenis | Blok di DETAIL | Field |
|---|---|---|
| Pulsa/PLN/Game | `data.order` | `epin_pin` (token PLN 20 digit), `epin_serial`, `provider_serial`, `topup_serial_number` — 1 order = 1 serial |
| **Voucher retail (Indomaret/Alfamart/Deals)** | `data.deal_voucher.codes[]` | `serial`, `url` (redeem link e.uvcr.me), `unique_id`, `fe_status` (unused/used), `start_date`, `end_date`, `voucher_unique_id`, `booking_id`, `merchant_ids` — **1 order = N kode (N = qty)** |

**ATURAN PARSER:** untuk order retail (`category_id` 70101-70104/30105) ATAU `quantity>1` ATAU list tanpa `epin_serial` → WAJIB tarik DETAIL lalu iterasi `data.deal_voucher.codes[]` (loop SEMUA, bukan `codes[0]`). Render tiap kode bernomor `i/N` + serial + URL.
**Voucher retail = 1 order qty N → N kode dalam SATU `order_id`.** Jangan harap N order terpisah; kalau cuma tampil 1, itu bug parser (codes[0] doang / gak baca deal_voucher), BUKAN koins/partial.
**Artefak OPSEC di detail:** `data.order.raw_extend_info` (JSON string) berisi `real_ip` (IP buyer asli), `sz_device_fingerprint`, `payment_result` — tersimpan permanen per order.
**`data.deal_voucher` TIDAK ADA di order pulsa/PLN** — cuma di order voucher retail.

### Render PAID lengkap (shipped 2026-10-28) — `shopee_bot.py _block()`
Tampilkan SEMUA, bukan cuma serial:
- `👤 username` → `• item (denom) ×qty` → `• No` → `• Total` → `• Order` (order_id) → `• Status`
- `• Channel` (channel_name dari detail) · `• Dibuat` + `• Dibayar` (create_time/payment_time, format `%d/%m/%y %H:%M`)
- `🎟️ Token/Hasil` (epin_pin PLN) · `🎟️ Serial` (epin_serial + provider_serial + topup_serial_number, dedup)
- Voucher retail: `🎫 VOUCHER (N kode)` → per kode `i/N <code>serial</code> · status` + `🔗 <a href=url>Klik redeem</a>` (clickable) + `<code>url</code>` (copyable) + `🆔 voucher_unique_id` + `⏳ s/d tanggal`
- `send(..., disable_web_page_preview=True)` biar link gak bikin preview gede.
- **`send()` di shopee_bot.py sekarang nerima kwarg `disable_web_page_preview`** (signature: `send(chat_id, text, markup=None, disable_web_page_preview=False)`). Bot global `parse_mode="HTML"` → tag `<a href>`, `<code>`, `<b>` valid.
- Parser: `check_account` SELALU tarik `order/v2/detail` utk tiap order PAID (`attach_deal_vouchers`) → dapet voucher codes + provider/topup serial + channel + payment_time.

## ⚡ CEK PESANAN CEPAT — FAST DIRECT BROWSER (2026-10-28)
Bug: `run_cek_pesanan` dulu spawn `BrowserAPI(cookies_str=ck)` **PER AKUN** + lewat **proxy** → lemot (10-60s/akun) + sering "browser gagal init (proxy/koneksi)".

**FIX — modul baru `order_fast.py` + `fast_check.py`:**
- `order_fast.FastBrowser` = **playwright ASYNC di event-loop THREAD terpisah** (persis model `browser_warmer.BrowserPool`). Bot (sync) manggil `fast.submit(coro)` → `run_coroutine_threadsafe`. **WAJIB async-loop** — kalau pakai `sync_playwright()` yg dibuat di satu thread lalu dipakai dari thread lain → `"Cannot switch to a different thread"` / `"Playwright connection closed"`. Ini bug nyata yg kejadian di bot (`run_cek_pesanan` jalan di worker thread).
- **1 context bersama → WAJIB LOCK (`_ACCT_LOCK`) per akun.** `clear_cookies`+`add_cookies` paralel bikin cookie KETIBAN (thread A dapet hasil akun B). Terbukti: 4 thread paralel → 2 hasil dobel sebelum di-lock. Serial aman (0.4-1.5s/akun).
- `fast_check.check_account_fast(cookie, mode)` = submit coroutine `_run()`: set_cookie → get_account_info → list 55/44/11 → `oc.parse_item` (pure, sync, boleh) → utk PAID tarik DETAIL via `fast._ev` inline → `_vouchers_from_detail` (JANGAN `oc.attach_deal_vouchers` — itu butuh sync page).
- `get_fast()` singleton, warm di `_boot_warm` saat bot start (§ 2.5-2.8s).
- **Waktu: ~0.4-1.5s/akun (warm).** Sebelumnya 10-60s + "browser gagal init" (spawn per akun + proxy).
- JANGAN lewat `_pick_proxy()` — fast path `new_context` tanpa proxy eksplisit.
- **PELAJARAN: JANGAN push fitur ke bot tanpa E2E test lewat fungsi aslinya dari WORKER THREAD.** Test helper standalone (main thread) LOLOS tapi bot worker-thread GAGAL. Cara test: `sb.send=cap_fn; threading.Thread(target=sb.run_cek_pesanan,args=(cid,ck,mode)).start()` lalu inspeksi `sb.CEK_LAST[cid]` + captured output.

## ⚠️ PAID = TANPA VA (di SEMUA titik)
- Teks progress `⏳ Cek pesanan (mode) — VA bank X` HANYA utk mode unpaid/all. Mode paid: `(mode in ("unpaid","all"))` guard.
- Mode paid TIDAK lewat bank picker (`cp_mode:paid` → langsung `cekpesanan_input`, gak singgah `cekpesanan_bank`).
- Render paid **RINGKAS** (koreksi Maker): cuma `👤 akun` → `• item ×qty — harga` → (`🎟️ Token`/`Serial`) → `🔗 kode + URL` per voucher. JANGAN tampil: No, Order id, Status, Channel, Dibuat/Dibayar, 🆔 uid, ⏳ s/d. (yang itu buat EXPORT TXT, bukan chat).
- `send(..., disable_web_page_preview=True)` supaya URL voucher gak bikin preview gede.

## SERVICE — DUA UNIT BEDA (jangan ketuker!)
- **`shopee-war.service`** = BOT WAR (this stack). `ExecStart=/root/sniffenv/bin/python3 /root/shopee-war/shopee_bot.py`, cwd `/root/shopee-war`, log `/root/shopee-war/shopee_bot.log`.
- **`shopee-bot.service`** = BOT FARM (BEDA, `@tokn_aiBot`). `ExecStart=/usr/bin/python3 /root/shopee_bot.py`, log `/root/shopee_bot.log`. JANGAN restart ini buat war.
- Setelah edit `shopee_bot.py` (war) → `systemctl restart shopee-war` (BUKAN `shopee-bot`). Salah unit = edit gak ke-load + MainPID gak cocok.
- **JANGAN `pkill -f shopee_bot.py` / pattern-kill dari dalam shell Hermes** — pattern-nya nge-match shell wrapper sendiri → bunuh diri (SIGKILL/SIGTERM). Pakai `systemctl restart shopee-war` atau kill PID eksplisit dari `ps -eo pid,cmd | grep shopee-war/shopee_bot`.
- Cek sehat: `systemctl is-active shopee-war` + `ps -eo pid,ppid,cmd | grep shopee-war/shopee_bot` (harus 1). MainPID di `systemctl show shopee-war -p MainPID`.

## Cek Pesanan — input & export (shipped 2026-10-28)
- **Input cookie** (dua-duanya jalan): paste cookie langsung di chat (1 baris = 1 cookie) ATAU upload file `.txt` (1 baris = 1 cookie). Handler text (`flow=="cekpesan_input"`) + document handler. Validasi `"SPC_" in text or "csrftoken=" in text`.
- **Export TXT**: tombol `📤 Export TXT (kode+link)` (`callback_data="cekexp"`) muncul tiap selesai cek, atau `📤 Export ulang`. Fungsi `do_export_cek(chat_id)` baca `CEK_LAST[chat_id]{"mode","rows"}` → bikin TXT lengkap (item, nomor, total, order, status, channel, dibuat, dibayar, token, serial, VA, voucher + link + uid + s/d) → `bot.send_document` (`visible_file_name=cek_pesanan_<mode>_<ts>.txt`).
- `CEK_LAST` = module global dict, di-set tiap run render (`CEK_LAST[chat_id] = {"mode":..., "rows":...}`).

## UI bot — checklist & output (koreksi Maker)
- **Cek Pesanan PAID = SUBMENU**: klik `cp_mode:paid` → muncul 2 tombol `cp_paid:full` (📋 Full Check) / `cp_paid:deals` (🎫 Deals aja). `cp_paid:<kind>` → `set_state(flow=cekpesan_input, cek_mode="paid", cek_kind=kind)`.
- `run_cek_pesanan(chat_id, text, mode, bank, kind)` — `kind`: `full`|`deals`. **deals** = filter `[o for o in got if o.get('vouchers')]` (cuma order yg punya voucher Deals).
- **Render PAID ringkas** (Full): `👤 akun` → `• item ×qty — RpXXXX` → `🔗 kode · status` + link. TANPA No/Order/Status/Channel/Dibuat/Dibayar/uid/s-d.
- **Render DEALS** (chat): `👤 akun` → `• item ×qty` (TANPA harga) → `🔗 kode · status` + link. Judul blok: `🎫 DEALS — KODE / LINK`.
- **Export TXT DEALS** (format Maker, EXACT):
  ```
  ===== AKUN: <user> =====
  item    : <item> x<qty>
  nomor   : <nomor|->
  order   : <order_id>

  voucher : N kode
    [i/N] <serial>  (status)
          link: <url>
          uid : <voucher_unique_id>
          s/d : YYYY-MM-DD HH:MM
  ```
  TANPA total/status/channel/dibuat/dibayar. Nama file `deals_<ts>.txt`.
- **REKAP DENOM (deals)** di header chat + export: grouping `Merchant Denom` → jumlah KODE (link), urut **denom NAIK** (`_dnum` pakai `re.search(r'(\d+)rb')` — JANGAN `re.match`, key diawali nama merchant!) lalu nama merchant. Merchant map: indomaret|alfamart|alfamidi|lawson|superindo|ramayana|ranking|dan+dan. Denom: `(\d{1,3})\s*(?:rb\b|ribu|k\b)` — JANGAN pakai `\b` di depan angka (`Rp25RB` → 'p'|'2' bukan word boundary → gagal). Total link = sum semua kode.
- **SEMUA timestamp pakai WIB** = `time.strftime(..., time.gmtime(ts + 7*3600))` + ` WIB`. System TZ host = CST(+8) jadi JANGAN `localtime()`; konversi WIB (+7) eksplisit.
- **PITFALL: `header` di run_cek_pesanan HARUS di-send sendiri** — `_block()` bikin pesan terpisah dan TIDAK termasuk `header`. Kalau lupa `send(chat_id, header)` → rekap/statistik gak muncul (dead code).
- `CEK_LAST[chat_id] = {mode, kind, rows}` — `do_export_cek` baca `kind`; kalau `deals` → format di atas, else format full lama.
- Checklist toggle HARUS `edit_message_text` in-place (bukan delete+send). Callback handler: JANGAN `delete_message` untuk callback `vocset_*`/`vocchk*` — biar ga lempar user ke bawah chat. Simpan `c.message.message_id` untuk edit.
- Output hasil voucher SELALU 2 blok: (1) akun yang MATCH filter (username + file cookie urut), (2) detail voucher SEMUA akun (voc apa aja per akun). JANGAN `return` awal pas filter kosong — blok 2 tetap dikirim.

## Deteksi ShopeeFood — PAKAI FIELD, BUKAN PREFIX KATALOG
- **JANGAN deteksi SF dari prefix kode** (BAUGO/GACOAN/...). Voucher SF bisa pakai prefix BARU yg gak ada di katalog (NUSHI, BAUGO1, BAUGO5) → ke-miss → akun "kosong". DETEKSI dari field API: `voucher_market_type == 8` ATAU `icon_text` mengandung `SHOPEEFOOD`. Ini ground truth dari Shopee sendiri.
- **Label human dari FIELD juga** (bukan katalog prefix): `discount_percentage`/`discount_value`/`discount_cap`/`min_spend` + `customised_labels[].content` + `icon_text`. Prefix katalog cuma buat voucher lama; voucher baru pakai generator field.
- **Micro-unit Shopee = ÷100.000** (min_spend=5000000000 → Rp50.000; cap=2500000000 → Rp25.000; value=800000000 → Rp8.000). BUKAN ÷1e6.
- **JANGAN `.rstrip("0")` di format angka** — "70" jadi "7". Pakai `"%g" % (n/1000)` langsung.
- Payload lengkap dari web: `{exclude_user_voucher_list_type:[], voucher_status:1, user_voucher_list_type:7, voucher_sort_flag:1, cursor:"", limit:50, addition:["voucher_microsite_link"], version:7, priority_voucher_list:null, need_statistics:true, show_red_dot:false}`. `voucher_sort_flag:1` WAJIB (tanpa itu t7=0).
- `user_voucher_list_type=7` = tab ShopeeFood (SF wallet). Tapi voucher SF juga bisa muncul di t1 dgn vmt=8.
- UI tab "ShopeeFood (N)" ngitung lebih banyak dari API (termasuk voucher toko makanan `icon: MAKANAN & MINUMAN`). Yang bot kasih = SF asli (vmt=8).

## Audit bot — kerentanan yang HARUS dicek tiap kali ubah struktur data
- **ISOLASI CONTEXT WAJIB:** 1 tab = 1 browser context (`new_context` per tab). JANGAN share context antar tab "biar hemat RAM" — worker saling timpa cookie → username DUPLIKAT / hasil salah. Ini race, bukan hemat.
- **SEMAPHORE anti-throttle:** Shopee block IP kalau >9 request paralel → akun balik KOSONG. Pasang `asyncio.Semaphore(9)` + jeda 0.12s walau worker banyak. Sweet spot 9 worker (3 browser x 3 tab).
- **DEFAULT SETTING = 3 browser x 3 tab (9 worker) = akurat & stabil. UI tombol: B=1/3/5/8, T=3/4/6/8 (max 8x8=64 worker). Warnai UI: <=9 hijau, <=16 kuning, >16 "kilat tapi bisa throttle". Semaphore 9 jaga dari throttle walau worker banyak.**
- **`_boot_warm` JANGAN hardcode cap** (`min(browser,1)`, `min(tabs,3)`) — warm SESUAI setting boss. Hardcode = worker dikit = cek lambat.
- **PAGE BUTUH MATANG:** page baru di-warm perlu 1-2 run sebelum akurat (run1=0 SF, run3=penuh).
- **UNPACK TUPLE KONSISTEN:** kalau `VOUCHER_CATALOG` diubah (mis. tambah field `is_sfood` → 3-tuple jadi 4-tuple), WAJIB update SEMUA `for a,b,c in` / `[x for x,_ in]` di shopee_bot.py + voucher_checker.py. Lupa satu → `too many values to unpack` → tiap callback crash → log spam ribuan `Infinity polling exception`.
- **BROWSER LEAK:** `_do_warm` harus KILL browser/page berlebih saat setting TURUN, bukan cuma nambah. Kalau cuma nambah → zombie chrome numpuk → OOM, shell mati.
- **STATE RACE:** `set_state/get_state` akses dict global dari banyak thread → wajib `threading.Lock`.
- **UNBOUNDED THREAD:** tiap klik spawn `threading.Thread` — spam klik = ratusan thread = OOM. Pertimbangkan guard.
- **OWNER GUARD:** semua handler (`/start`, callback, document, text) wajib `only_owner()`. Handler utility (`/id`, `/cancel`) sering kelupaan.
- **SECRETS:** `config.json` chmod 600 (default 644 = world-readable → token bocor).
- **JOB 30 AKUN HENG = PASS-2 KEBANYANGAN:** pass-2 recovery 3 round × backoff 2/6/10s × 23 akun = >10 menit sebelum render — Boss kabur sebelum hasil keluar ("udah 100% tapi ga dikirim"). FIX: pass-2 SATU round, max 10 akun, `asyncio.wait_for(..., timeout=14)` per akun → total job 30 akun ±4 menit. TEST end-to-end: 9 pesan terkirim (header+filter+file+4 chunk Blok2).
- **30 AKUN DUMP-PERSIS (Req Boss, 18 Okt):** t7 single sequential +3s delay — akun yg SF muncul: c1tb9zbhwu 19, tk3x0wuo35 18, 04v5q_hq3k 21, zlvru4nb_o 15, wh6pn02899 19, 617e38fow0 18, nvl8dks5b7 21, ssjmx8bpx4 20 (=8 akun). 22 akun lain: err=0 n=0 (ghost). **PATTERN: akun yg SF muncul = akun yang PERNAH dicek banyak kali via bot sebelumnya (warm session).** Ghost = akun jarang dicek. Bukan signature, bukan speed, bukan IP doang — kombinasi cookie-session heat + IP. Cek ulang run-2 kadang muncul.
- **TIPE-7 "GHOST EMPTY" (err=0, n=0) = RISK-FLAG, BUKAN THROTTLE:** akun tertentu dari data center IP → Shopee sembunyiin voucher SF di wallet WEB (err=0, kosong semua voucher_status 1-4), padahal datanya ADA (akun sama bisa 21 SF saat IP bersih / dari app). Bedakan dari throttle (76100003): ghost-empty gak bisa di-retry paksa — pass-2 3 round gak nolong. Tandai `sf_suspect` + lapor "kemungkinan risk-flag, cek manual app". SOLUSI beneran: IP residential / jangan over-farm batch 30 paralel.
- **RETRY ANTI-THROTTLE pakai flag `error=76100003`:** `_one()` retry kalau `out.get("throttled")` (dari API), BUKAN `voucher_n >= 20`. Akun dgn 16 voucher beneran (error=0) langsung return tanpa retry borosan.
- **LABEL BLOK 2 WAJIB pakai `label_from_fields()`** (jangan `label_of(code)` mentah tanpa min). Kalau pakai label katalog mentah: (a) min belanja hilang, (b) voucher identik-label tapi beda min (NUSHI2 min85rb vs NUSHI3 min125rb) ke-dedup jadi satu → "cuma 3 dari 4". Dedup pakai key `label|min_spend|value/cap`, BUKAN label saja.
- **THROTTLE = INDIKATOR API VALID, BUKAN TEBAK JUMLAH:** JANGAN pakai `voucher_n < 20` (akun baru beneran 0-19 voucher). Indikator valid: Shopee balikin `error=76100003` (rate-limit) di body — HTTP tetap 200, `data:null`, `bair[]`. Cara: VOUCHER_JS capture `j.error` per tipe; `_parse` hitung `throttle_hits`; `throttled = throttle_hits > 0`. Akun dgn sedikit voucher tapi `error=0` = BENERAN sedikit.
- **LAPOR THROTTLE, JANGAN BILANG "KOSONG":** `_parse` set `throttled` dari `error=76100003` (lihat atas). Blok 2: kalau akun `throttled` & 0 SF → tampil "⚠️ Kena limit Shopee (throttle) — ulangi cek", BUKAN "— (tidak ada voucher ShopeeFood)". Header: kalau ada akun throttled → warning "+N akun kena limit". Boss marah kalau throttle disamarkan jadi kosong.
- **URUTAN cookie di file ≠ urutan username!** Jangan asal index. `30cok.txt` index 2 = 04v5q_hq3k (bukan index 5). SELALU map via API `get_account_info` (`username` field) dulu sebelum klaim "akun X kosong". Salah index = diagnosa salah total.
- Endpoint `get_user_voucher_list` pakai `limit` + **`data.next` cursor**. WAJIB loop cursor sampai `next` kosong! `limit:50` tanpa pagination bikin tipe 1 kepenuhan (50) dan TIPE LAIN (mặc tipe 7=ShopeeFood) kelihatan KOSONG. Pakai limit:100 + cursor loop (guard 20 iterasi).
- Response per-tipe: `{status:200, list:[...voucher]}`. Jangan json.loads `text` lagi.
- Tipe valid (dari endpoint meta `get_user_voucher_list_meta`): [0,1,2,3,4,6,7,9,10]. t7 = ShopeeFood (15-21 voucher/akun). t1 = toko umum (biasanya 72). t4/9 = kredit.
- Akun yg t7=0 SETELAH retry = benar-benar gak punya SF di voucher wallet. Jangan paksa.

## Label voucher — aturan:
- **`label_from_fields()`: cek KATALOG prefix DULU** (label akurat: 'Diskon Ongkir Rp6rb', 'Mie Gacoan ...'), baru fallback generate dari field (prefix baru).
- **TAG ongkir = "Diskon Ongkir"** (BUKAN "Gratis Ongkir"). Boss koreksi eksplisit.
- **Min belanja WAJIB tampil** — diambil DARI FIELD `min_spend` (variabel tiap voucher, mis. NUSHI1=min 60rb, NUSHI2=min 85rb, NUSHI3=min 125rb). Unit ÷100.000. Jangan hardcode min di label katalog.
- **Prefix NUSHI1/2/3** = voucher pengguna baru, ShopeeFood, tag "Diskon Ongkir" (sebelumnya ke-miss karena gak di katalog).

## Cek voucher — 2 blok output (jangan bingung):
- BLOK 1 (filter): cuma akun yang punya voucher tercentang. BLOK 2: HANYA voucher **ShopeeFood** tiap akun (pakai `SFOOD_PREFIXES` dari katalog — kartu/SPayLater/bank dikeluarkan, dihitung sebagai "non-ShopeeFood"). Mark ✅=sesuai filter, •=ShopeeFood lain.
- Katalog punya flag `is_sfood` per entry. SFOOD_PREFIXES = prefix dgn is_sfood=True. Kartu/bank (BRIDBFOOD/SIMASFOOD/BTNFOOD/DBSFOOD) + SPayLater (ONGKIRLATER/JAJANLATER/COBALATER) = False.
- Kalau user bilang "kosong padahal ada" — cek dulu `voc_settings.json` `checks`. Seringkali filter ke-narrow (cuma 1-2 dicentang) → akun yang punya voucher LAIN dianggap kosong. Engine BENAR, filter-nya sempit. Cek dengan `ids_for_codes` apakah hit match checks.
- `hits` = cuma kode yang match katalog (`ALL_PREFIXES`). Buat "semua voucher", pakai `all_vouchers`.

## Beban VPS — JANGAN pre-warm browser gede
- Browser pre-warm di VPS 8GB WAJIB di-cap keras (browser<=1-3, tab<=3-6). Setting 5 browser × 12 tab = 60 tab = load average 60+, RAM habis, BOT LEMOT/HANG total. Ini penyebab nyata "cek akun tiba-tiba lemot" — cek akun sendiri pure-HTTP ~48 akun/dtk (200 akun = 4.2s), browser idle-lah yang makan CPU.
- Cap di `_save_voc_settings` (browser max 3, tab max 6). Startup pre-warm pakai `min(setting, 1×3)`.
- Flag hemat memori chromium WAJIB: `--js-flags=--max-old-space-size=256`, `--renderer-process-limit=3`, abort resource_type image/media/font/script/stylesheet saat warm (jangan render penuh).
- Warm URL = halaman voucher (`/user/voucher-wallet?type=7`), BUKAN homepage `shopee.co.id` (homepage jauh lebih berat).
- 1 browser headless = ~9-10 proses chrome (1 parent + zygote + gpu + renderer/utility). Itu normal.

## UI bot — export & tombol (koreksi Maker)
- Tombol export (`vcexp_*`) JANGAN hapus pesannya — user harus bisa klik export kategori lain (Aktif, Expired, Ada Nomer, Gak Ada Nomer) berkali-kali tanpa kehilangan tombol. Tambahkan ke `keep_msg` di callback handler + kirim ulang KB setelah tiap export.
- Sama untuk checklist toggle (`vocchk*`, `vocset_*`) — edit in-place, jangan delete+send.
- Semua output username pakai `<code>` (clickable-copy), TANPA `@`.

## Cek voucher — WAJIB scan SEMUA tipe
- JANGAN skip tipe! Scan `range(0,16)` — voucher ShopeeFood/kartu/SPayLater tersebar di tipe berbeda (1=Toko umum, 4/9=Auto/Kredit, 7=ShopeeFood utama). Skip tipe = voucher kelewat blas (bug nyata: akun dgn 19 voucher target cuma kebaca 10).
- Trade-off: 16 tipe ≈ 3x lebih lambat dari 4 tipe. Kalau mau cepet, scan type 7 dulu; kalau ada target langsung kelar; kalau kosong baru scan 0-15.
- Prefix kode voucher banyak banget: BAUGO (ongkir 1-13rb), BAUHI, BAUNG, COBAFU, COBAIN, GACOAN, DKNPU, SHINW, SHPKYCOCT, ONGKIRLATER/JAJANLATER/COBALATER (SPayLater), BRIDBFOOD/SIMASFOOD/BTNFOOD/DBSFOOD (kartu). Katalog di voucher_catalog.py — tambah terus kalau ada prefix baru.
- PENTING: sort prefix by panjang DESC sebelum match (BAUGO13 sebelum BAUGO1) — kalau tidak, BAUGO12 akan salah ke-match jadi BAUGO1.

## Username & warm-up (WAJIB)
- Username TIDAK dari mapping accounts.json (akun baru gak ada) — ambil dari API `GET /api/v4/account/basic/get_account_info` field `data.username`. Fetch PARALEL dengan voucher (1 worker = 2 request bareng).
- Warm-up browser: goto `https://shopee.co.id/` (base, BUKAN `/user/voucher-wallet?type=7`) — biar SDK/SAP token penuh ke-load. Cek pakai browser pre-warm = 0 dtk launch.
- Browser pre-warm: persistent pool (`browser_warmer.py`), launch sejak bot START + saat setting berubah. JANGAN kill setelah dipakai.
- Playwright object terikat event-loop → coroutine cek HARUS jalan di loop pool (`pool.submit`), bukan `asyncio.run` (deadlock). Di dalam coroutine, panggil `await pool._do_warm()`, JANGAN `pool.warm()` (self-submit deadlock).

## Voucher check — tuning kecepatan & filter
- Endpoint voucher scan multi-tipe: cuma tipe 1 (Diskon/Toko), 4 (Auto/Kredit), 7 (ShopeeFood), 9 (Kredit) yang ada isinya — tipe 2,3,5,6,8,10,11 SELALU kosong. Scan [1,4,7,9] saja = 3x lebih cepat.
- TIDAK perlu page.goto per akun: cukup context.clear_cookies() + add_cookies() + page.evaluate() (SDK udah ke-load saat warm-up). goto per akun = buang 1.5s.
- Paralel 4 tipe sekaligus via Promise.all, BUKAN loop serial.
- Tipe=1 balikin 50 voucher default (voucher toko umum) — itu normal, bukan bug.
- Bottleneck sejati = latency Shopee per akun (~0.6-1.4s), bukan CPU. Nambah worker di atas 8 tidak menambah throughput (throttle).
- Default: direct (no proxy). VOC_SOCKS_PORTS=off.
- Filter checklist: label human di voucher_catalog.py (VOUCHER_CATALOG), output HANYA akun yang punya voucher tercentang, username dulu lalu file cookie urut.

## Hapus database akun (fitur bot + CLI, shipped 2026-10-28)
- Bot: Tools → `💀 HAPUS SEMUA AKUN` (`m_delall`) → double-confirm `delall_yes` (akun saja) / `delall_full` (akun + file turunan). Handler `do_del_all(chat_id, purge_derived)`.
- CLI: `python3 nuke_accounts.py` (dry-run) | `--yes` | `--yes --full`. Backup auto ke `accounts.backup.<ts>.json` SEBELUM wipe — jangan pernah wipe tanpa backup.
- File turunan yg dibersihin: `acc_check_result.json`, `db_check_result.json`, `30cok.txt`, `response.txt`.
- Restore: `cp accounts.backup.<ts>.json accounts.json`.

## Pitfalls

- Don't run `shopee_bot.py` and `v2_bulk.py` on the same bot token — getUpdates conflict.
- **Jangan tinggalkan DUA instance `shopee_bot.py`** (satu systemd + satu orphan lama PPID 1) → getUpdates conflict, polling saling bunuh. Cek `pgrep -af shopee_bot.py` setelah restart; bunuh orphan tadi.
- **Cookie akun dari accounts.json banyak yg mati (`error=19`, tracking residue):** probe `get_account_info` dulu per akun sebelum narik order. idx=0 (`c1tb9zbhwu`) contoh = error19. `error=19` = cookie bukan sesi login (SPC_U/SPC_ST/SPC_CLIENTID gak nyambung).
- Missing `digital_api` module (imported by the bot's dig-catalog feature) breaks import — recreate from `skill/scripts/order_digital.py`.
- Datacenter proxies render Shopee as a blank page (CDN `deo.shopeemobile.com` bundles fail); residential or tunnel-relay required. See `selfhosted-service-vps-exposure`.
- CLI menu prints `clear_screen()` — run headless-safe or subclass menus when driving non-interactively.
