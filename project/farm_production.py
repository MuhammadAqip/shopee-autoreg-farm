#!/usr/bin/env python3
"""farm_production.py — penjadwal produksi farm Shopee (Option A: page-context).

Aturan (dari boss):
  - Jam eksekusi: 02:00-05:00 (dini hari, aktivitas rendah)
  - Nomor random (acak jarak)
  - Jarak antar akun: 10-30 menit
  - Report ke WA/Telegram: 🟢 sukses / 🟡 limit / 🔴 gagal
  - Definisi produksi = akun READY; failed = akun LIMIT

Mode:
  farm_production.py --plan N        # cetak jadwal N akun malam ini (dry)
  farm_production.py --run           # jalan (per akun, sesuai jadwal)
  farm_production.py --test-now      # 1 akun sekarang (test)

Status per-akun disimpan di production_state.json.
"""
import os, sys, json, time, random, datetime as dt, subprocess
from pathlib import Path

ROOT = Path("/root/shopee-farm")
STATE = ROOT / "production_state.json"
PY = "/root/sniffenv/bin/python"

sys.path.insert(0, str(ROOT))


def _rep():
    """Lazy-load reputasi nomor (P1b pre-check)."""
    try:
        from phone_reputation import PhoneReputation
        return PhoneReputation()
    except Exception:
        return None


def pick_phone(rep=None, tries=25):
    """Pilih nomor random yang LOLOS pre-check reputasi (anti-LIMIT)."""
    rep = rep or _rep()
    for _ in range(tries):
        ph = random_phone()
        if rep is None:
            return ph
        ok, why = rep.allow(ph)
        if ok:
            return ph
    return random_phone()

def load_state():
    if STATE.exists(): return json.loads(STATE.read_text())
    return {"accounts": [], "date": "", "plan": []}

def save_state(s):
    STATE.write_text(json.dumps(s, indent=1))

def night_plan(n, date=None):
    """Buat jadwal N akun dalam window 02:00-05:00, jarak 10-30 min."""
    date = date or dt.date.today().isoformat()
    start = dt.datetime.fromisoformat(f"{date}T02:00:00")
    end = dt.datetime.fromisoformat(f"{date}T05:00:00")
    plan = []
    t = start + dt.timedelta(minutes=random.randint(0, 20))
    for i in range(n):
        if t >= end:
            # lanjut ke hari berikutnya kalau kehabisan window
            date2 = (dt.date.fromisoformat(date)+dt.timedelta(days=1)).isoformat()
            t = dt.datetime.fromisoformat(f"{date2}T02:00:00") + dt.timedelta(minutes=random.randint(0,20))
            date = date2
        plan.append({"idx": i+1, "at": t.isoformat(), "date": date})
        t += dt.timedelta(minutes=random.randint(10, 30))
    return plan

def random_phone():
    """Nomor ID random (prefix operator valid)."""
    prefix = random.choice(["812","813","815","816","817","818","819","821","822","823","851","852","853","855","856","857","858","859"])
    rest = "".join(str(random.randint(0,9)) for _ in range(8))
    return "62"+prefix+rest

def detect_chat_id():
    """Auto-detect chat id: env → bot getUpdates → home channel fallback."""
    env = os.environ.get("FARM_CHAT_ID", "")
    if env: return env
    try:
        tok = open("/tmp/shopee_bot_token_v2").read().strip()
        import urllib.request
        r = urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/getUpdates", timeout=8)
        d = json.loads(r.read())
        for u in d.get("result", []):
            m = u.get("message") or u.get("channel_post") or {}
            cid = (m.get("chat") or {}).get("id")
            if cid: return str(cid)
    except Exception:
        pass
    # fallback: home channel (proven target)
    return "7341376283"

def notify(msg):
    """Kirim notif ke Telegram (auto-detect chat id)."""
    try:
        tok = open("/tmp/shopee_bot_token_v2").read().strip()
        chat = detect_chat_id()
        subprocess.run(["curl","-s","-m","10",
            f"https://api.telegram.org/bot{tok}/sendMessage",
            "-d", f"chat_id={chat}", "-d", f"text={msg}"], capture_output=True)
    except Exception as e:
        print(f"[notify] {e}", file=sys.stderr)

