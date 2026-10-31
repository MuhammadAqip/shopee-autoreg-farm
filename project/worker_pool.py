#!/usr/bin/env python3
"""worker_pool.py — #10: jalankan N registrasi paralel (worker pool).

Tiap worker: nomor + proxy + key sendiri → jalankan shopee_hold → tunggu OTP.
OTP dibaca dari file per-worker (.otp_input_<phone>) supaya ga bentrok.
Hasil akun dikumpulin ke account_result.json (dict).

Usage: worker_pool.py <phone1,phone2,...> [--workers 3] [--channel wa]
"""
import os, sys, json, time, subprocess, threading
import random

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
SOLVER = f"{ROOT}/shopee_hold.py"

WORKERS = 3
CHANNEL = "wa"
PW = "PASS_REDACTED"
for a in sys.argv:
    if a.startswith("--workers="): WORKERS = int(a.split("=", 1)[1])
    if a.startswith("--channel="): CHANNEL = a.split("=", 1)[1]


_KM_SINGLETON = None


def _km():
    """Singleton KeyManager — biar round-robin idx gak reset tiap call."""
    global _KM_SINGLETON
    if _KM_SINGLETON is None:
        try:
            import key_manager
            _KM_SINGLETON = key_manager.KeyManager()
        except Exception:
            _KM_SINGLETON = False
    return _KM_SINGLETON or None


def read_key():
    # [P3] pakai KeyManager (rotasi + kredit) kalau ada
    km = _km()
    if km:
        k = km.next()
        if k: return k
    try:
        import sadkey_db as K
        b = K.best_key()
        if b: return b
    except Exception: pass
    try: return open(f"{ROOT}/bot_key.txt").read().strip()
    except Exception: return os.environ.get("SADCAPTCHA_KEY", "")


def read_key_for(phone):
    """[P3] tiap nomor boleh beda key (hindari 1 key jenuh) — round-robin."""
    km = _km()
    if km:
        k = km.next()
        if k: return k
    return read_key()


def _rep():
    try:
        import phone_reputation
        return phone_reputation.PhoneReputation()
    except Exception:
        return None


def proxies():
    out = []
    for fn in ("proxies_best.txt", "proxies_id_vs.txt"):
        try: out += [l.strip() for l in open(f"{ROOT}/{fn}") if l.strip()]
        except Exception: pass
    return out


def classify_pool(out):
    o = out.lower()
    if "identifikasi tambahan" in o or "sudah terdaftar" in o:
        return "limit"
    if "success" in o or "account_saved" in o or "user_id" in o:
        return "ready"
    return "failed"


def run_one(phone, proxy, key, result_box, log):
    otp_file = f"{ROOT}/.otp_input_{phone}"
    env = dict(os.environ, SADCAPTCHA_KEY=key)
    cmd = [PY, SOLVER, phone, key, proxy, CHANNEL, "--retry=20", f"--pw={PW}"]
    log(f"[W:{phone}] start (proxy ...{proxy.split('@')[-1]}) key={str(key)[:6]}…")
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env, timeout=560,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = p.stdout.decode(errors="ignore")
        st = classify_pool(out)
        result_box[phone] = {"ok": st == "ready", "status": st, "otp_file": otp_file}
        log(f"[W:{phone}] {'✅ SUKSES' if st=='ready' else ('🟡 LIMIT' if st=='limit' else '❌ gagal')}")
        # [P3] catat reputasi nomor
        rep = _rep()
        if rep:
            rep.record(phone, {"ready": "ok", "limit": "limit", "failed": "fail"}[st])
    except Exception as e:
        result_box[phone] = {"ok": False, "status": "failed", "err": str(e)[:80]}
        log(f"[W:{phone}] err {str(e)[:60]}")


def run_pool(phones, workers=WORKERS, log=print):
    px = proxies()
    if not px:
        px = ["http://8108c95881d0c4b2f18e__cr.id;sessttl.5:7dfd03c5eb868991@gb.vsproxy.org:10000"]
    result = {}
    lock = threading.Lock()
    used_proxies = set()     # [P3] 1 proxy = 1 worker pada saat bersamaan
    rep = _rep()

    def worker_loop():
        while True:
            with lock:
                if not phones: return
                ph = phones.pop(0)
                # [P3] pre-check reputasi
                if rep:
                    ok, why = rep.allow(ph)
                    if not ok:
                        result[ph] = {"ok": False, "status": "skipped", "why": why}
                        log(f"[W:{ph}] ⏭ skip: {why}")
                        continue
                # pilih proxy yg belum dipakai (hindari tabrakan IP)
                free = [p for p in px if p not in used_proxies] or px
                prx = random.choice(free)
                used_proxies.add(prx)
            try:
                run_one(ph, prx, read_key_for(ph), result, log)
            finally:
                with lock:
                    used_proxies.discard(prx)

    threads = [threading.Thread(target=worker_loop) for _ in range(min(workers, len(phones) or 1))]
    for t in threads: t.start()
    for t in threads: t.join()
    return result


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    phones = [x.strip() for x in ",".join(args).replace(";", ",").split(",") if x.strip()]
    if not phones:
        print("usage: worker_pool.py <phone,phone,...> [--workers N]"); sys.exit(1)
    print(f"[pool] {len(phones)} nomor, {WORKERS} worker")
    res = run_pool(phones)
    print(f"[pool] selesai: {sum(1 for v in res.values() if v.get('ok'))}/{len(res)} sukses")
