---
name: farmed-account-validation
description: Use when proving farmed accounts actually work.
version: 1.0.0
author: curator
license: MIT
metadata:
  hermes:
    tags: [farming, signup, validation, cookies, verification]
    related_skills: [browser-signup-farming, captcha-solver-api-integration, shopee-captcha-solver]
---

# Farmed Account Validation

The complement to any signup farm: the flow that decides whether an account is
REALLY created and REALLY logged in, before you report it. A farm that skips this
ships unauthenticated cookies as "success" and the user finds out later.

## When to use
- Any browser-based registration farm (see `browser-signup-farming`,
  `shopee-captcha-solver`) where the last step is "accounts created: N".
- Whenever you are about to hand account credentials + cookies to the user for
  testing.

## Rule 1 - never declare success from a cookie jar alone
A cookie jar that LOOKS complete (two dozen keys: session, device, csrf, tracking)
can still be UNAUTHENTICATED. The key that actually matters is often a SINGLE field
(e.g. an auth token / user-id cookie). Missing it, the site returns success HTML but
the session is dead.

Gate every account before reporting:
```python
# hit an AUTHENTICATED endpoint with the saved cookie
import requests
r = requests.get(API_ACCOUNT_INFO, headers={"Cookie": cookie_string}, timeout=20)
data = r.json()
assert data.get("error") == 0 and data.get("data", {}).get("userid"), "NOT authenticated"
```
Common failure shape even with 24+ cookie keys present:
`200 {"data":null,"error":19,"error_msg":"Failed to authenticate"}`.
Cause: cookies were saved before the site set the real auth cookie (session captured
mid-flow, not after a full login).

**Cheap pre-check before you even hit the API:** the auth cookie usually announces
itself in the jar's size and field set. Compare a known-good jar against a suspect one:
authenticated = longer and contains the session/user-id fields (e.g. Shopee: ~1869+
chars, includes `SPC_U` + `SPC_ST`); unauthenticated = shorter (~1500), missing those
auth fields even though the tracking/device/csrf keys are all present. Gate the save
on those auth fields EXISTING in `context.cookies()` before writing the account record;
do not save a jar that lacks them and hope the API accepts it.

**Fix, not a re-parse:** if unauthenticated, do a real LOGIN inside the SAME browser
context (cookies auto-attach via `page.evaluate` fetch) and re-read cookies after.
Hand-parsing the jar to "add the missing field" usually writes a wrong value.

**BUT a re-login only repairs the "captured too early" class — it CANNOT repair a
registration that never completed.** Distinguish the two before spending attempts:
- `error:19` WITH the auth fields PRESENT in the jar = session captured mid-flow →
  re-login repairs it.
- `error:19` with the auth fields ABSENT (Shopee: no `SPC_U`, no `SPC_ST`, `user_id`
  empty) = the signup never reached the login/verify step, so the password was never
  SET. Logging in with the stored password fails and just stays on the login page →
  the account is unrecoverable, not repairable. Classify it DEAD and drop it; the
  durable fix is completing the register flow (Rule 4), not repeated login attempts.

## Rule 1b — classify into three states, not two

A binary valid/invalid hides the repairable middle. Score every account:
- **READY** — auth fields present AND an authenticated endpoint returns `error:0` + id.
  Only these go in the saleable pool.
- **REPAIR** — cookie present, auth fields present, API auth fails → re-login candidate.
- **DEAD** — auth fields absent / no cookie / signup aborted → discard.

Run this as a standalone validator that reads the account store, writes back the
resolved `user_id` + a `status`/`status_msg` per record, and emits a summary + a
`*_status.json`. Schedule it on cron (e.g. twice a day) so a stored pool cannot silently
rot, and diff the READY count across runs to catch a systematic extraction regression
early instead of discovering it at delivery time.

**Gate the SUCCESS REPORT on READY, not on "cookie exists".** The same check the
validator makes must run in the farm's own completion handler before it announces
success — a bot that prints "berhasil" for a jar without the auth fields is lying to
the operator and pollutes the pool. Only mark/announce success when auth fields are
present AND the API authenticates; otherwise report a distinct "not finalized" state.

