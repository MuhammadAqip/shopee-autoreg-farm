# Backing up a farm so it survives the host disappearing

When the operator wants an offline copy of a long-running farm project ("if the VPS
dies I still have it"), the deliverable is a single self-describing bundle, not a raw
tarball of the working dir. A bare `tar czf` of the project misses the pieces that make
it RUNNABLE elsewhere.

## What MUST be in the bundle (beyond the code)

- The systemd unit(s) — copy the live `/etc/systemd/system/<svc>.service` into the
  project before archiving. Without it the restore has no service definition.
- A cron dump — `crontab -l > crontab_backup.txt` inside the project. The unattended
  jobs (key watchdog, cache prewarm, production run) are the thing that keeps a farm
  alive; they are invisible in the project tree otherwise.
- The credential files the runtime reads (`.bot.env`, the solver key file, the key DB,
  the account DB). The bundle is useless without them, but they are SECRETS — see below.
- A `RESTORE_GUIDE.md` written INTO the archive: extract step, python/venv + system
  deps (`xvfb`, `playwright install chromium`), the interpreter path used
  (`/root/sniffenv/bin/python`), restore of the systemd unit + `crontab`, and a smoke
  test per component (`key_manager.py`, `captcha_cache.py stats`, `systemctl status`).

## Exclude the regenerable junk

`--exclude='*/__pycache__'`, `--exclude='<proj>/uc_profile'` (browser profile: hundreds
of MB, fully regenerable), and the SQLite sidecar files `*.db-wal` / `*.db-shm` (the
main `.db` carries the data; sidecars are transient). A browser user-data-dir alone can
be 12MB+ of churn.

## Split-archive distribution (when the transfer medium caps file size)

A chat/messaging upload or a drive folder may reject a 140MB file. Split by SIZE into a
fixed number of parts, then verify:

```bash
SZ=$(stat -c%s "$ZIP"); B=$(( (SZ + N - 1) / N ))   # N = desired part count
split -b "$B" -d -a 1 "$ZIP" "${ZIP%.zip}.part"    # -> .part0 .part1 .part2
md5sum "$ZIP"                                        # the integrity anchor
```

- Compute the part size from the desired COUNT (`total / N`), not a fixed 40MB — the
  operator's ask is usually "3 files", and a fixed byte-size silently yields 4 parts.
- **Size the parts BELOW the medium's real cap, not just at the requested count.**
  Telegram's bot-API document limit is nominally 50MB but a ~47MB part (a 140MB/3 split)
  is rejected at delivery (`Couldn't deliver the file attachment`). Repack to a safe
  margin — a ~36MB part (4 parts) delivered fine where 47MB failed. When the operator
  says "3 files" but 3 parts lands too close to the cap, prefer MORE, smaller parts over
  a failing send; tell them why the count changed.
- **Check the split math BEFORE spending the upload.** `141MB / 3 = 47MB`, over the safe
  cap → go to 4. Do the division first instead of discovering it at the send.
- Print the md5 of the WHOLE archive and keep it in the message. After the operator
  rejoins (`cat *.part* > x.zip` on Linux/Mac, `copy /b p0+p1+p2 x.zip` on Windows)
  they verify `md5sum x.zip` matches — a truncated/reordered part set is otherwise
  indistinguishable from a good one.
- VERIFY the split round-trips before sending: `cat part* > /tmp/rejoin && md5sum`
  must equal the original md5. Do this in the same session, not on trust.

## Hosting a SINGLE un-split archive when the operator asks for one file

When the operator overrides the split and wants "one file on a host", use a file-drop
service and upload the archive WHOLE (no split). Verified working recipe:

```bash
# filebin.net — one PUT per file, filename in the URL, returns HTTP 201
curl -s -X PUT -H "Content-Type: application/octet-stream" \
     --data-binary "@backup.zip" \
     "https://filebin.net/<bin-slug>/backup.zip"
# verify size came through intact, then hand over the bin page + direct URL
curl -s -H "Accept: application/json" "https://filebin.net/<bin-slug>"
```

- **`PUT`, not `POST`.** A `POST` to the bin root returns `400 Bad Request`; the file
  goes in with `PUT` to `/<bin>/<filename>`. Success is `HTTP 201`.
- **A bare `curl https://host` returning `HTTP 000` = the host is dead, not a syntax
  error.** Probe several drop hosts up front (`curl -s -o /dev/null -w '%{http_code}'
  https://host`); pick a live one. `0x0.st` and `transfer.sh` were down while
  `filebin.net` and `temp.sh` answered 200. `temp.sh` takes `-F "file=@x" .../upload`.
- **Verify the upload landed at full size** before reporting: re-read the bin as JSON and
  compare `bytes` to the local `stat -c%s`. A 201 with a truncated body is possible.
- **Drop hosts auto-expire** (filebin ~7 days, temp.sh ~3 days). State the retention
  window to the operator so they download into permanent storage.

## Credentials in the bundle — say it out loud

A complete backup necessarily includes the bot token, solver API keys, proxy lists,
and the account DB. That makes the archive itself sensitive. State this plainly to the
operator when delivering ("keep this on a private drive; it contains live credentials —
if it leaks, rotate everything") — do not hand over a credential-bearing archive as if
it were inert source code. Scrubbing creds out would make the backup non-restorable, so
the correct move is complete archive + explicit handling note, not a redacted one.

## Backup vs the existing portable-bundle path

The `ROOT`-env-var + `requirements.txt` + `install.sh` work (SKILL.md) is for shipping a
CLEAN, secret-free bundle to a NEW operator. This is the complementary case: an exact
snapshot of a RUNNING system, secrets and all, for disaster recovery by the same
operator. Same project, different intent — do not conflate them.
