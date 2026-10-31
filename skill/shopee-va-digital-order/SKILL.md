---
name: shopee-va-digital-order
description: Use when extracting Shopee digital-product VA numbers.
---

# Shopee Digital-Product VA Extraction

## When to use
Getting the Virtual Account / payment code for a Shopee digital-product order
(pulsa, paket data, PLN, voucher) via the mobile/pc API, without drag captcha.

## The core gate: `90309999`
Every WRITE endpoint (`order/create`, `order/pay`, `order/merge_pay`) returns
`{"error":90309999,"action_type":2,"redirect_to_error_page":true}` when the
anti-fraud device token is missing. This is NOT a drag captcha — it's the
`af-ac-enc-sz-token` / `security_device_fingerprint` layer.
READ endpoints (`item/v2/list`, `bill_info`, `account/phone`, `order/v2/detail`)
do NOT require it — only WRITES do.

### What does NOT fix it
- Empty `device_fingerprint` alone (many docs claim it bypasses — it does not by itself)
- `INJECT_FINGERPRINT` placeholder (guarantees 403)
- Adding residential proxy (proxy fixes network/geo, not the token)
- Raw `fetch()` from the homepage (SDK not warm on that route)

### What DOES move past 90309999
Request must originate from the **real product page context**
(`/produk-digital/<slug>`) where the Sense SDK is loaded and hooks `window.fetch`
(`window.__sap_hook_fetch === true`). The SDK then auto-injects `x-sap-ri`,
`x-sap-sec`, and generates a **real** `security_device_fingerprint` of the form:
```
b64(16B)|b64(64B sig)|b64(12B)|08|3
# e.g. QMaDMOjfJaNs48kW7IkO8w==|EqV+bggJ...|gdKkK6mJ...|08|3
```
When the H5 checkout page (`/produk-digital/m/static-checkout`) sends merge_pay,
the gate becomes `err_code 102 params invalid` instead of `90309999` — proof the
token passed and only the payload is incomplete.

## Working flow (PC/H5)
1. Warm: `goto https://shopee.co.id/produk-digital/pulsa` (or any produk-digital
page) and wait ~6s so the SDK initialises (`window.__sap_hook_fetch` true).
2. Read bill (works unauthenticated-by-token):
   `GET /digital-product/api/item/v2/bill_info?customer_id=<id>&category_id=<cat>&carrier_id=<c>&item_id=<item>`
3. Build the checkout H5 URL:
   `https://shopee.co.id/produk-digital/m/static-checkout?dp_from_source=36&cacheInfo=<urlenc json>`
   cacheInfo = `{"phoneNumber":..,"categoryId":..,"carrierId":..,"itemInfo":{...}}`.
   **The H5 reads the bill from cacheInfo** — if absent it renders
   `Stand Meter/No. Pelanggan: undefined` and merge_pay sends no `bill_detail` → 102.
4. Click "Bayar Sekarang" → H5 calls `order/merge_pay` (signed) → `payment_url`.
5. `payment_url` gives `transaction_ref`; POST it to
   `https://gw1.wsa.spm.shopee.co.id/api/payment/transaction/init_payment`
   `{"encrypted_transaction_id":<ref>,"app_type":1,"status":3}`
6. Response `transify_data.virtual_account` = the VA.

## merge_pay body (from a verified success capture)
```json
{"items":[{"id":ITEM,"item_name":"..","quantity":1,"market_price":AMT,
  "discount_price":AMT,"carrier_id":CARR,"category_id":CAT,"promotion_activity_id":0,
  "snapshot_id":SNAP,"original_discount_price":AMT,"promotion_quantity":1}],
 "phone_number":CUST,"language":"id-ID","device_fingerprint":"",
 "channel_id":8005200,"channel_name":"Transfer Bank",
 "channel_item_option_info":"{\"option_info\":\"89052001\"}",
 "call_back_url":"https://shopee.co.id/produk-digital/m/checkout-result/channel/8005200/order/__ORDER_ID__?fromSource=checkoutH5&categoryId=CAT&orderIdType=payment",
 "total_amount":AMT,"final_price":AMT+FEE,"payment_handling_fee":FEE,
 "security_device_fingerprint":"","h5_version":"id/live@release-2026.10.v2",
 "is_new_fee":true,"order_extend_info":{"bit1":false,"bit2":false},
 "is_service_fee_flow":true,"category_id":CAT,"carrier_id":CARR,"system_version":"Windows-10"}
```

## Channels (from shopee_bot.py PAY map)
- SeaBank: channel 8005200, option_info 89052007
- Bank BCA: 8005200, 89052001 | Mandiri: 8005200, 89052002
- Indomaret (bayar di toko): channel 8003001, option_info "none", fee Rp2.500
- VA fingerprint: BCA `126`+customer_id; SeaBank `7810`+phone[2:]

## SDK internals
- Global: `window.ssdk00oQOOooO00QoQO` (constructor, closure — not callable directly)
- localStorage: `_sapid` (device id), `mdap_persisttk_tiny_live_persisttk` (MDAP JWT),
  `__WIR_SZ_UNIQ_DC`
- 4 anti-fraud headers: `af-ac-enc-sz-token`, `x-sap-ri`, `x-sap-sec`, `af-ac-enc-dat`
  (reads get only x-sap-ri/x-sap-sec; higher-trust writes want the sz-token too).

## Pitfalls
- `requests`/raw HTTP to shopee API → `error 19 Failed to authenticate` even with a
  valid cookie. Must use the browser context (Playwright `page.evaluate(fetch)`).
- Cookie `SPC_F=<hex>_unknown` = device not yet bound; becomes `_known` after SDK runs.
- Datacenter IPs (e.g. Tencent SG) get blocked on the H5's internal calls →
  "Jaringan Error Silakan Coba Lagi". Use a residential ID proxy.
- The product-page meter input resists synthetic typing (React uncontrolled +
  re-created node) — `press_sequentially`, `fill`, and native value-setter all
  registered empty in testing; driving it as a real user needs a genuine tap/keypad.
- `pkill -f shopee_bot.py` kills the invoking shell — use
  `pgrep -af "python.*shopee_bot.py"` then kill the PID.
- Pack `accounts.json` cookies expire in ~2-3 weeks; always re-check liveness via the
  browser context, not raw requests.
