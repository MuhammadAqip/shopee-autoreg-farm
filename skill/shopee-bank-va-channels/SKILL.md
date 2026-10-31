---
name: shopee-bank-va-channels
description: Use when a Shopee VA order fails. Bank channel matrix.
version: 1.0.0
author: curator
license: MIT
metadata:
  hermes:
    tags: [shopee, virtual-account, payment-channels, bank, digital-product]
    related_skills: [shopee-va-digital-order, shopee-token-war-stack, transacting-api-automation]
---

# Shopee Bank VA Channels — matrix & failure traps

## When to Use

- An order exists but the user reports **no VA / VA kosong**.
- A bank channel needs adding, switching, or its fee/flag adjusted.
- `merge_pay` returned `err_code: 0` yet `init_payment` produced no account number.
- You are about to "try every bank" — read the traps first; most sweeps fail on a
  constant rather than on the value being swept.

Routing a Shopee digital-product order to a specific bank's Virtual Account. The
user-facing symptom is always "VA-nya kosong" — the order exists, the payment page
loads, no account number. Almost every time it is one of four traps below, and the
error code tells you which.

## Hard precondition

VA only exists on the **pulsa** path (`category_id: 10102`, one-step `merge_pay`).
PLN (`20103`) is a bill-flow whose `encrypt_payment_id` is always empty, so its
`init_payment` returns `error_code: 7` and no VA slot is created. That is
architecture — do not debug PLN for a VA.

## Bank matrix (all verified working)

Every row: `channel_id: 8005200`, `channel_name: "Transfer Bank"`, category
`10102`, and **both** `device_fingerprint` and `security_device_fingerprint` sent as
`""`. Always `final_price = total_amount + payment_handling_fee`.

| bank | `option_info` | fee (Rp) | `is_new_fee` | min denom | VA shape |
|---|---|---|---|---|---|
| SeaBank | `89052007` | **0** | **omit the key** | 2.000 | `781` + random |
| BCA | `89052001` | 1.000 | yes | **10.000** | `126 ` + phone |
| Mandiri | `89052002` | 1.000 | yes | 2.000 | `896 ` + phone |
| BNI | `89052003` | 1.000 | yes | 2.000 | `8806 ` + phone |
| BRI | `89052004` | 1.000 | yes | 2.000 | `128 ` + phone |
| BSI | `89052005` | 1.000 | yes | 2.000 | `600 ` + phone |
| Permata | `89052006` | 1.000 | yes | 2.000 | `704 ` + phone |
| Bank lain | `89052902` | 1.000 | yes | 2.000 | `788 ` + phone |
| Alfamart | channel `8003200`, **no option** | 2.500 | yes | 2.000 | payment CODE, not a VA |

**Non-bank channels do not share the bank channel id.** Alfamart rides
`channel_id: 8003200` with an empty `channel_item_option_info` (`"{}"`) and returns a
store payment code (e.g. `KJNQZEDKW43QS98`) instead of a `transify_data.virtual_account`
number — the caller must render it as a code, not a VA. Fee for it is keyed on the
**channel id**, never on an `option_info` (there is none to key on).

## Trap 7 — `2021` on a channel the user SWEARS they selected

When the user picks a valid channel from the menu and still gets `2021`, stop sweeping
channels — the channel id never reached the payload. A state getter that returns a
**copy** (`dict(STATE[...])`, `.copy()`, a lock-guarded snapshot) makes `st["ch_id"] = ...`
write into a throwaway object, so the order is built with `channel_id: None` and the
server answers `2021` because no channel was named.

- **Use `2021` on a KNOWN-GOOD id as the tell for a missing value, not a retired channel.**
  `pay_1`/SeaBank is verified live; if selecting it yields `2021`, the option never left
  the callback.
- **After mutating a getter's return value, call the setter explicitly** —
  `set_state(chat_id, ch_id=ch_id, opt=opt, pay_name=name)` — and do not rely on the
  getter aliasing the store.
- **Log at the consumption point**: `print(f"ORDER ch_id={ch_id} opt={opt!r} bank={name}")`
  immediately before `merge_pay`. `opt=None` ends the investigation instantly.
- **Guard the order builder** with a valid default channel + a log line naming the branch,
  so a dropped value degrades to a working channel instead of `2021`.
- **Verify by round-trip, not by tapping**: import the bot module, apply the selection the
  same way the callback does, read it back through the getter, and assert equality for
  EVERY entry in the channel map. Runs in ~1s and costs no live order.
- Sweep fees, flags, and channel ids only after this check passes — a constant that never
  arrives makes every sweep return the same `2021`.

The same copy-vs-reference bug hits any selector→executor split (denomination, account,
proxy path). It is one class, not one channel.

## Session death — `19` / `501` is not a channel problem

`ec=19 Failed to authenticate` on a read and `501 user auth error` on `merge_pay` mean the
cookie lost its session, not that a channel is wrong. Do not start sweeping channels: with
a dead cookie every channel returns the same auth code and the sweep teaches you nothing.

