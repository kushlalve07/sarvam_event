# 🏏 Gully Commentator

Say what just happened in a mohalla cricket match — in Hindi, Tamil or code-mixed
speech — and hear it back as a dramatic "gully-uncle" commentary line.

One user. One task. One flow:

```
voice clip ──▶ Saaras (STT) ──▶ Sarvam-105B (JSON) ──▶ Bulbul (TTS) ──▶ audio plays
   Saaras auto-detects the language, so there is no language dropdown.
```

Three Sarvam calls, in order. That's the entire app.

---

## Files

| File | What it is |
| --- | --- |
| `pipeline.py` | The whole flow: `transcribe()` → `commentate()` → `speak()`. The "gully uncle" persona lives in `SYSTEM_PROMPT`. |
| `app.py` | Minimal Streamlit page: record → transcript → commentary → audio. |
| `test_cli.py` | Test the flow on real clips from the terminal, without Streamlit. |
| `.env.example` | Copy to `.env` and drop in your key. `.env` is git-ignored. |
| `requirements.txt` | `sarvamai`, `streamlit`, `python-dotenv`. |

---

## Steps

### 0. Get a key (do this first, once)
Grab a key from your Sarvam dashboard. **Do not paste it anywhere but your own
machine.** The code reads it from the environment only — it never asks you for it.

### 1. Env var + `.gitignore`, before the first commit
```bash
cd gully-commentator
cp .env.example .env          # then edit .env and put your key in
# .env is already listed in .gitignore — confirm with:
git check-ignore .env && echo "good: .env is ignored"
```
Prefer a shell export instead of a file? `export SARVAM_API_KEY=...` also works.
If you use `.env`, load it (the app and CLI call `python-dotenv` if present — or
just `set -a; source .env; set +a`).

### 2. Install
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Prove each Sarvam call works on its own
This is the step people skip. Don't wire up the UI until the three calls are
known-good.

```bash
# Step 1 only — Saaras
python -c "import pipeline; t,l = pipeline.transcribe(open('sample.wav','rb').read()); print(l, '|', t)"

# Step 1+2 — add the commentary JSON
python -c "import pipeline; t,l = pipeline.transcribe(open('sample.wav','rb').read()); print(pipeline.commentate(t,l))"

# All three — and write the audio
python test_cli.py sample.wav
```

`test_cli.py` prints the transcript, the JSON fields, and writes
`sample.commentary.wav` next to your clip so you can listen.

### 4. Test with real input (record these yourself)
Record 3–4 clips and run them all through `test_cli.py`:
1. A clean Hinglish clip — e.g. *"Rahul ne header maara, 23rd minute, 1-0!"*
2. A clean Tamil clip — say the same kind of line in Tamil.
3. One clip **with crowd / room noise** (TV on, fan, people talking).
4. One clip where you **stumble or switch languages mid-sentence**.

Watch for: does Saaras pick the right language? Does the commentary come back in
*that* language and script (not English)? Is the noisy clip still usable? If the
noisy clip collapses, move closer to the mic — Saaras wants ~16 kHz mono and a
decent signal-to-noise ratio.

Save your best clean clip as `fallback/demo.wav` — the app offers it as a
pre-recorded fallback so a live demo can't die on a bad mic.

### 5. Run the app
```bash
streamlit run app.py
```
Browser opens. Record → **Commentate!** → read the transcript → hear the call.

---

## Demo script (10 minutes, matches the timeline)

| Minutes | What to do |
| --- | --- |
| 0–3 | `cp .env.example .env`, add key, `pip install -r requirements.txt`. |
| 3–8 | Run the Saaras one-liner on a recorded clip. Confirm the transcript + language. |
| 8–13 | Run the `commentate()` one-liner. Confirm the four JSON fields, commentary in the right language. |
| 13–17 | Run `test_cli.py` on a clip. Listen to the generated `.wav`. |
| 17–19 | `streamlit run app.py`. Record live, click Commentate, let it play. |
| Remaining | Run the noisy clip and the Tamil clip. Keep `fallback/demo.wav` loaded in case the mic hiccups. |

---

## Knobs worth knowing

- **Persona** — edit `SYSTEM_PROMPT` in `pipeline.py`. One string, no rebuild.
- **Voice** — `SPEAKER_BY_LANG` maps each language to a `bulbul:v3` speaker. For
  extra stadium energy on Hindi, set `SARVAM_TTS_MODEL=bulbul:v4-flash` and add
  `"hi-IN": "ratan_hi_sports"` to the map (v4-flash uses persona IDs like
  `ratan_hi_sports`, not short names like `shubh`).
- **Transcript style** — `SARVAM_STT_MODE`. Default `codemix` keeps English words
  in English and Indic words in native script; use `transcribe` for pure native
  script.
- **Model IDs** — `saaras:v3` (or `saaras:v4`), `sarvam-105b` (or
  `sarvam-105b-conversations`), `bulbul:v3`.

## Gotchas (these bite in a live demo)

- **REST audio cap is 30 seconds.** Gully clips are short, so this is fine — but a
  long recording will 422. Keep clips to a single moment.
- **`sarvamai` version matters.** On `sarvamai >= 0.1.29` the TTS argument is
  `language_code`; older versions used `target_language_code`. `requirements.txt`
  pins `>=0.1.29`, so you get the new name.
- **Bulbul speaker must match the model.** v3 short names (`shubh`) and v4-flash
  persona IDs (`ratan_hi_sports`) are not interchangeable — a mismatch is a 400.
- **Keep the key in the env.** The code has no parameter for it and never logs it.
