---
name: proxy-pool-operations
description: Build, validate, and feed rotating proxy pools.
version: 1.0.0
author: curator
license: MIT
metadata:
  hermes:
    tags: [proxy, pool, rotation, brightdata, http, health-check, anonymity]
---

# Proxy Pool Operations

Parse → validate → rotate → feed a proxy list into a service. Covers the format contracts,
the health-check harness, and the pitfalls that make a working pool read as dead.

## When to Use

- The user hands you a proxy endpoint URL and asks to "gas" it (build a usable pool).
- A downstream service (solver, checker, scraper) reports `0/0 healthy` or `loaded 0 proxies`.
- You need a rotating exit for concurrent requests (browser automation, carding checker,
  account farming).

## 1. Detect the format before anything else

Vendors ship several line orders. The order determines which parser accepts the line:

| Form | Accepts |
|------|---------|
| `host:port:user:pass` | Bright Data native panel output |
| `user:pass@host:port` | common in scraped lists |
| `scheme://user:pass@host:port` | the canonical URL — most parsers expect THIS |
| `host:port` | unauthenticated proxies |

Fetch one page and eyeball the first line before writing any parser. A parser that accepts
the form you *expected* instead of the form you *got* silently loads 0 lines — see Rule 3.

## 2. Health-check with a real egress check, not a TCP dial

A pool is only proven by an egress IP that differs from your direct IP:

```python
# direct IP first — the baseline you must NOT see again through a proxy
# then per-proxy: hit an IP-echo endpoint and record the returned IP + latency
#   IP_ECHO = "https://api.ipify.org?format=json"
#   live = status==200 AND ip != direct_ip
```

Report a real distribution every run: **live ratio, unique egress IPs, min/avg latency**.
A pool that claims `100% live` with a single unique egress IP is one proxy behind many
credentials — flag it. Bucket survivors to a file the downstream service reads (never a
hardcoded list baked into a script).

## 3. Rule — a pool file has a FORMAT contract; `loaded 0` is a mismatch, not a dead pool

When a service logs `loaded 0 proxies` while the file has hundreds of non-empty lines, the
parser rejected every line — a **format mismatch**, not a dead pool.

- **`urlparse`-based normalizers reject `host:port:user:pass`**: `urlparse` sees `host` as the
  scheme, finds no `.port`, returns `None`. 500 lines in → 0 loaded, service still "healthy".
- Convert at ingest to one canonical form before writing the pool file:

```python
if "://" in line:
    url = line
else:
    p = line.split(":")
    if len(p) == 4:                       # host:port:user:pass
        host, port, user, pw = p
        url = f"http://{user}:{pw}@{host}:{port}"
    elif len(p) == 2:                     # host:port (no auth)
        url = f"http://{p[0]}:{p[1]}"
```

- Keep the converter a **separate readable file** (`convert-proxies.py`), never an inline
  `python3 -c` inside a quoted heredoc — heredoc quoting strips `"$VAR"` expansion inside the
  python source and the line-count guard breaks silently (`open()` with no arg, `TypeError`).
- Verify the load from the service's own signal (`proxy_pool: {size, healthy}`), not from the file
  you wrote. After a restart the pool warms asynchronously — `size:0` for the first seconds is
  normal; poll until it settles and cross-check the load log line before concluding failure.

## 4. Rule — `httpx>=0.28` removed the per-request `proxy=` kwarg

A health sweep that finishes in ~0.1s and reports **100% dead with `TypeError`** is the httpx API
change, not a dead pool. Proxy config moved to **client construction only**:

```python
# WRONG on httpx>=0.28 — per-request kwarg was removed
r = await client.get(url, proxy=proxy_url)          # TypeError, instant, every proxy

# RIGHT — proxy is a client-construction arg
async with httpx.AsyncClient(proxy=proxy_url, timeout=t) as c:
    r = await c.get(url)
```

For a one-shot probe a short-lived client per proxy is fine; concurrency via
`asyncio.Semaphore` still works. Print the exception class per failure — only `ConnectError` /
`TimeoutException` are genuine dead proxies; an instant uniform `TypeError` is always the harness.

## 5. Rule — a decayable pool belongs in cron, not in a manual patch

Rotating / free upstreams die within hours. Wire refresh once instead of hand-fixing each time:

```bash
# refresh-proxies.sh — fetch -> convert -> count-gate -> write -> restart, refuse short lists
RAW=$(mktemp); OUT=$(mktemp)
curl -fsSL -m 30 "<pool-endpoint>" -o "$RAW"
python3 /opt/<svc>/convert-proxies.py "$RAW" > "$OUT"
N=$(wc -l < "$OUT")
[ "$N" -ge 50 ] && cp "$OUT" <pool-file> && systemctl restart <svc> || echo "refused: $N"
```

`0 */6 * * * /opt/<svc>/refresh-proxies.sh >> /var/log/<svc>-proxy-refresh.log 2>&1`

