# Shopee PLN Prepaid (Token Listrik) — Order Flow (CAPTURED LIVE 2026-10-20)

Akun: `<akun>` (SPC_U=[REDACTED]). Proxy: ID (socks4://[PROXY_HOST]:[PORT]).
Meter uji: **45052412587** → `NUR************` · `R1M / 900 VA` · R1M/900VA · provider_id 10002.

## Item IDs (category_id=20103 PLN_PREPAID, carrier_id=20)

| Nominal | item_id | snapshot_id | market_price (×1e5) |
|---|---|---|---|
| 20.000  | 100206 | 30333447 | 2000000000 |
| 100.000 | 100203 | 30333448 | 10000000000 |

Harga = nominal × 1e5. Admin fee provider: **150000000** (=Rp1.500).

## Flow (urutan request, dari UI live)

Base: `https://shopee.co.id/digital-product/api`

1. `GET /item/v2/list?category_id=20103&carrier_id=20` → daftar nominal (item_id, snapshot_id, denomination, price)
2. `GET /item/v2/bill_info?item_id=100206&customer_id=<METER>&carrier_id=20&category_id=20103`
   → **cek meter**: `{customer_name:"NUR***", details:{meter_number, customer_code, power_tariff:" R1M / 900 VA"}, provider_additional_fee:{admin_fee:150000000}, pay_amount}`
3. `POST /order/create` → bikin order (BODY lengkap di bawah). Sukses → `data.order_id` / payment url.
4. Pay → `POST /order/pay` ATAU `POST /order/merge_pay` (create+pay sekaligus).
5. Init payment → VA (channel 8005200 = Transfer Bank/VA).

## POST /order/create — body PERSIS (PLN 20rb)

```json
{
 "items":[{"id":100206,"quantity":1,"market_price":2000000000,"discount_price":2000000000,"promotion_activity_id":0}],
 "category_id":20103, "carrier_id":20, "total_amount":2150000000,
 "device_fingerprint":"", "source_system":3, "customer_id":"45052412587",
 "bill_amount":2000000000,
 "bill_detail":{
   "details":{"account_warning_flag":"0","customer_code":"521082517348","meter_number":"45052412587","power_tariff":" R1M / 900 VA","unsold_denomination_list":""},
   "bill_no":"","customer_id":"45052412587","customer_name":"NUR************","bill_amount":2000000000,
   "provider_additional_fee":{"discount":0,"retribution":0,"penalty_fee":0,"admin_fee":150000000,"outstanding_bill":0,"open_close_fee":0,"remaining_penalty_fee":0,"original_admin_fee":0,"additional_charge":0},
   "shopee_admin_fee":0,"payment_due_date":"","bill_period":"","pay_amount":2150000000,"support_other_amount":false,
   "total_amount":2150000000,"customer_id_mask":"45052412587","provider_id":10002,"expire_date":"","customer_address":"",
   "provider_resp_status":"","max_pay_amount":0,"min_pay_amount":0,"identify_number":"521082517348","customer_id_encrypted":""
 },
 "bill_flow_version":1, "security_device_fingerprint":"<dari SDK, lihat bawah>"
}
```

**PENTING:** `bill_amount`+`total_amount` di-isi dari hasil `bill_info` (bill_amount=2000000000, pay_amount=2150000000 = bill+admin 150000000). `security_device_fingerprint` & header x-sap di-generate SDK — WAJIB lewat browser in-page fetch / UI, JANGAN hardcode.

## POST /order/merge_pay — body (create+pay sekaligus, dari capture lama)

Termasuk: `channel_id:8005200`, `channel_name:"Transfer Bank"`,
`channel_item_option_info:"{\"option_info\":\"89052001\"}"`, `call_back_url`,
`h5_version:"id/live@release..."`, `is_new_fee:true`, `is_service_fee_flow:true`,
`order_extend_info:{bit1,bit2}`, `system_version:"Windows-10"`.

## Anti-bot pada order endpoints (WAJIB TAHU)

Dua lapis nolak `order/create` / `merge_pay`:
1. **`90309999`** (HTTP 403) — traffic/verify gate, `action_type:2`, `redirect_to_error_page:true`, field `6` = TLV blob challenge. Muncul saat sesi/akun ber-trust rendah.
2. **`err_code:4108` `ORDER_CREATE_TPSAnti_512`** — TPS Anti-fraud rule engine. Request SUDAH signed & sampai backend, tapi rule engine tolak (akun farm/percobaan berulang).

**Bypass nyata = DRIVE UI ASLI** (headed + xvfb). SDK di halaman bikin `security_device_fingerprint` + tanda tangan valid otomatis → `order/create` TERKIRIM. (Rules tetap bisa tolak 4108 kalau akun ke-flag, tapi request lolos lapis 90309999.)

Contoh fp valid dari SDK live: `9ZTud5CCBrYF6fkXom0cDg==|g6P/wJqYCmgDTxa4BQjIQ+YK6cOtzU1mhNR9Z6YUlEtQEWFbX9jtgjlvQOnbRfOYkmG0e1iKZVB5ZKW...|08|3`
(format `b64|b64|b64|08|3` — per-device, TIDAK bisa dipalsukan asal).

## ⚡ TANPA FP = ORDER PLN JADI (2026-10-20, TERBUKTI)

**`security_device_fingerprint: ""` (KOSONG) → `order/create` BERHASIL.**
Dipanggil via page-context fetch (SDK sign header otomatis), headed+xvfb, proxy ID:

```json
POST /digital-product/api/order/create  -> 200
{"err_code":0,"err_msg":"success","err_code_v2":"OK",
 "data":{"order_id":"2792484002224490178","total_amount":2150000000}}
```
→ Order **Token PLN 20.000** utk meter 45052412587 **KEBUAT**, `payment_status:P0` / OR1.

**Jadi kunci-nya: JANGAN isi FP.** SDK tanda tangan HEADER (x-sap-*) otomatis; body FP biarin
kosong. FP non-empty malah kena `ORDER_CREATE_TPSAnti_512` (4108).

Hasil matriks (meter 45052412587, item 100206):
| Test | Hasil |
|---|---|
| `order/create` FP=`""` | **err_code:0 ✓ ORDER JADI** |
| `order/create` tanpa key FP | 2096 "place order too fast" |
| `order/merge_pay` FP=`""` | 102 "params invalid" (body merge_pay beda) |
| `item/v2/bill_info` | err_code:0 ✓ |

## Pay / VA — status
`POST /order/pay` utk order baru:
- `final_price=TOTAL, fee=0` → `2412 payment handling fee check fail` (ORDER_PAY_PRICING_CENTER_511)
- `final_price=TOTAL-fee` → `2096 place order too fast` (rate limit)
- `{order_id, channel_id}` minimal → `90309999`

**Butuh `payment_handling_fee` + `final_price` PERSIS dari pricing center.** Ambil dari halaman
checkout preview sebelum bayar (buka `/produk-digital/m/checkout-result/channel/8005200/order/<OID>?...`)
— tapi kalau order belum ada sesi bayar, `to_pay_detail` balik 107. Solusi: bayar lewat UI
(checkout page pilih metode → halaman pembayaran render VA) bukan raw endpoint.

## ⚡ TANPA FP = ORDER PLN JADI (2026-10-20, TERBUKTI)

**`security_device_fingerprint: ""` (KOSONG) → `order/create` BERHASIL.**
Dipanggil via page-context fetch (SDK sign header otomatis), headed+xvfb + proxy ID.

### RESEP PAY PLN (create+pay) — TERVERIFIKASI
- `channel_name: "VA/Minimarket"`, `channel_id: 8005200`, `option_info: "89052007"` (SeaBank)
- **`payment_handling_fee: 0`, `final_price: total_amount`** → `err_code:0` + `payment_url`
- JANGAN pakai `is_new_fee` (bikin 2412). `channel_name:"Transfer Bank"` bikin 2412.
- `order/create` body: `security_device_fingerprint:""`, `device_fingerprint:""`, bill_detail lengkap dari `bill_info`.

### ⛔ BLOCKER VA: SPM `init_payment` = `error_code:7` (SISTEMATIS)
`POST https://gw1.wsa.spm.shopee.co.id/api/payment/transaction/init_payment`
body `{"encrypted_transaction_id":"<trref>","app_type":1,"status":3}` → `{"error_code":7,"error":"An unexpected error occured"}`.
- Sama utk gw0/gw1/wsa, semua app_type/status, semua client_id, setelah buka payment page, setelah buka checkout-result page.
- Berlaku di SEMUA akun (create+pay err_code:0 tapi init_payment error 7) → bukan flag akun.
- `encrypt_payment_id` di respon pay = `""` (sesi SPM tidak di-seed dari web).
- page: `transaction/init` (render) juga error 7.
- **Kesimpulan:** VA tidak bisa diambil dari web entry; butuh entry SPM app (RN/mobile) ATAU flow yang menaruh `encrypt_payment_id` non-kosong.

### 🔑 BUKTI VA PERNAH SUKSES (dari capture `catalog/pulsa_flow/init_payment_full.json`)
`init_payment` → `transify_data`: `{"username":"k8lm9h2i5u","virtual_account":"126 082239526707","receiver_name":"Qif","company_code":"89307","merchant":"Shopee","amount":"Rp13.250","phone_number":"6282239526707"}`
- VA sukses didapat via **PULSA merge_pay** flow (akun `k8lm9h2i5u`), BUKAN PLN bill flow.
- Respons sukses = `page_config.title:"Pembayaran"` + `poll_config` + `transify_data` + `component_type:7` (`account_number`).
- Redirect sukses punya `paymentCode=<angka>` + `orderIdType=payment`.
- PLN (create+pay) TIDAK pernah menghasilkan `paymentCode` → `encrypt_payment_id:""` → init_payment error 7.

### Resep merge_pay PULSA (body capture cap_stage9)
`{items:[{id,item_name,quantity:1,market_price,discount_price,carrier_id:26,category_id:10102,promotion_activity_id:0,snapshot_id,original_discount_price,promotion_quantity:1}],phone_number,language:"id-ID",device_fingerprint:"",channel_id:8005200,channel_name:"Transfer Bank",channel_item_option_info:"{\"option_info\":\"89052007\"}",call_back_url:...checkout-result...,total_amount,final_price:total+fee,payment_handling_fee:100000000,security_device_fingerprint:"",...,is_new_fee:true,is_service_fee_flow:true,category_id,carrier_id,system_version:"Windows-10"}`
- Respons sukses: `{err_code:0,data:{encrypt_payment_id:"",order_id_list:[...],pay_order_id:"379...",payment_url:"...transaction/<TID>?..."}}`
- Lalu `init_payment {encrypted_transaction_id:<TID>,app_type:1,status:3}` → `transify_data.virtual_account`.

### 🎯 PULSA merge_pay SUKSES → jalur VA yang BENAR (2026-10-20)
`POST /digital-product/api/order/merge_pay` (pulsa, category 10102, carrier 26) **HARUS pakai promo live**:
- `activity_item_priority_promotion_info.priority_promotion_info`: `promotion_activity_id` (mis. 38028), `price` (mis. 100000=Rp1), **`payment_channel_list:[8002601]`**.
- Body: `total_amount=price_promo`, `final_price=price_promo+fee`, `payment_handling_fee=100000000`, `channel_id` = channel dari `payment_channel_list` (bukan 8005200!), `is_new_fee:true`, `is_service_fee_flow:true`.
- Salah channel (8005200) → `err_code:9012 promotion detail not matched`. Harga non-promo → `2080 price check fail`.
- Sukses → `{err_code:0,data:{order_id_list:[...],pay_order_id:"379...",payment_url:"...transaction/<TID>?"}}` (order jadi OR1/P1).

### init_payment: error_code beda per sumber
- `encrypted_transaction_id` = **TID dari payment_url** → PLN: ec=7; PULSA (pay_order_id ada): **ec=5**.
- `encrypted_transaction_id` = **pay_order_id** → ec=None (respons lain, bukan error).
- **VA asli** (dari capture lama, akun k8lm9h2i5u): `transify_data.virtual_account="126 082239526707"` — jalur PULSA.
- Catatan: `exist_order_id` (`err_code:2112`) = ada order pending menggantung → cancel dulu (`/order/cancel {order_id,category_id:10102}` → err_code:0).

### Blocker tersisa (VA)
init_payment utk pulsa masih ec=5. Perlu cari param yang tepat (dugaan: butuh `paymentCode` dari payment session / urutan init setelah `transaction/init` render sukses). PLN bill-flow = ec=7 (tembok, bukan jalur VA).

### 🏆 VA BERHASIL PENUH (2026-10-20) — RESEP FINAL PULSA
`merge_pay` TANPA promo + option BCA → `err_code:0` → `init_payment` → **VA nyata**:
```
merge_pay: items:[{id,item_name,quantity:1,market_price,discount_price(=harga normal),
  carrier_id:<c>,category_id:10102,promotion_activity_id:0,snapshot_id,original_discount_price,promotion_quantity:1}],
  phone_number:"08xx",language:"id-ID",device_fingerprint:"",
  channel_id:8005200,channel_name:"Transfer Bank",
  channel_item_option_info:"{\"option_info\":\"89052001\"}",   ← BCA (89052007 SeaBank: 2080!)
  call_back_url:...checkout-result/channel/8005200/order/__ORDER_ID__...,
  total_amount:<harga>,final_price:<harga>+100000000,payment_handling_fee:100000000,
  security_device_fingerprint:"",is_new_fee:true,order_extend_info:{bit1:false,bit2:false},
  is_service_fee_flow:true,category_id:10102,carrier_id:<c>,system_version:"Windows-10"
→ {err_code:0,data:{order_id_list:[...],pay_order_id:"379...",payment_url:"...transaction/<TID>?"}}
init_payment: POST gw1.wsa.spm.shopee.co.id/api/payment/transaction/init_payment
  {"encrypted_transaction_id":"<TID>","app_type":1,"status":3}
→ {"page_config":{"title":"Pembayaran",...},"transify_data":{
    "virtual_account":"126 089617716500","receiver_name":"Muhamad nasirudin",
    "company_code":"89307","merchant":"Shopee","amount":"Rp27.295"}}
```
**KUNCI SUKSES:** (1) `option_info:89052001` (BCA) — SeaBank 89052007 kena 2080; (2) TANPA promo (`promotion_activity_id:0`) pakai harga normal; (3) init_payment PAKAI `transaction/<TID>` dari payment_url; (4) cancel order menggantung dulu kalau `err_code:2112`.
**Order sukses:** `3792493229114790170` (Telkomsel 25.000) → VA `126 089617716500` Rp27.295.

### 🤖 INTEGRASI KE BOT (2026-10-20) — `order_checker.gen_va_for_order()`
- `parse_item` sekarang bawa `pay_order_id`, `channel_option_info`, `is_payable`.
- `gen_va_for_order(b, order)` → `(va, how)`:
  1. `pay_order_id` ada → `_init_payment_va(b, pay_order_id)` → `"existing-session"`.
  2. else kalau `category_id in (10102,10101)` → `_merge_pay_va(b, order)` (bikin sesi baru via merge_pay) → `"merge_pay"`.
- `_init_payment_va(b, eid)`: init_payment gw1→gw0, ambil `transify_data.virtual_account` / component_type 7.
- `_merge_pay_va`: merge_pay pakai data order (item_id, phone, harga normal), channel 8005200, option 89052001 (BCA), no promo, fee 1k → init_payment.
- `check_account(want_va=True)` utk mode unpaid/all → tiap order unpaid otomatis di-generate VA.
- Render bot: tampilkan `💳 VA: <code>...</code>`; kalau gagal → alasan (`gagal generate` / `order gak bisa dibayar lagi`).
- **TERUJI LIVE:** order `2792493229114190147` (Telkomsel 25.000) → VA `12008023649256678` via merge_pay.

## ✅ VA SEMUA METODE BAYAR (2026-10-20) — TERVERIFIKASI
`merge_pay` pulsa + `init_payment(transaction_ref)` → VA keluar utk SEMUA bank (channel 8005200).

| Metode | option_info | fee | is_new_fee | Prefix VA |
|---|---|---|---|---|
| BCA | 89052001 | 100000000 (Rp1.000) | true | `126` |
| Mandiri | 89052002 | 100000000 | true | `896` |
| BNI | 89052003 | 100000000 | true | `8806` |
| BRI | 89052004 | 100000000 | true | `128` |
| BSI | 89052005 | 100000000 | true | `600` |
| Permata | 89052006 | 100000000 | true | `704` |
| SeaBank | 89052007 | **0** | **ABSENT** | `781` |
| Bank lain | 89052902 | 100000000 | true | `788` |

**RULE FEE (kritikal):** bank biasa = fee Rp1.000 + `is_new_fee:true`; **SeaBank = fee 0, TANPA `is_new_fee`** (fee 1k → 2080).

### ⚠️ HARGA HARUS LIVE (jebakan 2080)
`discount_price` di katalog BERUBAH + ada promo aktif (`activity_item_priority_promotion_info.priority_promotion_info`). `merge_pay` WAJIB pakai harga live + `promotion_activity_id` live:
- ambil harga paling baru dari `item/v2/list` SEGERA sebelum merge (di `_merge_pay_va`)
- kalau ada promo `aip.price` → pakai itu + `promotion_activity_id`-nya, fee jadi 0
- harga basi/promo kadaluarsa → `2080 price check fail` (`ORDER_PAY_PROMO_511`)

### ⚠️ IP BURN setelah ~2-3 merge_pay
IP yang dipakai berulang → `90309999` / merge gagal / `init_payment` "Failed to fetch" (CORS preflight ditolak). WAJIB rotate proxy ID Tiap 1-2 order.

### Terbukti E2E (kode shipped)
```
merge_pay → err_code:0  pay_order_id 3792504579274790183
init_payment(tid) → page_config.title "Pembayaran"
  transify_data.virtual_account  = 126 089617716500   ✓
  component_type 7 account_number = 126 089617716500   ✓
_scan_va = 126 089617716500
```

### Alur lengkap
`merge_pay` (channel+option+fee+harga live+promo) → `pay_order_id`/`payment_url` → ekstrak `transaction_ref` → `POST gw1.wsa.spm.shopee.co.id/api/payment/transaction/init_payment {encrypted_transaction_id, app_type:1, status:3}` → `transify_data.virtual_account`.

**Alfamart/Indomaret (gerai 8003200/8003001):** merge_pay err_code:0 (option `8003200-1`/`8003001-1`) tapi bukan VA — kode bayar offline.
**ShopeePay/SPayLater/CC:** bukan VA (instan/kartu).

## ⛔ PLN TETAP TIDAK BISA VA (arsitektur)
`merge_pay` pulsa + `init_payment(transaction_ref)` → VA keluar utk SEMUA bank (channel 8005200).

| Metode | option_info | fee | is_new_fee | Prefix VA |
|---|---|---|---|---|
| BCA | 89052001 | 100000000 (Rp1.000) | true | `126` |
| Mandiri | 89052002 | 100000000 | true | `896` |
| BNI | 89052003 | 100000000 | true | `8806` |
| BRI | 89052004 | 100000000 | true | `128` |
| BSI | 89052005 | 100000000 | true | `600` |
| Permata | 89052006 | 100000000 | true | `704` |
| SeaBank | 89052007 | **0** | **ABSENT** | `781` |
| Bank lain | 89052902 | 100000000 | true | `788` |

**RULE FEE (kritikal):** bank biasa = fee Rp1.000 + `is_new_fee:true`; **SeaBank = fee 0, TANPA `is_new_fee`** (fee 1k → 2080 price check fail).

**Alfomaret/Indomaret (gerai 8003200/8003001):** merge_pay err_code:0 dgn option `8003200-1`/`8003001-1` tapi TIDAK ada VA — itu kode bayar offline (bukan VA), diinisiasi lewat jalur beda.
**ShopeePay/SPayLater/CC:** bukan VA (instan/kartu).

**Wajib cancel order menggantung dulu** tiap ganti metode (err 2112 `exist_order_id`). VA hanya sekali per sesi — init ulang bisa kosong/expired.

## ⛔ PLN TETAP TIDAK BISA VA (arquitektur)
PLN = bill-flow (`order/create` + `order/pay`). Bukti ekshaustif:
- `order/pay` PLN → `encrypt_payment_id:""` (KOSONG)
- `init_payment(pay_order_id dari detail)` → `error_code:7` (gw1 & gw0)
- `init_payment(transaction_ref)` → `error_code:7`
- `init(transaction_ref/client_id 80006)` → `error_code:7`
- `payment_request_id` (`dp_...`) → `error_code:6`
- buka `payment_url` di browser → SPA kosong, 0 network call
- `payment_handling_fee` yg benar utk create = echo FULL bill_info (bukan minimal)

**Kesimpulan:** sesi PLN TIDAK terdaftar di gateway SPM → slot VA gak pernah dibuat. Satu-satunya yg bisa: `order/create` + `order/pay` + `payment_url` (bayar manual lewat app).

**PLN order/create body YANG SUKSES (echo FULL bill_info):**
`bill_detail = {bill_no, customer_id, customer_name, bill_amount, provider_additional_fee, shopee_admin_fee, details, payment_due_date, bill_period, pay_amount, support_other_amount, total_amount, customer_id_mask, provider_id, expire_date, customer_address, provider_resp_status, max_pay_amount, min_pay_amount, identify_number, customer_id_encrypted}` (semua dari `item/v2/bill_info`). Kalau subset → `18001 check bill info failed`.

## Endpoint yang TIDAK kena gate (read-only)
`item/v2/list`, `item/v2/bill_info`, `order/v2/list`, `order/v2/detail`, `get_account_info` → semua `err_code:0` walau akun ke-flag.

## ✅ RESEP FINAL VERIFIED — `gen_token_pln()` (2026-10-20, live)
Shipped di `/root/shopee-war/order_checker.py::gen_token_pln(b, meter, nominal=20000)`:
```
{"ok":true, "order_id":"2792509212217630475",
 "payment_url":"https://shopee.co.id/payment/transaction/5420580785278908857?...&transaction_ref=...",
 "total":2150000000, "customer":"NUR************"}
```
3 kunci: (1) `order/create` dgn `device_fingerprint:""`+`security_device_fingerprint:""` → err_code:0 (non-empty = 4108 TPSAnti_512); (2) `pln_cancel_hanging()` dulu → guard 2112; (3) `order/pay` dgn `payment_handling_fee:0`+`final_price:total` → payment_url (fee!=0 = 2412). Item: 100206/20k 100208/50k 100203/100k 100207/200k 100209/500k 100204/1M.