- **A session cookie that disappears from the jar after a page load was rejected by the
  server.** Snapshot `context.cookies()` before a navigation and again after; if an auth
  cookie existed and is now gone, the account is expired. No amount of re-saving that jar
  repairs it.
- **There is no refresh endpoint to fall back on.** Refresh paths return `404`; a token
  sitting in localStorage may be telemetry, not a session. Scan the stored pool for any
  jar whose auth call returns `error:0` before deciding the fleet is dead — a uniform zero
  across hundreds of jars means they expired together.
- **Re-login is the only repair, and it can be gated behind identity verification.** A
  password accepted but followed by an identity-check screen is a *credential success*
  (the login endpoint returns a verification token, not an error). If the operator's
  password keeps producing that screen, do not tell them the password is wrong — the
  device/IP needs verification through a channel they must supply.

## Trap 0 — `2021 unsupported payment channels` is a retired channel, not a payload bug

A channel id that no longer exists on the digital-product rail answers `2021` before any
price or flag is validated. Do not sweep fees or options against it — every variant
returns `2021`. Identify the channel by id, not by its marketing name.

**Indomaret `8003001` is ALIVE. `8003000` is the retired one.** Both look like the same
store; only one id exists on the rail. Never retire a channel from one failing attempt —
scan the range one id at a time, one order per id, ≥3s apart, cancelling each success:

| channel id | result on pulsa 10102 |
|---|---|
| `8003001` | ✅ Indomaret, fee 2.500 |
| `8003200` | ✅ Alfamart, fee 2.500 (payment code, no VA) |
| `8003000` `8003003` `8003005` `8003010` `8003050` `8003100` `8003101` `8003150` `8003175` `8003210` `8003220` `8003230` `8003240` `8003250` `8003260` | ⛔ `2021` |

Only `8003001` and `8003200` exist in the 8003000–8003260 band. A `2112` inside a sweep
means the previous success was not cancelled — it does not mean the channel is broken.

When a payment method starts failing with `2021` and nothing else changed, suspect a stale
`__pycache__` first (`find . -name __pycache__ -type d -exec rm -rf {} +` before restart) and
a second copy of the channel map elsewhere in the repo (`grep -rn '<channel_id>' --include='*.py' .`).
A driver that still holds the retired id reproduces `2021` no matter what the user selects.

The VA is bound to the **phone number, not the order**. Re-running for the same
number yields the same VA with a fresh `order_id`. Only SeaBank randomises; the
rest are literally `<prefix> <phone>`. Keep the whole matrix in one structure
(`BANK_OPTS = {key: {opt, label, min_denom}}`) so the fee and the flag can never
drift apart from the option code.

## Trap 1 — `2080 ORDER_PAY_PROMO_511` from the wrong fee flag

SeaBank is the only channel that is fee 0 **and** must omit `is_new_fee` entirely
(absent, not `false`). A brute-force that varies only `fee` while `is_new_fee`
stays `true` fails on **every** row including `fee=0`. The flag is the variable,
not the price. If a whole sweep returns identical `2080`, check what stayed
constant rather than widening the sweep.

## Trap 2 — BCA `error_code: 16` is a floor, not a bad parameter

`init_payment` → `"Minimum payment amount of Rp10.000,00 is required."` Note where
it lands: `merge_pay` returns `err_code: 0` **and a valid `payment_url`**, and only
after that does the VA fail to materialise. A valid payment URL is not proof a VA
exists. If `ec=16` repeats across every `option_info` and fee variant, raise the
denomination — do not keep changing parameters.

## Trap 3 — the promo pointer goes BOTH ways

Two opposite failures wear the same `2080`. Which fix applies depends on the item, not
the bank:

| item state | correct body | wrong body → result |
|---|---|---|
| `promotion_activity_id` nonzero, price sane | echo it + its `price` | `0` → `2080` |
| promo price absurd (Rp1 on a Rp10.000 item) | drop pointer + nested block | echoing it → `9012` / `2080` |

So "always zero the promo" is wrong. A live campaign must be mirrored back exactly; only
a **broken** campaign is stripped. Guard on the ratio, never on the presence of a
pointer:

```python
eff = promo_price if promo_price >= denom * 100_000 * 0.05 else discount_price
if promo_price and promo_price < denom * 100_000 * 0.05:
    item["activity_item_priority_promotion_info"] = {}
    promotion_activity_id = 0
```

Also mirror `original_discount_price` from the item's own field (falling back to
`market_price`), never from `discount_price` — copying the discounted value into the
"before" slot is an independent `2080` source. Shopee micro-units: `1_000_000` = Rp10.000
(`/100_000` to display).

## Trap 5 — `2096 place order too fast`

A sweep across banks or denominations hits this after two or three orders from one IP.
It is a throttle, not a payload defect: back off inside the same variant
(2.5s → 4.5s → 6.5s) and resubmit before mutating anything. Sweeps that report the tail
rows as failures are usually just rate-limited.

