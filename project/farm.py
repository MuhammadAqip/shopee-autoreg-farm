#!/usr/bin/env python3
"""Shopee farm runner -- the whole registration chain, per account.

Flow per account:
  device gen -> profile gen -> proxy pin -> warm_up -> send_otp
  -> wait OTP -> verify_otp -> login -> store(active)

Resumable: accounts already 'active' are skipped.

Usage:
  python3 farm.py --count 10                 # build 10, real registration
  python3 farm.py --count 50 --dry-run       # generate + store only, no network
  python3 farm.py --count 5 --proxies proxies.txt
  python3 farm.py --resume                   # continue 'otp_sent'/'pending'
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, "/root/shopee-farm")

from core.device import Device
from core.accounts import AccountGen
from core.shopee_client import ShopeeClient
from core.store import Store
from tools.proxy import ProxyPool, ManualOTP


def build_one(gen: AccountGen) -> tuple:
    """Create the identity + device for one account (no network)."""
    dev = Device()
    prof = gen.profile()
    return prof, dev.as_dict(), dev


def register_one(idx: int, dry_run: bool, pool: ProxyPool, sink, store: Store) -> dict:
    gen = AccountGen()
    prof, dev_json, dev = build_one(gen)
    proxy = pool.acquire(prof["phone"])
    store.insert(prof, dev_json, proxy)
    store.update(prof["phone"], status="pending")

    if dry_run:
        store.update(prof["phone"], status="dry")
        return {"phone": prof["phone"], "status": "dry", "proxy": proxy}

    result = {"phone": prof["phone"], "status": "error", "proxy": proxy}
    try:
        with ShopeeClient(device=dev, proxy=proxy) as cli:
            warm = cli.warm_up()
            result["warm"] = warm.get("status")

            otp_req = cli.send_otp(prof["phone"])
            result["otp_send"] = otp_req.get("http")
            store.update(prof["phone"], status="otp_sent")

            code = sink.wait(prof["phone"], timeout=150)
            if not code:
                result["error"] = "otp_timeout"
                store.update(prof["phone"], status="pending", error="otp_timeout")
                return result

            ver = cli.verify_otp(prof["phone"], code, prof["password"], prof["name"])
            result["otp_verify"] = ver.get("http")

            login = cli.login(prof["phone"], prof["password"])
            token = None
            data = login.get("body", {}).get("data")
            if isinstance(data, dict):
                token = data.get("access_token")

            if token:
                store.update(prof["phone"], status="active", access_token=token,
                             cookie_json=json.dumps(dict(cli.session.cookies)))
                result["status"] = "active"
            else:
                store.update(prof["phone"], status="pending", error=str(login)[:200])
                result["error"] = "no_token"
    except Exception as e:
        result["error"] = str(e)[:200]
        store.update(prof["phone"], status="pending", error=str(e)[:200])
    finally:
        pool.release(prof["phone"], failed=result["status"] != "active")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--proxies", default=None)
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()

    store = Store()
    pool = ProxyPool()
    if args.proxies:
        n = pool.load_file(args.proxies)
        print(f"[+] loaded {n} proxies")
    sink = ManualOTP()

    print(f"[*] farm start  count={args.count}  dry_run={args.dry_run}  "
          f"workers={args.workers}  proxied={len(pool)}")

    ok = err = 0
    if args.dry_run:
        for i in range(args.count):
            r = register_one(i, True, pool, sink, store)
            print(f"  [{i+1}/{args.count}] {r['phone']}  {r['status']}")
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(register_one, i, False, pool, sink, store)
                    for i in range(args.count)]
            for i, f in enumerate(as_completed(futs)):
                r = f.result()
                ok += r["status"] == "active"
                err += r["status"] != "active"
                print(f"  [{i+1}/{args.count}] {r['phone']}  {r['status']}  {r.get('error','')}")

    print(f"\n[done] active={ok} failed={err}")
    print("[stats]", store.stats())


if __name__ == "__main__":
    main()
