---
name: browser-pool-concurrency
description: Use when scaling headless browser automation.
version: 1.0.0
author: curator
license: MIT
metadata:
  hermes:
    tags: [playwright, concurrency, async, proxy, tor, automation]
    related_skills: [transacting-api-automation, spa-api-recon, shopee-antifraud-reversing]
---

# Browser Pool Concurrency

Driving a headless browser against N accounts/targets where each request must run
INSIDE a page context (see `transacting-api-automation` Rule 1) — the concurrency +
routing layer: how to parallelise, where the ceiling is, how to route the browser
through a proxy.

## When to use

- A signed/anti-fraud endpoint forces `page.evaluate` fetch, and you must run it
  across hundreds-to-thousands of accounts.
- You are choosing between relaunching a browser per item, one persistent browser,
  or a pool — and picking thread vs async.
- You are wiring the browser through a proxy (SOCKS/Tor/mitm) for anonymity or geo.

## Rule 1 — the sync playwright API is NOT thread-safe

Driving `sync_playwright` from several threads makes every call fail with `error` /
EPIPE (`write EPIPE` in the node driver) while a single-thread serial loop over the
same accounts succeeds. Symptom pattern: serial = 3/3 OK, 5 threads = 0/30 all
`error`. The sync API is bound to one thread; parallelism through threads is not
possible.

**Do not chase this as a per-account problem** (cookie expiry, rate limit, device
fingerprint) — if serial works and parallel does not, it is the API's threading
model. Switch to async.

## Rule 2 — parallel tabs = `playwright.async_api` + asyncio.gather

Multi-tab/multi-account concurrency uses one event loop:

```python
from playwright.async_api import async_playwright
import asyncio

async def run(cookies, n_tabs):
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
    pages = []
    for _ in range(n_tabs):
        ctx = await browser.new_context(user_agent=UA)
        pages.append(await ctx.new_page())
    q = asyncio.Queue()
    for ck in cookies: q.put_nowait(ck)
    async def worker(pg):
        while True:
            try: ck = q.get_nowait()
            except asyncio.QueueEmpty: return
            await pg.context.clear_cookies()
            await pg.context.add_cookies(cookies_from_str(ck))
            await pg.goto(WARMUP_URL, wait_until="domcontentloaded")
            await pg.evaluate(JS, body)
    await asyncio.gather(*[worker(p) for p in pages])
    await browser.close(); await pw.stop()
```

Each `new_context()` is an isolated cookie jar — one context per worker, so cookie
swaps never cross-contaminate. **1 tab = 1 context, always.** See Rule 2b.
A sync wrapper for a threaded bot is
`asyncio.run(run(...))`, but the wrapper itself must be called from ONE thread.

## Rule 2b — one context per page: never share a context across workers to save RAM

