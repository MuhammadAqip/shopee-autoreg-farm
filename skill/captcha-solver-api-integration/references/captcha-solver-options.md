# Captcha Solver Options — Free & Paid (no-VCC first)

Landscape for solving the signup captcha (reCAPTCHA v2/v3, Turnstile, image) when
mass-farming. Prefer free tiers; only pay when a paid key is already on hand.

## Free tiers that do NOT require a credit card

- **NopeCHA** — 100 free credits/day per IP (= ~100 reCAPTCHA solves/day), no signup
  required for the browser extensions and the **Recognition API**; the **Token API**
  (what reCAPTCHA/Turnstile token farming needs) requires an API key.
  - Free credits are **refused from high-risk IPs (VPN / datacenter proxies)** — must
    originate from a real residential IP, so a proxied farm cannot use them.
  - Key surface: `nopecha.com/manage` (Sign in → "Active – API key" + "Available
    credits" + "Next refill in"). Register/login at `/register` `/login` (JS-rendered
    SPA — read via a real browser, raw HTML has no form fields).
- **CapMonster / CapSolver** — small signup trial credits; CapSolver also documents a
  free reCAPTCHA-v2 endpoint. Trial sizes change; verify on the pricing page.

## Paid (per-1000 solves) — when already available

- **2captcha** `POST http://2captcha.com/in.php` (`method=userrecaptcha&googlekey=&pageurl=&json=1`)
  → poll `res.php?action=get&id=` until `status:1` (retry while `CAPCHA_NOT_READY`).
- **CapSolver** `POST https://api.capsolver.com/createTask`
  `{"task":{"type":"ReCaptchaV2TaskProxyLess","websiteURL":...,"websiteKey":...}}`
  → poll `getTaskResult` until `status:ready`, token at `solution.gRecaptchaResponse`.
- **peak.fo** — Turnstile: `POST https://api.peak.fo/solve` Bearer `pk_...`
  `{"task_type":"turnstiletaskproxyless",...}`. Returns `Blocked sitekey` when the
  site opted out of automated solving (dead end).

Both 2captcha & CapSolver clients share the same shape: submit → poll → token string.
Budget a ~5s poll interval and ~40 polls before declaring timeout. reCAPTCHA v2 sitekey
+ pageurl are the two inputs; the token goes into the form field `g-recaptcha-response`.

## Economics of farming the solver's own free tier

Some solver products (SadCaptcha) grant **25 free credits per new account**. Farming
N accounts of the solver itself yields 25·N credits for the downstream farm, and the
per-solve cost is only the reCAPTCHA solve of the solver's OWN signup (often a free
daily allowance). Do the arithmetic before paying: 40 solver accounts cleared with a
cheap/free reCAPTCHA solve ≈ 1000 downstream credits.

## Manual-solve fallback (zero cost, when no solver is wired)

When no solver key exists, run the flow interactively: the agent prints the signup URL
+ the generated email/password, the human solves the widget, and hands back the token.
Hand off via file so the agent stays unblocked:
```python
# agent side: poll a token file while the human solves
while time.time() - t0 < 900:
    if os.path.exists('.token_input'):
        tok = open('.token_input').read().strip()
        if tok and len(tok) > 50: break
    time.sleep(3)
```
Human side: solve the widget, then `grecaptcha.getResponse()` in the browser console
→ `echo 'TOKEN' > .token_input`. Then POST the form with `g-recaptcha-response=<tok>`.
Slow (one human action per account) but it proves the whole pipeline end-to-end before
any solver spend.