def run_one(phone, proxy):
    """Jalankan 1 akun via shopee_hold.py (Option A / page-context)."""
    key = open(ROOT/"bot_key.txt").read().strip() if (ROOT/"bot_key.txt").exists() else ""
    cmd = ["xvfb-run","-a","--server-args=-screen 0 1280x900x24", PY, "shopee_hold.py",
           phone, key, proxy, "wa", "--retry=2", "--pw=PASS_REDACTED"]
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, timeout=900)
        out = (r.stdout or b"").decode("utf-8","replace")
        return out
    except subprocess.TimeoutExpired:
        return "TIMEOUT"

def classify(out):
    """Klasifikasi hasil: ready / limit / failed.

    Prioritas: modal anti-fraud (LIMIT) > sukses > gagal.
    """
    o = out.lower()
    # LIMIT: modal "Identifikasi Tambahan" (anti-fraud) — per arahan boss
    if "identifikasi tambahan" in o or "diperlukan identifikasi" in o:
        return "limit"
    if "sudah terdaftar" in o or "no. handphone ini sudah terdaftar" in o:
        return "limit"
    if any(k in o for k in ["sukses", "berhasil", "user_id", "cookie"]):
        return "ready"
    if "limit" in o:
        return "limit"
    return "failed"

def main():
    args = sys.argv[1:]
    if "--plan" in args:
        n = int(args[args.index("--plan")+1]) if args.index("--plan")+1 < len(args) else 10
        plan = night_plan(n)
        print(json.dumps(plan, indent=1))
        s = load_state(); s["plan"] = plan; s["date"] = dt.date.today().isoformat(); save_state(s)
        print(f"\n[plan] {n} akun dijadwalkan. jarak 10-30 min, window 02:00-05:00")
    elif "--test-now" in args:
        rep = _rep()
        phone = pick_phone(rep)
        proxy = (ROOT/"proxies_id_vs.txt").read_text().splitlines()[0].strip()
        print(f"[test] phone={phone}")
        out = run_one(phone, proxy)
        st = classify(out)
        emoji = {"ready":"🟢","limit":"🟡","failed":"🔴"}[st]
        print(f"[test] status={st} {emoji}")
        if rep:
            rep.record(phone, {"ready":"ok","limit":"limit","failed":"fail"}[st])
        save_state({"accounts":[{"phone":phone,"status":st,"at":dt.datetime.now().isoformat()}],
                    "date":dt.date.today().isoformat()})
    elif "--run" in args:
        rep = _rep()
        # prune cache basi (>30 hari) sebelum produksi — hemat disk
        try:
            from captcha_cache import CaptchaCache
            pruned = CaptchaCache().prune(30)
            print(f"[run] cache pruned: {pruned}")
        except Exception as e:
            print(f"[run] prune skip: {e}")
        s = load_state()
        plan = s.get("plan") or night_plan(10)
        print(f"[run] {len(plan)} akun")
        for item in plan:
            at = dt.datetime.fromisoformat(item["at"])
            now = dt.datetime.now()
            if now < at:
                wait = (at-now).total_seconds()
                print(f"[run] akun#{item['idx']} tunggu {wait/60:.1f} min...")
                time.sleep(min(wait, 1800))
            phone = pick_phone(rep)
            proxy = random.choice((ROOT/"proxies_id_vs.txt").read_text().splitlines()).strip()
            out = run_one(phone, proxy)
            st = classify(out)
            msg = {"ready":f"🟢 nomor ini beres / sukses: {phone}",
                   "limit":f"🟡 nomor ini limit: {phone}",
                   "failed":f"🔴 nomor ini gagal: {phone}"}[st]
            notify(msg)
            if rep:
                rep.record(phone, {"ready":"ok","limit":"limit","failed":"fail"}[st])
            s.setdefault("accounts",[]).append({"phone":phone,"status":st,"at":dt.datetime.now().isoformat(),"idx":item["idx"]})
            save_state(s)
        # ringkasan akhir
        accs = s.get("accounts", [])
        ok = sum(1 for a in accs if a["status"]=="ready")
        lim = sum(1 for a in accs if a["status"]=="limit")
        fail = sum(1 for a in accs if a["status"]=="failed")
        notify(f"📊 RINGKASAN PRODUKSI\n🟢 ready={ok} 🟡 limit={lim} 🔴 gagal={fail}\nTotal={len(accs)}")
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
