#!/usr/bin/env python3
"""key_manager.py — P2: rotasi + failover API key SadCaptcha.

Sumber key (digabung, dedup by api key):
  - /root/sadfarm/keypool.json        (farm key)
  - /root/shopee-farm/sadkey_db.json  (db key + credits)
  - /root/shopee-farm/bot_key.txt     (current active)

Fungsi:
  km = KeyManager()
  key = km.next()                  # key dgn kredit > 0 (round-robin)
  km.mark(key, delta=-1)           # kurangi 1 kredit setelah solve
  km.refresh(key)                  # tanya /license/credits, update kredit
  km.alive()                       # list key yg masih ada kredit

Aturan:
  - key dgn credits <= LOW_WATER (mis. 2) → prioritas turun
  - key dgn credits 0 → skip
  - failover: kalau key habis saat dipakai → auto pindah key berikutnya
"""
import json
import os
import time

ROOT = "/root/shopee-farm"
SADFARM = "/root/sadfarm"
LOW_WATER = 2           # ambang kredit rendah
DB_CACHE = f"{ROOT}/key_manager_cache.json"


def _load_json(p):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


class KeyManager:
    def __init__(self):
        self.keys = {}   # key -> {"credits": int|None, "email": str, "src": str}
        self._idx = 0
        self._load()

    def _load(self):
        # 1. sadkey_db.json (paling lengkap: credits)
        for k, v in _load_json(f"{ROOT}/sadkey_db.json").items():
            cr = v.get("credits") if isinstance(v, dict) else None
            self.keys.setdefault(k, {"credits": cr, "email": v.get("email", "") if isinstance(v, dict) else "", "src": "sadkey_db"})
        # 2. sadfarm/keypool.json
        for k, v in _load_json(f"{SADFARM}/keypool.json").items():
            cr = v.get("credits") if isinstance(v, dict) else None
            if k not in self.keys:
                self.keys[k] = {"credits": cr, "email": v.get("email", "") if isinstance(v, dict) else "", "src": "keypool"}
        # 3. bot_key.txt
        try:
            bk = open(f"{ROOT}/bot_key.txt").read().strip()
            if bk and len(bk) > 20:
                self.keys.setdefault(bk, {"credits": None, "email": "", "src": "bot_key"})
        except Exception:
            pass

    def alive(self):
        """Key dgn kredit > 0 (atau belum diketahui)."""
        out = []
        for k, v in self.keys.items():
            c = v.get("credits")
            if c is None or c > 0:
                out.append(k)
        return out

    def next(self):
        """Round-robin key hidup, prioritaskan kredit tertinggi."""
        pool = self.alive()
        if not pool:
            return None
        # urut: kredit diketahui & besar dulu, lalu yg belum diketahui
        pool.sort(key=lambda k: (self.keys[k].get("credits") is None,
                                 -(self.keys[k].get("credits") or 0)))
        # round-robin dalam grup kredit cukup
        good = [k for k in pool if (self.keys[k].get("credits") or 0) > LOW_WATER] or pool
        self._idx %= len(good)
        k = good[self._idx]
        self._idx = (self._idx + 1) % len(good)
        return k

    def mark(self, key, delta=-1):
        """Sesuaikan kredit setelah pemakaian."""
        if key in self.keys:
            c = self.keys[key].get("credits")
            if c is not None:
                self.keys[key]["credits"] = max(0, c + delta)
            else:
                self.keys[key]["credits"] = delta if delta < 0 else None

    def refresh(self, key=None, timeout=20):
        """Tanya /license/credits untuk key tertentu (atau semua). Return dict."""
        import requests
        targets = [key] if key else list(self.keys.keys())
        res = {}
        for k in targets:
            try:
                r = requests.get("https://www.sadcaptcha.com/api/v1/license/credits",
                                 params={"licenseKey": k}, timeout=timeout)
                if r.status_code == 200:
                    cr = int(r.json().get("credits", 0))
                    self.keys[k]["credits"] = cr
                    res[k] = cr
                elif r.status_code == 401:
                    self.keys[k]["credits"] = 0
                    res[k] = 0
                else:
                    res[k] = self.keys[k].get("credits")
            except Exception as e:
                res[k] = f"err:{str(e)[:40]}"
        self._save_cache()
        return res

    def _save_cache(self):
        try:
            with open(DB_CACHE, "w") as f:
                json.dump(self.keys, f, indent=1)
        except Exception:
            pass

    def summary(self):
        al = self.alive()
        total = sum((v.get("credits") or 0) for v in self.keys.values())
        return {"total_keys": len(self.keys), "alive": len(al),
                "total_credits": total,
                "low": [k[:10] for k, v in self.keys.items() if (v.get("credits") or 0) <= LOW_WATER]}


if __name__ == "__main__":
    import sys
    km = KeyManager()
    if len(sys.argv) > 1 and sys.argv[1] == "refresh":
        r = km.refresh()
        print(f"refreshed {len(r)} keys")
    print("summary:", json.dumps(km.summary(), indent=1))
    print("next key:", (km.next() or "")[:12], "…")
    print("alive keys:", len(km.alive()))