## Error-code decoder

## Trap 4 — `2112 exist_order_id` while iterating channels

One hanging order per (item + phone). The second bank in a serial loop hits `2112`.
The id is **not** in `data` — it arrives as a JSON-encoded **string inside
`err_msg`**:

```python
oid = (j.get("data") or {}).get("exist_order_id")
if not oid and "exist_order_id" in str(j.get("err_msg", "")):
    try:    oid = json.loads(j["err_msg"])["exist_order_id"]
    except Exception: oid = re.search(r'"exist_order_id"\s*:\s*"(\d+)"', j["err_msg"]).group(1)
```

Cancel (`{order_id, category_id: 10102}`) then retry — the next VA appears with
the new bank's prefix. Put this inside the order function so callers stay clean.

## Error-code decoder

| code | meaning | action |
|---|---|---|
| `90309999` | anti-fraud device token missing | request must come from warmed product-page context |
| `404` HTML body | wrong header route (`x-api-source` changed) | keep `x-api-source: 'pc'` |
| `102` | params invalid | payload shape |
| `102 API_REQUEST_INTERNAL_001` | token passed, params bad | fix payload |
| `2080` | price / promo / flag mismatch | Trap 3 (pointer), then Trap 1 (flag) |
| `2096` | placement throttled | back off and retry same body (Trap 5) |
| `2112` | hanging order | Trap 4 |
| `2021` | no / stale channel id in the payload | Trap 7 (state plumbing) first, then Trap 0 (retired id) |
| `9560` | promo already claimed by this phone number | Trap 6 — not retryable, fall back to a non-promo item |
| `4100` | purchase limit for this item/account | different denomination or account |
| `9012` | promotion detail not matched | poisoned promo, Trap 3 |
| `ec=16` on init_payment | below bank minimum | Trap 2 |
| `ec=7` on init_payment | bill-flow (PLN), no VA ever | wrong category |

Translate every code above in the user-facing error mapper. A raw
`❌ 2021 unsupported payment channels` leaves the user unable to tell "wrong channel"
from "my driver is out of date", and they will re-report the same failure.

## Trap 6 — `9560` promo limit is per phone number, not per attempt

`9560 You have reached the maximum promotion purchase limit with this phone number`
means that handset already consumed the campaign. It is **not** a throttle and **not** a
payload defect — retrying, changing bank, or backing off all return `9560` again.

One denomination maps to exactly **one** item, so a promotional denomination has no
non-promo twin to fall back to. Consequences to encode in the caller:

- Return a distinct flag (`promo_limit: True`) instead of a generic failure, so the order
  loop can look for a non-promo item of the same denomination and switch to it.
- If no non-promo sibling exists, tell the user plainly which denomination is closed for
  that number and to pick a `💰 Normal` one or another number. A retry prompt that
  cannot succeed burns the user's trust and the campaign's rate limit.
- Expose `Promo` / `Normal` filtering in the catalog UI and warn on the confirmation page
  that a promo is good for one redemption per number.

## Reading the order id out of `merge_pay`

`err_code: 0` does **not** put the id where you expect. The real shape:

```json
{"err_code":0,"data":{"order_id_list":["2793..."],"pay_order_id":"3793...",
 "payment_url":"https://shopee.co.id/payment/transaction/<tid>?...",
 "encrypt_payment_id":"","spm_order_id":""}}
```

There is **no `data.order_id`**. Reading only that yields `Order: None` in the
user-facing message while everything else worked.

```python
oid = (d.get("order_id")
       or (d.get("order_id_list") or [None])[0]
       or d.get("pay_order_id"))
```

Apply the same extraction on **every** success path — the first attempt, the
`2112` cancel-and-retry, and the `2096` backoff retry. Fixing one branch and
leaving the others is how the bug comes back a week later after a throttle.

Never render `None` to the user: `f"Order: <code>{oid or '-'}</code>"`.

The VA itself must be `<code>`-wrapped so Telegram offers press-to-copy, with both
forms — spaced (what the bank shows) and `re.sub(r"\D", "", va)` for pasting into
m-banking — plus `bank` and `receiver` when present.

## Verify before declaring it shipped

Run **all** channels through the production entry point, not a hand-rolled test
harness. Two mismatch classes only show up on the real path:

- **Page object**: the engine's browser wrapper may expose `.page` while a test
  shim exposes `.pg`. Resolve through one helper
  (`getattr(b, "pg", None) or getattr(b, "page")`) rather than either directly.
- **Return type**: callers render `va["va"]` / `va.get("amount")`. A function that
  returns a bare string raises `TypeError` at render time — after the order was
  already created.

On `init_payment`, retry across `gw1`→`gw0` and `status` `3`→`1`, and keep the last
`error_code` in module state so the caller can translate `ec=16` into a human
"this bank needs a bigger denomination" message.