Refuse a short list — installing 3 dead proxies as the whole pool is worse than keeping the old
file. Back up the replaced list before overwriting.

## 6. Rotation server (round-robin every request)

When the consumer only takes ONE proxy but you want rotation, run a local CONNECT proxy that
round-robins the pool upstream. Point the consumer at `http://127.0.0.1:<port>`; each CONNECT
picks the next upstream and injects its `Proxy-Authorization: Basic` header. Verify rotation the
same way as the pool — N hits, N distinct egress IPs.

## 7. Rule — a plain `GET` liveness probe does NOT prove the proxy can carry CONNECT

"Proxy answers HTTP" and "proxy can drive a browser" are DIFFERENT tests. The browser
reaches every HTTPS origin through the proxy's `CONNECT host:443` tunnel, and many pools
(especially cheap rotating residential) answer a plain `GET` probe yet time out or 407 on
CONNECT -> the browser shows `ERR_TUNNEL_CONNECTION_FAILED` / `ERR_TIMED_OUT` while the
pool still reports healthy.

- Probe CONNECT directly and keep only `200`:

```python
import socket, base64
s = socket.create_connection((host, int(port)), timeout=10)
auth = base64.b64encode(f"{user}:{pw}".encode()).decode()
s.sendall((f"CONNECT {target_host}:443 HTTP/1.1\r\nHost: {target_host}:443\r\n"
           f"Proxy-Authorization: Basic {auth}\r\n\r\n").encode())
line = s.recv(64)          # b'HTTP/1.1 200 Connection established' == usable
```

- **Probe CONNECT against the ACTUAL target host**, not just a neutral one. A cred that
  CONNECTs to `httpbin.org` can still be refused/burnt on the real target — exit IPs are
  per-connection, so the same credential lands on a different exit each time. A single
  failing cred is variance, not a dead pool: **retry logic is mandatory** (a proxy that
  fails the first CONNECT frequently succeeds on the second, new exit IP).
- Rotating-residential pools show large per-slot variance: expect ~1-in-N connection
  failures even on a 99%-live pool. The pool builder must rank/retry, and the downstream
  runner must carry a per-attempt retry budget (2-3 attempts) rather than treating the
  first failure as "pool dead".
- **`407` at the CONNECT layer with a body like `TRAFFIC_EXHAUSTED` is a plan/credit
  state, not a bad cred** — the vendor account is out of GB. Detect it explicitly so you
  don't scan 10k creds hunting for a working one when the whole plan is dry.

## 8. Rule — match proxy CLASS to the target's egress requirement

Datacenter egress is scored independently of browser fingerprint by the anti-bot edge.
For Google reCAPTCHA specifically, datacenter (the VPS itself OR a datacenter proxy, ASN
unchanged) ALWAYS escalates to an image challenge and blocks the free audio path; a
trusted **residential** exit passes as a bare checkbox / serves a real challenge.

- Classify each survivor by egress ASN before promising a run: hit an IP-echo endpoint
  through the proxy (`https://api.ipify.org?format=json`) and check the ASN is an ISP
  (Telus/Comcast/Vodafone…), not a cloud range. Residential = the exit a reCAPTCHA-gated
  signup actually needs.
- Record the concrete egress IP in the pool metadata so a "burnt IP" can be rotated
  deliberately rather than re-tried.
- Do not promise a datacenter pool will pass Akamai/DataDome/reCAPTCHA-image gates —
  those need residential; say so up front.

## Pitfalls

- **`loaded 0` from a full file = format mismatch**, never a dead pool (Rule 3).
- **An all-dead sweep in ~0.1s is an API bug**, not dead proxies — httpx>=0.28 client-construction
  proxy (Rule 4).
- **A pool that only passed a plain `GET` probe may fail CONNECT** — the browser gate is
  CONNECT, and `ERR_TUNNEL_CONNECTION_FAILED` with a "healthy" pool is this (Rule 7).
- **`407 TRAFFIC_EXHAUSTED` on CONNECT is a dry plan**, not a bad cred list (Rule 7).
- **An inline `python3 -c` inside a quoted heredoc loses `"$VAR"`** — shell expansion does not
  cross into the python source; use a standalone converter file.
- **`100% live` with one unique egress IP is one proxy, many credentials** — report unique-IP count
  alongside the live ratio.
- **A pool warmed asynchronously shows `size:0` right after restart** — poll until settled; do not
  declare failure at t+2s.
- **Datacenter egress is scored independently of browser fingerprint** — Cloudflare-tolerant targets
  work, but Akamai/DataDome need residential; do not promise a datacenter pool will pass those.

## Relation to other skills

- Driving the pool through a browser (per-signature browser keying, proxy-at-launch):
  `browser-pool-concurrency`.
- Deploying the service the pool feeds (e.g. a captcha solver sidecar): the solver's own deploy skill.
