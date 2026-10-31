# -*- coding: utf-8 -*-
"""nuke_accounts.py - hapus SEMUA akun di database (CLI, headless).

  python3 nuke_accounts.py              # dry-run (tampilkan jumlah, TIDAK hapus)
  python3 nuke_accounts.py --yes        # hapus accounts.json (backup otomatis)
  python3 nuke_accounts.py --yes --full # hapus + bersihin file turunan

Restore: cp accounts.backup.<ts>.json accounts.json
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ACC = os.path.join(HERE, "accounts.json")
DERIVED = ["acc_check_result.json", "db_check_result.json", "30cok.txt", "response.txt"]

do_yes = "--yes" in sys.argv
full = "--full" in sys.argv

def count(p):
    try:
        with open(p) as f:
            d = json.load(f)
        return len(d) if isinstance(d, list) else len(d.get("accounts") or d or {})
    except Exception:
        return -1

n = count(ACC)
print(f"[*] accounts.json -> {n} akun")
print(f"[*] file turunan: " + ", ".join(f"{fn}={'ada' if os.path.exists(os.path.join(HERE,fn)) else '-'}" for fn in DERIVED))

if not do_yes:
    print("\n[DRY-RUN] tidak ada yang dihapus. Tambah --yes untuk eksekusi."); sys.exit(0)

ts = time.strftime("%Y%m%d_%H%M%S")
bak = os.path.join(HERE, f"accounts.backup.{ts}.json")
try:
    with open(ACC) as f: raw = f.read()
    with open(bak, "w") as f: f.write(raw)
    print(f"[+] backup -> {os.path.basename(bak)}")
except Exception as e:
    print(f"[!] backup gagal: {e}"); sys.exit(1)

with open(ACC, "w") as f:
    json.dump([], f, indent=4)
print(f"[+] wiped accounts.json ({n} -> 0)")

if full:
    for fn in DERIVED:
        p = os.path.join(HERE, fn)
        try:
            if os.path.exists(p): os.remove(p); print(f"[+] removed {fn}")
        except Exception as e:
            print(f"[!] gagal hapus {fn}: {e}")

print(f"\n[+] DONE. Restore: cp accounts.backup.{ts}.json accounts.json")
