#!/usr/bin/env python3
"""backup_account.py — backup akun ke target (local / webhook / gsheet).

Target:
  local   → file CSV di /root/shopee-farm/backup/
  webhook → POST JSON ke URL (Sheet via Apps Script webhook, Zapier, dll)
  gsheet  → butuh GSHEET_WEBHOOK env (Apps Script URL)

Usage:
  backup_account.py   (bakal dipanggil bot otomatis setelah akun jadi)
"""
import os, sys, json, time, csv, requests

ROOT = "/root/shopee-farm"
BK = f"{ROOT}/backup"
ACCOUNTS = f"{ROOT}/account_result.json"


def read_accounts():
    out = []
    try:
        for line in open(ACCOUNTS):
            line = line.strip()
            if line.startswith("{"):
                try: out.append(json.loads(line))
                except Exception: pass
    except Exception:
        pass
    return out


def backup_local(acc):
    os.makedirs(BK, exist_ok=True)
    f = f"{BK}/accounts.csv"
    new = not os.path.exists(f)
    with open(f, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["username", "password", "phone", "user_id",
                        "fingerprint", "device_id", "cookie", "created"])
        w.writerow([acc.get("username", ""), acc.get("password", ""), acc.get("phone", ""),
                    acc.get("user_id", ""), acc.get("fingerprint", ""), acc.get("device_id", ""),
                    acc.get("cookie", ""), time.strftime("%Y-%m-%d %H:%M:%S")])
    return f


def backup_webhook(acc, url):
    try:
        r = requests.post(url, json=acc, timeout=20)
        return r.status_code == 200
    except Exception:
        return False


def backup(acc, target="local", webhook_url=""):
    if target == "webhook" and webhook_url:
        return {"target": "webhook", "ok": backup_webhook(acc, webhook_url)}
    if target == "gsheet":
        url = webhook_url or os.environ.get("GSHEET_WEBHOOK", "")
        if url:
            return {"target": "gsheet", "ok": backup_webhook(acc, url)}
    p = backup_local(acc)
    return {"target": "local", "ok": True, "path": p}


def export_all_csv():
    os.makedirs(BK, exist_ok=True)
    f = f"{BK}/accounts_all_{int(time.time())}.csv"
    accs = read_accounts()
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["username", "password", "phone", "user_id",
                    "fingerprint", "device_id", "cookie"])
        for a in accs:
            w.writerow([a.get("username", ""), a.get("password", ""), a.get("phone", ""),
                        a.get("user_id", ""), a.get("fingerprint", ""), a.get("device_id", ""),
                        a.get("cookie", "")])
    return f


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "export"
    if cmd == "export":
        print("exported:", export_all_csv())
    else:
        accs = read_accounts()
        if accs:
            print(json.dumps(backup(accs[-1]), indent=1))