Sharing a single context across the pages of one browser ("fewer contexts = less
memory") makes every worker write into the SAME cookie jar: `add_cookies` from
worker A is overwritten by worker B mid-flight. Symptom: results come back with the
WRONG account identity attached — the same username repeated N times, fewer distinct
accounts out than in. This is a race, not a memory win. Each worker/page gets its own
`new_context()` even when they live in the same browser process.

**Tell:** output has duplicate identities / `len(set(names)) < len(names)`. Fix by
restoring `new_context()` per tab (and `clear_cookies()` before `add_cookies()`).

## Rule 2c — a hard concurrency cap: worker count ≠ parallel request count

The number of live pages (workers) and the number of in-flight server requests are
DIFFERENT knobs. Spinning up 30-64 workers against one exit IP fires that many
requests at once, the server rate-limits the IP, and accounts come back EMPTY —
faster wall-clock, zero data. Gate the actual request with a semaphore, keep the
pool large:

```python
sem = asyncio.Semaphore(9)          # in-flight requests, tune per server
async def worker(pg):
    while True:
        try: item = q.get_nowait()
        except asyncio.QueueEmpty: return
        async with sem:
            r = await one(pg, item)
            await asyncio.sleep(0.12)   # small gap between requests
```

Measure the ceiling with a sweep (e.g. 3 / 9 / 16 / 30 workers, count total records
returned, not just wall-clock): a server that throttles per-IP shows records DROPPING
to zero as workers rise, while a legit-fast server holds them constant. Same signature
as Rule 3 (more tabs behind one exit = slower) but the fix here is a semaphore rather
than more exits — use the semaphore when the limiter is per-IP request-rate, use extra
exits when it is per-connection/bandwidth.

## Rule 2e — a rate-limited (partial) result must be REPORTED, never rendered as empty

When the semaphore (Rule 2c) is not enough and a server still rate-limits the IP, a
worker can return a genuinely THIN result for one item — fewer records than a healthy
item yields (e.g. 0-12 instead of the normal 70-100). If you render that as
"no data / empty", the user reads a FALSE NEGATIVE and re-checks accounts forever.
Tag the result and surface it:

- **Detect the throttle from a SERVER SIGNAL, not a guessed record count.** The best
  tell is an API error code in the RESPONSE BODY while HTTP stays `200` — the server
  replies `{"data":null,"error":<rate-limit-code>}` instead of counting the
  request as failed. Capture the body `error` per sub-request and set
  `throttled = any_error_hit` (or `throttle_hits > 0`). A thin count (`n < threshold`)
  is a LAST-RESORT heuristic only: a genuinely empty/new item also returns a small
  count, so counting alone both false-positives (new item flagged throttled) and
  false-negatives (a throttled item that still returned its baseline of unrelated
  records). Prefer the error code; fall back to a count strictly ABOVE zero healthy
  items' baseline.
- When a thin result is also empty of the target, print an explicit throttle notice
  ("⚠️ rate-limited — result may be a false blank, re-check this item"), NOT the
  same "— none" line used for a verified-empty item. Distinguish three states:
  has-data / verified-empty / throttled-empty.
- Add a run-level summary when any item is flagged ("⚠️ N items rate-limited") so the
  user sees the batch is partially unreliable without opening each item.

This is a user-facing correctness rule, not cosmetic: conflating throttled-empty with
verified-empty destroys trust in the whole tool. The dangerous cell is "flagged AND
empty" — report it loudly.

## Rule 2f — return one result per input, keyed by a fetched identity (never by list index)

A batch tool must return exactly N results for N inputs, and the identity attached to
each result must be READ FROM THE SERVER, not inferred from input order.

- **Do not assume the input list order matches the identity order.** A cookie file's
  line order is NOT the account order (cookie 5 is not account 5). If you report
  "account X is empty" from a position index, you are reporting on the WRONG account —
  and the wrong diagnosis reads exactly like a real one. Fetch the real identity per item
  (a lightweight signed `get_account_info`, run in parallel with the main call).
- **Preserve input order in the output** (`results[i] = ...` per input index) but attach
  the FETCHED identity to each result; sort/emit by the fetched identity for a clean list.
- Sanity check: `len(results) == len(inputs)` and `len(set(ids)) == len(ids)` unless
  duplicates are genuinely expected. A duplicate identity is the Rule 2b/2f tell.

Downstream: any "X is empty" claim must be re-checked against that item's OWN fetched
identity — an index bug manufactures false negatives indistinguishable from real ones
(Rule 2e).

## Rule 2d — a freshly warmed page is not accurate on its first run

A page that was just launched/warmed returns INCOMPLETE results for its first pass
(e.g. run1 = 0 records, run2 = few, run3 = full). The signing SDK / session needs a
beat to settle after the warm `goto`. Do not read run-1 output as ground truth, and
do not "fix" the parser because the first post-warm run came back empty — re-run once
or twice before diagnosing. Warm the pool at startup (Rule 3d) so real requests never
hit a cold page.

## Rule 3 — a single proxy exit is the real ceiling

With one exit IP (one Tor SOCKS circuit, one proxy line), throughput saturates long
before CPU/RAM do, and MORE workers makes it SLOWER: 25 workers (5×5) ran ~3× slower
than 8 (1×8). The exit serialises (and under Tor, resets) the parallel requests.

- Measure the sweet spot per exit; a single Tor circuit lands around one browser ×
  8 tabs (~0.9 acct/s on a lightweight signed call).
- Scale wider ONLY by adding distinct exit IPs (a pool of SOCKS endpoints), not by
  adding tabs behind the same exit. To get several isolated exits from ONE Tor daemon
  (no second proxy line), see `references/multi-exit-socks.md`.
- Before spending on a proxy pool, check WHERE the limiter sits: if the server throttles
  PER ACCOUNT (a flat ~1s round-trip per account regardless of IP), more exits change
  nothing — the ceiling is the account rate, not the exit. Measure a 2-config sweep
  (e.g. 1×8 vs 5×5) before scaling infrastructure.
- Retry the transient `err=error` twice with a ~1.5s pause — it is exit saturation,
  not a dead cookie. Do not discard the account.

## Rule 3b — drop the per-account reload: warm up once, then swap only cookies

After the first warm-up `goto` (which loads the signing SDK into the page), a
cookie swap does NOT need a `page.goto` per account. `clear_cookies` +
`add_cookies` + `page.evaluate(fetch)` succeeds and runs ~10×+ faster than
reloading.

```python
# once, per page/context
await page.goto(WARMUP_URL, wait_until="domcontentloaded")
# per account — NO goto here
await page.context.clear_cookies()
await page.context.add_cookies(cookies_from_str(ck))
res = await page.evaluate(JS, body)
```

The SDK/anti-fraud interceptor does not re-bind to the session cookie on the client,
so it keeps signing after the swap — only the browser needs to have had the page
loaded once. Measured: with goto ~0.8-1.5s/account, without it the fetch itself is the
whole cost. **Try no-goto first**; only re-add `goto` if a fetch comes back 403/`error`.
This is compatible with the empty-fingerprint rule (`transacting-api-automation`
Rule 5) — same transport, just no reload.

## Rule 3c — batch sub-queries inside ONE page.evaluate, SEQUENTIALLY (parallel can false-empty)

When one account needs SEVERAL signed lookups (e.g. every `*_list_type` bucket of a
typed list), do them in ONE `page.evaluate` rather than looping from Python — but run
them as a **sequential `for` loop with a small inter-request delay**, not `Promise.all`.
A parallel fan-out over sub-queries on a session-keyed limiter can return `err=0` +
empty for the bucket that fires last (Rule 2i); the sequential version returns every
bucket. One `evaluate` round-trip either way, so sequential adds ~one small delay per
bucket and buys correctness.

```js
async (typesJson) => {
  const types = JSON.parse(typesJson);
  const csrf = (document.cookie.match(/csrftoken=([^;]+)/)||[])[1]||'';
  const out = {};
  for (const t of types) {
    const r = await fetch(URL, {method:'POST', credentials:'include',
      headers:{'Content-Type':'application/json','x-csrftoken':csrf,'x-api-source':'pc'},
      body: JSON.stringify({type:t, /* ... */})});
    out[String(t)] = await r.text();
    await new Promise(res => setTimeout(res, 120));   // inter-type gap
  }
  return out;
}
```

**Narrowing the variant list to the ones that carry data is also the first line of
defense against the over-farm risk flag (Rule 2h) — request VOLUME, not worker count,
is what flips server-side flags.** Scanning every bucket of every account multiplies
request count ~8x for zero data when most buckets are permanently empty.

Reach for `Promise.all` in the batch ONLY after a sequential run confirms the buckets
populate identically in parallel; on a limiter that counts concurrent sub-requests, the
bucket that fires last in the parallel fan-out trips it and comes back `err=0` + empty
(Rule 2i). Default = sequential.

## Rule 2i — a parallel sub-query fan-out can return `err=0` + empty for the LAST bucket; re-run it SEQUENTIALLY

Distinct from Rule 2h (dead signer: 100% of items blank, instantly, fix = unblock
scripts). This one is the SAME account, SAME warm page, SAME signer ALIVE: a bucket
that reads empty inside `Promise.all([...buckets])` returns its full list when fetched
SEQUENTIALLY with a short `await sleep(...)` between buckets.

Mechanism: the limiter counts CONCURRENT sub-requests on one session, not the number of
buckets; the bucket that fires last in the parallel fan-out trips it and gets `err=0` +
empty — a silent 200, no throttle code. Diagnostics that, in sequence, pinned it:

1. Same cookie, fetch ONLY that bucket (single request, nothing parallel) → full list.
   (Rules out cookie/fingerprint/account.)
2. Same cookie, fetch ALL buckets via `Promise.all` → the last bucket comes back 0.
3. Same cookie, fetch buckets in a serial `for` loop (~120ms delay) → ALL buckets
   return their lists, the previously-empty one included.

Rule: when the payload needs more than one signed sub-request per session, default to
SEQUENTIAL loops with a small delay; reach for `Promise.all` only after verifying it
silences no bucket. A per-bucket `err=0` empty is NOT proof of an empty bucket — it
needs the sequential re-check before you render it (see Rule 2e).

## Rule 2j — the residual: a per-account bucket that is blank across every variant

After ruling out the dead signer (2h) and the parallel fan-out (2i), a remaining
`err=0` + empty bucket looks like a genuine PER-ACCOUNT server state. Before concluding
that, exhaust the TIME axis: re-test the item alone on a warm page after a real pause
(tens of seconds), ideally on a fresh page/context. An IP-level limiter answers
`err=0`+empty during its cool-down and returns FULL data once it drains — so a bucket
that is blank now can be full a minute later for the SAME account+cookie. If it does
recover, the residual was throttling on the time axis, not a wall (handle via Rule 2g's
bounded pass-2).

Only after a paused, isolated re-test STILL returns `err=0`+empty while a
human-confirmed browser view shows data should you treat it as withheld server-side for
that account+route. Then the answer is a DIFFERENT data route/source — and you must not
promise one exists until you have its request. Ask the user for a capture (HTML export /
HAR) from the tool or browser view that DOES show the data, and diff its request against
yours — endpoint, path segment, extra body field, device header. Until that diff exists,
the honest state is "this account's data is not exposed on the route we can reach" —
never render it as a confident blank (Rule 2e), and do not write up dead-end probing as a
working method.

## Rule 2g — PASS-2 recovery: re-run thin/empty items SEQUENTIALLY with backoff

After the parallel gather, re-run items flagged thin (Rule 2e) or still missing their
target data ONE AT A TIME on a single page, rising inter-item delay (2s, 6s, 10s),
up to 3 rounds. Parallel recovery fires the same burst that caused the throttling
and recovers nothing; sequential + backoff lets the per-IP limiter drain between
attempts. Still missing after the last round → report per the item's server signal
(Rule 2e/2h), do not retry forever.

**BOUND the recovery or the whole job hangs before it ships.** An unbounded pass-2
(3 rounds × rising backoff × every failing item) put a 30-item job past 10 minutes and
the user walked away before any result was rendered — the checker LOOKED dead. Cap it:

- **Recover only the ITEMS THAT FAILED, and cap the set** (e.g. at most ~10 items per
  run) rather than re-running the whole batch.
- **One recovery round by default, not three** — with a raised per-item timeout if the
  backoff is long. If a single pass-2 does not recover an item, report it (Rule 2e) and
  move on; a second/third round rarely recovers more than the first when the cause is an
  IP cool-down (it needs TIME, not retries-in-a-burst).
- **Keep pass-1 CHEAP (`retries=0` per item).** Having the per-item call retry with a
  long backoff INSIDE the parallel pass-1 multiplies the backoff across every item —
  the batch takes items × backoff. Do the cheap pass-1 fast, let the sequential pass-2
  own the delay.
- **Raise the pool submit timeout when backoff is long.** With recovery in the tens of
  seconds, a default `submit(coro, timeout=600)` raises `TimeoutError` on a modest batch
  even though the work is fine — set the pool's default timeout high (e.g. 2400s) so the
  backoff has room.
- **Render SOMETHING early.** Send a header/progress message (or stream partial results)
  before the recovery pass completes, so a slow job never reads as a hang.

## Rule 2h — `err=0` + empty + full data elsewhere = the SIGNER IS DEAD, not throttling (check resource blocking FIRST)

When a batch returns `err=0` with an EMPTY sensitive bucket for most items — while a
few items return full data, and the same item returns full data when you query it
from a page whose JS actually ran — the cause is almost always that the **in-page
signing SDK never loaded**, so every fetch went out UNSIGNED and the server answered
`err=0` with an empty list (a silent 200-body no-op, NOT a `403` and NOT a
rate-limit code). Do this before blaming risk flags, IP reputation, or account heat:

1. **Audit every `route.abort()` / resource-block rule.** Blocking `resource_type`
   `script` (a common "save RAM" optimisation) kills the anti-fraud signer. Block by
   resource type ONLY for `image`/`media`/`font`; **never** abort `script` or
   `stylesheet` when the page must sign requests — the SDK must execute.
2. **Warm on a page that actually loads.** If a specific route returns an app error
   page ("Halaman Tidak Tersedia"/"Page Unavailable") from your exit IP, the warm
   loads nothing and the SDK is absent. Warm on the plain homepage instead — it is
   enough to boot the signer; a heavier route being a little slow is irrelevant.
3. **Verify with an interceptor, not a guess.** Hook `page.on("response")` OR wrap
   `window.fetch`/`XMLHttpRequest` in an `add_init_script` and confirm the SIGNED list
   request actually fires and returns `200` + a non-empty body. Zero captured
   voucher requests = the page's JS never ran the call.
4. **Confirm the fix on the previously-blank item**: same cookie via
   `page.evaluate(fetch)` from a page with the SDK alive returns the full list.

A genuine over-farm/risk flag (below) still exists, but it is the rarer cause. The
tell that it is a DEAD SIGNER and not a risk flag: **it is 100% of items, instantly,
and a page-context fetch with a live SDK returns data for the same item.** Only
after ruling out resource-blocking (steps 1-3) should you escalate to the risk-flag
narrative below.

## Rule 3d — pre-warm the pool at startup; a request must never pay launch cost

When the same browser pool serves a long-lived bot/daemon, launch the browsers ONCE at
startup (and on config change), never per request. First-launch cost is ~5-7s per
browser; paying it inside the first user request makes the tool feel broken.

- Launch from the bot's `__main__` on a background thread so startup polling is not blocked.
- **Warm exactly the configured count at startup — never hardcode a smaller cap**
  (`nb = min(setting, 1)`). A hardcoded startup cap silently throws away the user's
  workers (the UI says 3×3 but boot only warms 1×3), which reads to the user as "the
  bot got slower" / "it only checks slowly" while the bug is in the boot routine, not
  the engine. Warm what the user configured.
- On a config change (e.g. browsers 1→3), launch the NEW browsers immediately (trigger a
  re-warm), so the next request finds them already alive.
- NEVER close the browsers after a request — keep them warm for the next one. Closing
  throws away the loaded signing SDK and re-pays launch + warm-up.
- **A re-warm must shrink as well as grow.** When the config goes DOWN (browsers 3→1,
  tabs 8→3) the surplus browsers/contexts must be closed, not left alive — otherwise
  zombies accumulate on every change and eventually OOM the host. Match the pool to the
  config in both directions.
- Verify: `pgrep -c chrome` is already > 0 right after bot start, and the first vs second
  request take the same time (proof there is no relaunch).
- **Notify the user when a warm/re-warm finishes** ("🔧 Browser siap — 3 browser × 8 tab,
  6 dtk") and send a "⏳ Menyiapkan..." line the moment a config change triggers a
  re-warm. A 5-7s silent pause after tapping a setting reads as a hang; the two-line
  ack makes the delay legible and tells the user when the pool is ready to take work.

### Pool that owns its own event loop (bridge sync bot → async browsers)

Playwright objects are bound to ONE event loop, and a sync bot runs in none. Give the
pool its own loop on a background thread and submit coroutines into it:

```python
class BrowserPool:
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._run, daemon=True).start()
        self.browsers = []
    def _run(self):
        asyncio.set_event_loop(self._loop); self._loop.run_forever()
    def submit(self, coro, timeout=600):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)
```

**Do NOT launch a fresh `asyncio.run(...)` for a coroutine that reuses pool browsers** —
the browsers live on the pool's loop; a new loop cannot drive them (symptom: `write EPIPE`
from the node driver, or an event-loop-closed `RuntimeError` on teardown).

**Deadlock pitfall:** calling `pool.warm()` (which does `submit(...)` into the pool loop)
FROM INSIDE a coroutine already running on that pool loop blocks the loop on itself →
hang/TimeoutError. Inside pool coroutines, call the internal coroutine directly
(`await pool._do_warm(...)`), never the `submit`-wrapping public method. Make warm
idempotent so it can be awaited safely at the top of every request coroutine.

## Rule 3e — key the pool by LAUNCH SIGNATURE when the proxy is a launch-time arg

When the browser wrapper bakes the proxy into `pw.chromium.launch(proxy=...)` (Playwright
cannot authenticate a proxy at the context level — see Pitfalls), a warm browser is
**proxy-locked**: you cannot hand it a different proxy per request. The pool must
therefore be **keyed by the frozen launch kwargs** (incl. proxy), handing the same
browser (many concurrent contexts) only to callers with an identical signature. Distinct
proxies get their own pooled browser; past a per-signature cap, fall back to ephemeral.

- Pool the Chromium **process**; create a **context per request** — process launch is the
expensive part (~300-800 ms cold), `new_context()` is cheap. Independent confirmation: a
reference solver does exactly `browser.new_context()` per solve with the browser pooled
at startup. One warm browser then serves all no-proxy types (they share a signature).
- Implement it by **monkeypatching the wrapper's `launch_async`** behind a handle facade
  (`_Handle` miming the browser interface: `new_page()`, context tracking, `__aexit__`
  returns the browser to the pool instead of killing it) rather than editing N launch
  sites. Minimal diff; every call site gets pooling for free. Give it a kill-switch env
  (`POOL=0`).
- Two DIFFERENT backpressure modes for two DIFFERENT call paths:
  - **Sync path** (`POST /solve`): a semaphore with a bounded wait, then **HTTP 429**
    (`server busy — N in flight`). The caller can see it and retry.
  - **Async/job path**: the job already returned a `job_id`, so **queue-wait** instead of
    429 — the client polls; a 429 there would just lose the job.
- Verify per-signature pooling with a counter: `cold_starts` vs `warm_reuses` on a stats
  endpoint. `cold_starts:1, warm_reuses:4` across 5 different type solves = working.

### systemd drop-in ordering (bites every test override)

systemd applies drop-ins in **lexical order, later wins**. A `pool-test.conf` (dash,
0x2d) sorts BEFORE `pool.conf` (dot, 0x2e), so a test override is **silently
overridden** by the production file — the override appears to do nothing. Name test
overrides `zz-*.conf` so they sort last and win. (OpenSSH has the mirror-image trap:
first-match-wins, so a hardening drop-in must be named `00-*.conf`.) Failure signature: a
value you set in a test drop-in never takes effect and `systemctl show <svc> -p
Environment` looks correct for the OTHER file.

## Rule 4 — per-browser SOCKS proxy beats system-wide transparent routing

For headless streaming, point the browser at an explicit SOCKS proxy:
`launch(proxy={"server":"socks5://127.0.0.1:9050"})`. This is stable and keeps the
rest of the host (the bot's own API traffic, SSH) OFF the proxy.

A system-wide iptables→Tor transparent setup (e.g. PrivacyNet `-l`) is fragile for
this: the page loads but the in-page SDK fetch then fails, because the browser's
direct + SOCKS traffic is force-routed and breaks. Keep system-wide routing OFF while
a browser SOCKS proxy is active, or the browser is double-routed.

## Rule 4b — a proxy you can reach is NOT a proxy the browser can use; health-check with a real page load

`curl -x <proxy> https://target/` returning `200` does NOT mean the browser can drive
it. A heavy SPA loads dozens of CDN bundles; a proxy that answers a single `curl`
request in 10s+ will blow past `page.goto`'s timeout mid-bundle and fail the whole run.
Two false signals to distrust:

- **curl-OK / goto-TIMEOUT.** The proxy forwards one request fine but cannot sustain a
  full page load. Symptom: `curl` says `http_code=200`, then `page.goto: Timeout
  90000ms exceeded` from the browser through the same proxy.
- **A dead-to-curl proxy that the browser "connects" through.** Partial/degraded proxies
  can let `goto` return while every subsequent signed fetch silently fails — the run
  prints "proxy OK" then produces empty results. Never trust a "connected" banner as
  proof the proxy is usable; trust the RESULT payload.

**Health-check = drive the real, heavy page through each proxy, not curl:**

```python
pg.goto("https://target/heavy-route", timeout=12000, wait_until="domcontentloaded")
```

Iterate the candidate pool, keep only proxies that load the heavy route, write survivors
to a file. The runner then READS that file (never a hardcoded list), so a live run
cannot burn attempts on proxies that died since the last check.

**A proxy pool decays within HOURS.** A proxy measured at 2.4s at 14:00 can be a 90s
timeout by 21:00. Re-run the picker immediately before any live run; do not bake the
survivor list into the script once and reuse it for days. Give the runner a minimal
hardcoded fallback for when the pool file is missing/empty.

**Raise `page.goto` timeout generously (~90s) for proxied loads.** A too-tight timeout
(35s) false-fails a slow-but-alive proxy and drops you to the next candidate — which
may be worse. Distinguish "slow but working" from "dead" by timeout, not by first
attempt.

## Rule 4c — a per-ACCOUNT write-throttle looks like a per-PAYLOAD bug; check read-vs-write asymmetry first

When every WRITE call (create/pay/submit) fails with the same non-parameter error code
while every READ call (account info, list, detail) returns `err_code:0`, the account is
being throttled for write VOLUME — not a malformed body. The asymmetry is the tell:
wrong params return param-specific codes (`102`/`2080`/`2412`), a throttle returns ONE
generic code across every variant, including ones that worked earlier.

- **Do not re-run the same job to "try again."** Each run mints more dangling server
  sessions, deepening the throttle and burning the exit IP further. A job that produced
  8 clean results once and empty results on the next run is throttled, not broken.
- **Recovery, cheapest first:** (1) cool down for hours; (2) a fresh, unburned exit IP;
  (3) a fresh account+cookie. Session-reuse endpoints (act on an EXISTING session id)
  sidestep the throttle because they create no new session — prefer them while
  throttled.
- **Verify auth BEFORE blaming cookies:** a healthy read (`is_login:true` / account info
  returns `err_code:0`) proves the cookie is alive; combine with a blocked write to
  confirm throttle rather than expiry.
- **Batch jobs must clean up dangling sessions, not just their visible rows.** A cancel
  loop that cancels the user-facing record but leaves the minted session burns the
  account on every batch — the block reproduces itself.

## Pitfalls

- **Shared context across pages = duplicate/wrong identities.** One context per page,
  always; never "optimise" by sharing a cookie jar between workers (Rule 2b).
- **Worker count and in-flight request count are separate knobs.** A big pool behind
  one IP needs a semaphore, or the server rate-limits it to empty results (Rule 2c).
- **A hardcoded startup cap hides the user's setting.** Warm the configured count at
  boot, never `min(setting, small)`; and shrink the pool when the config shrinks.
- **Serial-works/parallel-fails is a threading-model tell, not a target tell** — go
  straight to async, do not debug per-account.
- **More tabs behind one exit is a slowdown, not a speedup** — add exits, not tabs,
  to scale.
- **`launch(proxy=...)` cannot authenticate a proxy** (`ERR_PROXY_AUTH_UNSUPPORTED`);
  run a local relay and point the browser at `127.0.0.1:<port>` for authed proxies.
- **Launch the browser once and swap cookies** — relaunching per account costs ~10s
  and leaks RAM; one persistent browser is ~2s/account.
- **Never abort `script`/`stylesheet` resources when the page must SIGN requests.**
  Blocking scripts stops the anti-fraud SDK from loading; every in-page fetch then
  goes out unsigned and the API silently returns `err=0` + empty for everything —
  indistinguishable at a glance from throttling or a risk flag. Block only
  `image`/`media`/`font` (Rule 2h). Warm on the homepage if the target route errors
  from your exit IP.
- **A `Promise.all` fan-out over sub-queries can silence the last bucket.** `err=0` +
  empty on one bucket of a parallel batch is not proof it is empty — re-check it
  sequentially with a small delay first (Rule 2i). An account blank across every
  variant is a server-side state, not a client fix (Rule 2j).
- **In a long-lived daemon, launch browsers at startup, not per request** — a 5-7s
  launch inside the first request reads as a hang to the user. Re-warm on config change,
  never close after a request (see Rule 3d).
- **Never render a rate-limited/partial result as "empty".** Flag it from a server
  signal (body error code while HTTP 200), not a guessed count (Rule 2e) — a
  false-blank the user trusts is worse than a slow run. Four render states, never
  collapse them: has-data / verified-empty / throttled-empty / risk-flagged-empty
  (ghost-empty, Rule 2h).
- **When rendering a human label per record, generate the label from the record's own
  fields at render time — do not fall back to a static lookup table for records it
  covers.** A table-cached label drops field-level detail (e.g. a per-record threshold/
  cap that varies between otherwise-identical records) and, worse, makes two genuinely
  distinct records collide into one label. If you also DEDUP rendered rows by label,
  those distinct records get swallowed ("4 records in, 3 shown"). Always build the label
  from live fields first, and dedup on a key that includes the varying fields
  (`label|fieldA|fieldB`), never the label string alone.
- **curl-reachable ≠ browser-loadable.** Health-check a proxy by loading the HEAVY
  route in a real browser, write survivors to a file, re-check before every live run —
  pools decay in hours and a dead proxy rides along producing empty results (Rule 4b).
- **A uniform write failure across all payload variants is a THROTTLE, not a body bug**
  — read-vs-write asymmetry is the tell, and re-running deepens it (Rule 4c).
- **Never key a result to its input by list position** — fetch and attach the real
  identity per item (Rule 2f); a cookie-file order is not an account order.
- **Never `submit()` into a pool loop from inside that same loop** — `pool.warm()` called
  from a pool coroutine self-blocks the loop (hang/TimeoutError). Await the internal
  coroutine directly.
- **A pool keyed by browser instance (not launch signature) cannot serve per-request
  proxies** — Playwright bakes proxy at launch; key the pool by the frozen launch kwargs
  (Rule 3e).
- **A test systemd drop-in named without a `zz-` prefix is silently overridden by the
  production drop-in** (lexical order, later wins) — the value you set appears to be
  ignored (Rule 3e).

## Relation to other skills

- Signed-endpoint flow (why a browser is required at all): `transacting-api-automation`.
- Signer reversal if you want to drop the browser: `shopee-antifraud-reversing` /
  `spa-api-recon`.
