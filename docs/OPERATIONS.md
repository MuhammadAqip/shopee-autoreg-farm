# OPERATIONS — Runbook Harian

Cara mengoperasikan farm: cek kesehatan, menjalankan batch, memantau, dan
memulihkan dari kegagalan.

---

## 1. Pemeriksaan Pagi

Lima perintah, tiga puluh detik.

```bash
cd project && source /root/sniffenv/bin/activate

python3 key_manager.py status        # kredit
python3 captcha_cache.py stats       # hit rate
python3 phone_reputation.py stats    # prefix diblok
python3 health_monitor.py            # overall
ls -la farm_out/ | tail -5           # run terakhir
```

### Yang dianggap sehat

```
key_alive        >= 2
credits_total    >= 20
cache_size       > 50 puzzle
prefix_blocked   < 30% dari total prefix
run_terakhir     < 24 jam
```

Kalau salah satu di bawah ambang, lihat bagian [Pemulihan](#8-pemulihan).

---

## 2. Menjalankan Batch

### Selalu plan dulu

```bash
python3 farm_production.py --plan 50
```

Output: `farm_out/plan_YYYYMMDD_HHMMSS.json`

Isi:

```json
{
  "target": 50,
  "selected": [
    {"phone": "08123...", "proxy": "proxy-A", "prefix": "8123"},
    ...
  ],
  "skipped": [
    {"phone": "08787...", "reason": "prefix 8787 rate 100%"}
  ],
  "estimated_credits": 19
}
```

**Review dulu sebelum run.** Nomor yang di-skip menunjukkan reputasi bekerja.

```bash
python3 -c "
import json, glob
f = sorted(glob.glob('farm_out/plan_*.json'))[-1]
p = json.load(open(f))
print('selected:', len(p['selected']))
print('skipped :', len(p['skipped']))
print('est kredit:', p['estimated_credits'])
"
```

### Eksekusi

```bash
python3 farm_production.py --run
```

Progress muncul di stdout. Hasil akhir:

```
farm_out/run_YYYYMMDD_HHMMSS.json
```

### Format hasil

```json
{
  "total": 50,
  "ready": 31,
  "limit": 14,
  "failed": 5,
  "credits_used": 19,
  "duration_s": 4200,
  "results": [
    {"phone": "08xxx", "status": "ready", "user_id": "16823...", "at": 1793...}
  ]
}
```

---

## 3. Jadwal Ideal

```
02:00  plan 50
02:02  run
```

Kenapa jam 02:00–05:00:

- trafik Shopee rendah
- anti-fraud lebih longgar
- OTP masuk lebih cepat
- IP residential lebih jarang bersaing

Kalau run melewati 05:00, sisa akun ditunda ke hari berikutnya —
`farm_production` menyimpan state dan bisa dilanjutkan.

---

## 4. Cron

```cron
*/30 *  * * *   key_watchdog.py              # jaga min 2 alive, 20 kredit
0    */6 * * *   account_warmer.py --warm     # panaskan akun baru
15   */2 * * *   proxy_health.py              # cek proxy
*/20 *  * * *   prewarm_cache.py             # isi cache saat sepi
0    2  * * *   farm_production.py --plan 50
2    2  * * *   farm_production.py --run
30   */6 * * *   key_manager.py refresh
0    6  * * *   captcha_cache.py prune 30
```

### Kenapa tiap cron ada

| Cron | Alasan |
|---|---|
| `key_watchdog` | kredit habis di tengah run = kehilangan slot |
| `account_warmer` | akun baru "dingin", gampang kena limit saat dipakai |
| `proxy_health` | proxy mati = akun gagal tanpa sebab jelas |
| `prewarm_cache` | jam sepi = kredit murah, isi cache |
| `plan` + `run` | dipisah supaya plan bisa direview |
| `key_manager refresh` | kredit berubah tanpa notifikasi |
| `prune` | DB tumbuh ~150 KB/puzzle |

---

## 5. Memantau Run

### Tail log

```bash
tail -f farm_out/log_$(date +%Y%m%d).log
```

Baris yang dicari:

```
[worker-1] 08123... → captcha CACHE HIT (0 credit)
[worker-1] 08123... → captcha API SOLVE (1 credit)
[worker-1] 08123... → OTP WAITING
[worker-1] 08123... → READY user_id=16823513404
[worker-2] 08787... → LIMIT Identifikasi Tambahan
```

`CACHE HIT` = gratis. Kalau semua `API SOLVE`, hit rate sedang turun — Shopee
rotasi puzzle.

### Monitor realtime

```bash
python3 chart_stats.py --live
```

---

## 6. Export Hasil

### Dari panel

```
http://localhost:8088  →  ⬇ CSV   /  ⬇ JSON
```

### Dari CLI

```bash
python3 -c "
import sqlite3, json
db = sqlite3.connect('core/store.db')
rows = db.execute('SELECT Username,Password,Nomor,UserId,Cookie FROM accounts WHERE status=\"ready\"')
print(json.dumps([dict(zip(['u','p','phone','uid','cookie'], r)) for r in rows], indent=1))
" > ready_accounts.json
```

---

## 7. Panaskan Akun Baru

Akun yang langsung dijual/dipakai setelah registrasi lebih mudah kena limit.

```bash
python3 account_warmer.py --warm
```

Yang dilakukan:

```
browsing halaman produk (bukan transaksi)
scroll, jeda acak
tanpa login ulang
durasi 2–5 menit per akun
```

Hasil disimpan di `accounts_health.json`.

---

## 8. Pemulihan

### Kredit habis

```bash
python3 key_manager.py refresh
python3 key_manager.py status

# semua dead → tambahkan key baru
python3 key_manager.py add <license_key>
```

Sementara kredit habis, produksi berhenti. Cache tetap jalan — kalau banyak
puzzle sudah tersimpan, beberapa akun masih bisa diselesaikan.

### Semua nomor diblok

```bash
python3 phone_reputation.py stats
# kalau banyak prefix rate 100%, sumber nomor yang bermasalah
```

Kalau semua prefix diblok, reputasi terlalu agresif. Reset:

```bash
python3 phone_reputation.py reset --prefix 8787
```

### Proxy mati semua

```bash
python3 proxy_health.py --verbose
# tambahkan proxy baru ke proxies.txt
python3 proxy_health.py --reload
```

### Browser crash

```bash
pgrep -c chrome
pkill -f "chrome.*headless"
sleep 3
# turunkan concurrency
python3 farm_production.py --run --concurrency 1
```

### Batch berhenti di tengah

```bash
# state tersimpan di SQLite — cukup jalankan ulang
python3 farm_production.py --run --resume
```

`--resume` melewati akun yang sudah `ready` atau `limit`.

### Cache terlalu besar

```bash
du -sh captcha_cache.db
python3 captcha_cache.py prune 30      # hapus > 30 hari
python3 captcha_cache.py vacuum
```

---

## 9. Backup

### Yang perlu di-backup

```bash
tar czf shopee_farm_backup_$(date +%Y%m%d).tar.gz \
  core/store.db \
  captcha_cache.db \
  accounts_health.json \
  phone_reputation.json \
  key_store.json \
  config.json \
  proxies.txt
```

### Yang tidak perlu

```
reference/         ← artefak RE, statis
__pycache__/
farm_out/          ← hasil run, bisa dibuat ulang
uc_profile/        ← browser profile, besar dan disposable
```

---

## 10. Anggaran Kredit

Rumus:

```
kredit_per_akun ≈ (1 - cache_hit_rate) × 1
```

Dengan hit rate 13%:

```
1 akun = 0.87 kredit
50 akun = ~44 kredit
```

Kalau hit rate turun ke 5% (Shopee rotasi besar):

```
1 akun = 0.95 kredit
50 akun = ~48 kredit
```

Lihat kebutuhan sebelum run:

```bash
python3 -c "
import json, glob
f = sorted(glob.glob('farm_out/plan_*.json'))[-1]
p = json.load(open(f))
print('kredit dibutuhkan:', p['estimated_credits'])
"
```

---

## 11. Batas Aman

| Parameter | Aman | Bahaya |
|---|---|---|
| `concurrency` | 1–2 | ≥ 5 |
| akun/jam | 2–4 | ≥ 10 |
| akun/hari | 50 | > 100 |
| jeda antar akun | 10–30 menit | < 5 menit |
| proxy per worker | 1 | 1 proxy untuk 2+ |
| RAM tersedia | ≥ 2 GB | < 1 GB |

Melewati batas ini tidak langsung gagal — tapi akun mulai kena `limit`
tanpa alasan jelas, dan itu lebih mahal daripada menunggu.

---

## 12. Checklist Harian

```
[ ] Key alive >= 2
[ ] Kredit >= 20
[ ] Proxy sehat >= 1 per worker
[ ] Cache hit rate dicek
[ ] Prefix block rate dicek
[ ] Plan direview sebelum run
[ ] Log tail dipantau saat run
[ ] Hasil run dicatat (ready/limit/failed)
[ ] Backup sebelum perubahan besar
```