## Rule 2 - a visible validation rule is a SERVER rule until proven otherwise
When a signup form shows a red X next to a password/field rule (e.g. "needs one
uppercase char"), that is usually NOT just a frontend pre-check. Bypassing the client
- inject value via the native `HTMLInputElement` value setter, hide the error text,
force-enable the disabled submit, click it - DOES fire the request, but the server
re-validates and bounces the form back to the same step. You will see: submit "clicked",
page does not advance, cookies stay unauthenticated.

Correct move: read the rule off the page and SATISFY it. If it demands one uppercase
char and the user wants lowercase-only, that requirement is server-side and unbypassable
client-side - report it as a hard constraint and supply a compliant value. Do not spend
attempts (rate limits on OTP/signup are real, ~5-6/number) fighting a server rule.

## Rule 3 - how to hand results to the user
- Dump one JSON record per account: username, password, phone, userid, fingerprint,
  device id, cookie string.
- State the VALIDATED auth status per account (error code from Rule 1), not just
  "created".
- If cookie is long, send as a file, not an inline message.
- Never present an unvalidated cookie as working.

## Rule 4 - a "filled" field is not a "submitted" form
A fill step (password/OTP) can log success (e.g. `fill_password {"ok": True}`) while
the page stays on the SAME step. That means the form never submitted - filling is a
no-op without a submit action. Always, after filling, click the real submit button
(and `keyboard.press('Enter')` as fallback), then WAIT for the state to advance to
the next step. Diagnose a stuck account by the state value, not the fill return code:
`STATE final: PASSWORD` after repeated ok-fills = missing submit click, and the
resulting cookie is unauthenticated (Rule 1).

## Rule 5 - authenticate before extracting identity fields
When the post-signup extraction reads `userid`/`username` via an authenticated API,
an empty `userid` alongside a present cookie is the SAME unauth signal as Rule 1
(`error:19`). Do the authenticated identity fetch in the SAME browser context that
holds the live session (browser fetch attaches cookies), not from a saved jar.

## Rule 7 — validate the PROXY like the browser will use it, not like curl

A proxy that answers `curl`/`requests` fast can be useless to a real browser, and this
looks identical to a dead target. Gate the proxy pool BEFORE spending signup attempts:
- **CONNECT(443) support.** Public HTTP proxies that cannot tunnel TLS make Chromium
  return `net::ERR_TIMED_OUT` on the first `page.goto`, not a captcha. Probe with a raw
  socket `CONNECT host:443` and keep only `200` responders.
- **Chromium render, not HTTP status.** A datacenter proxy can return `200` to `requests`
  on the signup URL while Chromium renders an EMPTY body: the HTML shell loads but the
  app's CDN JS bundle (a different host) times out (`requestfailed` on `*.cdn-host`).
  Read `page.evaluate('()=>document.body.innerText')` — an empty body = proxy quality, not
  a solved gate. Never conclude "site blocks us" from an HTTP 200 alone.

## Rule 6 — an overlay can swallow the submit click (looks like "login failed")

A login/submit that fills both fields, clicks the button, and STAYS on the same page
with no error text is often not a bad credential — the button was never actually
clicked. React anti-bot pages render a decorative image/overlay div that the click's
hit-test lands on, and Playwright retries the click forever (log shows "element is
visible, enabled and stable" then "<img …> from <div class=…> subtree intercepts pointer
events"). Fix: click with `force=True`, and if that still bounces, dispatch the click
via `page.evaluate` on the matched button (`[...document.querySelectorAll('button')]
.find(b=>/log ?in|masuk/i.test(b.innerText)).click()`). A second variant of the same
symptom: the input selectors are `name`-less — match the fields by PLACEHOLDER
(`input[placeholder*='Handphone']`, `input[placeholder='Password']`), and WAIT for them
to mount (poll up to ~40s) before filling, since a captcha/language gate can render first.

### Pitfalls
- **Saving cookies too early.** Capture the jar AFTER the step that returns the auth
  cookie (post-login / post-OTP-verify success state), not right after form submit.
- **Trusting a success page text.** Detect success by the presence of the auth cookie /
  authenticated-API `error:0`, not by body copy.
- **Reusing one browser context across accounts.** Cookies bleed; open a fresh context
  per account or you validate the previous account's session.
- **A post-submit confirm modal is not a failed login.** A same-page modal ("Tetap Login"
  / "Stay logged in?") left unclicked looks identical to a credential rejection. Click the
  modal's confirm with `force=True`, then re-read the auth cookie. Only a page that never
  leaves the login state even after the confirm is a real bad credential.
