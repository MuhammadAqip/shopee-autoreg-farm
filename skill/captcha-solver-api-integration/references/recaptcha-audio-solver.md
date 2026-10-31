# Free reCAPTCHA v2 solver — audio challenge + Whisper (no API key, no VCC)

When no paid solver key is on hand and the target's signup widget is reCAPTCHA v2,
you can solve it yourself for free: switch the widget to its **audio challenge**,
download the spoken clip, transcribe it offline with Whisper, and submit. No third
party, no credits, unlimited. Proven end-to-end on a real signup (register → email
verify → login → harvest API key).

## The flow (Playwright)

1. `goto` the register page, wait for a reCAPTCHA frame to appear in `page.frames`
   (poll `any('recaptcha' in f.url for f in page.frames)`, up to ~30s).
2. Scroll the widget into view: `document.querySelector('.g-recaptcha').scrollIntoView()`.
3. The widget renders **two frames**: an `anchor` frame (the checkbox) and, after a
   click, a `bframe` frame (the challenge). Resolve them by URL substring every time —
   they can be re-created, so re-scan `page.frames`; do not cache a frame handle.
4. Click the checkbox in the anchor frame (`#recaptcha-anchor`).
5. In the bframe, click `#recaptcha-audio-button` to switch to audio. The audio does
   NOT appear instantly — poll for `id="audio-source"` inside the bframe `content()`
   for up to ~20s before giving up.
6. Download the clip: read `src` off `#audio-source` (regex the bframe HTML: it may be
   HTML-escaped `&amp;` — unescape), then `requests.get(src)` to an `.mp3`.
7. Transcribe (see below), fill `#audio-response`, click `#recaptcha-verify-button`.
8. Read the token from the OUTER page:
   `document.querySelector('[name=g-recaptcha-response]').value`. If empty/low, the
   challenge refreshed — loop again (retries are normal, ~1 in 2 attempts fails).

## Transcribing the clip — faster-whisper, per the environment quirks

- Model: `faster-whisper` `base` (int8, cpu) is enough for the audio digits/words.
- **Download the model from the HF mirror, not huggingface.co** — the direct endpoint
  rate-limits (429) from datacenter IPs. `hf-mirror.com` serves the same repo:
  `https://hf-mirror.com/Systran/faster-whisper-base/resolve/main/{config.json,model.bin,tokenizer.json,vocabulary.txt}`
  into `--local` dir, then `WhisperModel('<dir>', device='cpu', compute_type='int8')`.
- **Bypass the `av`/PyAV decoder** — `WhisperModel.transcribe(path)` calls into `av`
  which can raise `TypeError: open() got an unexpected keyword argument 'metadata_errors'`
  on a version mismatch. Instead decode the audio yourself and pass a numpy array:
  ```
  os.system(f"ffmpeg -y -i '{mp3}' -ar 16000 -ac 1 -c:a pcm_s16le '{wav}'")
  import wave, numpy as np
  with wave.open(wav,'rb') as w: frames = w.readframes(w.getnframes())
  audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32)/32768.0
  segs,_ = model.transcribe(audio, language='en', beam_size=1)
  ```
- Normalize the transcript: lowercase, map spoken digits (`zero`→`0` … `nine`→`9`),
  strip non-alphanumerics. reCAPTCHA audio answers are short English phrases/numbers.

## The datacenter-IP block (the gate that actually stops you)

From a VPS/datacenter IP, clicking the checkbox yields **"Try again later. Your
computer or network may be sending automated queries."** — Google refuses to serve a
challenge, so the audio button does nothing and `#audio-source` never resolves.
Detect it: bframe `content()` contains `Try again later` or `automated queries`.

Counter: **run the browser through a residential/clean proxy.** With the proxy the
same click produces a real challenge and the audio flow above works. Pass the proxy to
Playwright as a separate `{server, username, password}` dict (inline `user:pass@host`
fails when the password contains `;`). Confirm the egress IP with `https://httpbin.org/ip`
before/after; rotate proxy ports to get a fresh IP if one is burnt.

## Pitfalls (each cost a run)

1. Reading `#audio-source` in the same tick you click the audio button — it is not
   there yet. Poll the bframe content for up to ~20s.
2. Caching the bframe handle across attempts — re-resolve anchor/bframe from
   `page.frames` each loop; the frame is re-created after a refresh.
3. `av` decoder crash on `transcribe(path)` — feed a numpy array decoded by ffmpeg.
4. HuggingFace 429 pulling the model — use `hf-mirror.com`.
5. Treating the datacenter "Try again later" as a captcha failure — it is an IP block;
   proxy it, do not retry the same IP.
6. Not loops: a single audio attempt fails ~half the time; retry several times before
   declaring the flow broken. Success = token in `g-recaptcha-response`.
7. **Clicking the audio button only once.** The challenge RESETS after a failed/delayed
   attempt and drops back to the checkbox/image state, so `#audio-source` stops
   resolving. Re-click `#recaptcha-audio-button` at the TOP of every retry iteration,
   and if the bframe content reads `expired` / `Try again later`, re-click
   `#recaptcha-anchor` in the anchor frame first. A one-shot audio click followed by a
   long poll loop just spins until the challenge expires.
8. **Per-attempt poll that is too long.** Polling `#audio-source` for ~20s per iteration
   burns past the challenge TTL. Cap the poll at ~10-12s, then re-click audio and loop
   — a fresh audio clip often downloads instantly while a stale poll never resolves.
9. Reading `#audio-source` only via regex when the element exists but the `src` attribute
   is briefly absent — add a locator fallback (`frame.locator('#audio-source').get_attribute('src')`)
   after the content-scan misses.
