#!/usr/bin/env python3
"""bot_store.py — penyimpanan persisten untuk bot: settings, stats, proxies.

Data disimpan di bot_data.json (per-user settings + global).

Skema:
{
  "users": {
    "<uid>": {
      "channel": "wa", "pwmode": "auto", "retry": 3,
      "auto_proxy": true, "custom_proxies": [],
      "credit_alert": 5, "backup_target": "local"
    }
  },
  "stats": {
    "total_attempts": 0, "total_success": 0, "total_fail": 0,
    "today": "<YYYY-MM-DD>", "today_success": 0, "today_fail": 0,
    "credits_spent": 0, "cache_hits": 0
  },
  "allowed_ids": [],           # kalau kosong = semua boleh
  "custom_proxies": []         # global custom proxy list
}
"""
import json, os, time, threading

ROOT = "/root/shopee-farm"
FILE = f"{ROOT}/bot_data.json"
_lock = threading.Lock()

DEFAULT_USER = {
    "channel": "wa",
    "pwmode": "auto",
    "retry": 3,
    "custom_pw": "",
    "auto_proxy": True,
    "credit_alert": 5,
    "backup_target": "local",
}

DEFAULTS = {
    "users": {},
    "stats": {
        "total_attempts": 0, "total_success": 0, "total_fail": 0,
        "today": time.strftime("%Y-%m-%d"),
        "today_success": 0, "today_fail": 0,
        "credits_spent": 0, "cache_hits": 0,
    },
    "allowed_ids": [],
    "custom_proxies": [],
    "history": {},
}


def _load():
    if not os.path.exists(FILE):
        return json.loads(json.dumps(DEFAULTS))
    try:
        with open(FILE) as f:
            d = json.load(f)
        for k, v in DEFAULTS.items():
            d.setdefault(k, json.loads(json.dumps(v)) if not isinstance(v, str) else v)
        return d
    except Exception:
        return json.loads(json.dumps(DEFAULTS))


def _save(d):
    try:
        with open(FILE, "w") as f:
            json.dump(d, f, indent=1, ensure_ascii=False)
    except Exception:
        pass


def get_user(uid):
    with _lock:
        d = _load()
        u = d["users"].get(str(uid), {})
        out = dict(DEFAULT_USER)
        out.update(u)
        return out


def set_user(uid, **kw):
    with _lock:
        d = _load()
        u = d["users"].get(str(uid), {})
        base = dict(DEFAULT_USER); base.update(u)
        base.update(kw)
        d["users"][str(uid)] = base
        _save(d)
        return base


def get_all():
    with _lock:
        return _load()


def set_all(k, v):
    with _lock:
        d = _load()
        d[k] = v
        _save(d)
        return v


# ---------- stats ----------

def _roll_today(s):
    today = time.strftime("%Y-%m-%d")
    if s.get("today") != today:
        s["today"] = today
        s["today_success"] = 0
        s["today_fail"] = 0


def bump(kind, n=1):
    """kind: attempt|success|fail|cache_hit|credit."""
    with _lock:
        d = _load()
        s = d["stats"]
        _roll_today(s)
        if kind == "attempt":
            s["total_attempts"] = s.get("total_attempts", 0) + n
        elif kind == "success":
            s["total_success"] = s.get("total_success", 0) + n
            s["today_success"] = s.get("today_success", 0) + n
            _hist(d, "success", n)
        elif kind == "fail":
            s["total_fail"] = s.get("total_fail", 0) + n
            s["today_fail"] = s.get("today_fail", 0) + n
            _hist(d, "fail", n)
        elif kind == "cache_hit":
            s["cache_hits"] = s.get("cache_hits", 0) + n
            _hist(d, "cache_hit", n)
        elif kind == "credit":
            s["credits_spent"] = s.get("credits_spent", 0) + n
        _save(d)
        return dict(s)


def _hist(d, key, n=1):
    """catat histori harian."""
    h = d.setdefault("history", {})
    today = time.strftime("%Y-%m-%d")
    day = h.setdefault(today, {"success": 0, "fail": 0, "cache_hit": 0})
    day[key] = day.get(key, 0) + n
    # simpan max 60 hari terakhir
    if len(h) > 60:
        for old in sorted(h.keys())[:-60]:
            h.pop(old, None)


def history(days=14):
    """return list [(date, success, fail, cache_hit)] terurut asc."""
    with _lock:
        d = _load()
        h = d.get("history", {})
        out = []
        for i in range(days - 1, -1, -1):
            day = time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
            v = h.get(day, {})
            out.append((day, v.get("success", 0), v.get("fail", 0), v.get("cache_hit", 0)))
        return out


def stats():
    with _lock:
        d = _load()
        s = d["stats"]
        _roll_today(s)
        _save(d)
        return dict(s)


# ---------- proxies ----------

def custom_proxies():
    with _lock:
        return _load().get("custom_proxies", [])


def add_proxy(p):
    p = p.strip()
    if not p:
        return False
    with _lock:
        d = _load()
        lst = d.setdefault("custom_proxies", [])
        if p in lst:
            return False
        lst.append(p)
        _save(d)
        return True


def del_proxy(idx):
    with _lock:
        d = _load()
        lst = d.setdefault("custom_proxies", [])
        if 0 <= idx < len(lst):
            lst.pop(idx); _save(d); return True
        return False


def clear_proxies():
    with _lock:
        d = _load(); d["custom_proxies"] = []; _save(d)


# ---------- allowed ids ----------

def allowed_ids():
    with _lock:
        return _load().get("allowed_ids", [])


def add_allowed(uid):
    uid = str(uid).strip()
    if not uid:
        return False
    with _lock:
        d = _load()
        lst = d.setdefault("allowed_ids", [])
        if uid in lst:
            return False
        lst.append(uid); _save(d); return True


def del_allowed(uid):
    uid = str(uid).strip()
    with _lock:
        d = _load()
        lst = d.setdefault("allowed_ids", [])
        if uid in lst:
            lst.remove(uid); _save(d); return True
        return False


def clear_allowed():
    with _lock:
        d = _load(); d["allowed_ids"] = []; _save(d)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(json.dumps(stats(), indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "dump":
        print(json.dumps(get_all(), indent=1))
    else:
        print("usage: bot_store.py stats|dump")
