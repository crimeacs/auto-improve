# auto-improve: voice notes

The same idea as the text loop — mutate, judge with a separate model, keep only
verified wins — applied to **spoken delivery**. The words stay fixed; the loop improves
how the note *sounds*: it mutates the text-to-speech settings (and the model, and
inline emotion tags), renders a candidate clip, and an **audio model** scores it. Keeps
the takes that genuinely sound better, discards the rest.

> The text loop (`../improve.py`) makes the *words* sharper. This makes the *delivery*
> sound alive. Run both for a note that reads well and lands when spoken.

## What you get

- `improve_voice.py` — the delivery GAN (baseline → mutate → render → audio-judge → keep)
- `eval_voice.py` — the audio judge (Gemini multimodal scores the rendered mp3 against a rubric)
- `make_voice.py` — text → speech via ElevenLabs (also a standalone CLI)
- `criteria/voice-note.md` — the delivery rubric · `examples/voice-note.txt` — a sample script

## Setup

```bash
pip install requests
export ELEVENLABS_API_KEY=...   # https://elevenlabs.io/app/settings/api-keys  (paid; TTS)
export GEMINI_API_KEY=...       # https://aistudio.google.com/apikey           (the audio judge)
```

## Run

```bash
cd voice
python3 improve_voice.py --max-iterations 4
afplay out/voice_baseline.mp3 ; afplay out/voice_improved.mp3   # before / after
```

It reads `examples/voice-note.txt` by default and writes:
- `out/voice_baseline.mp3` (before) and `out/voice_improved.mp3` (the champion)
- `out/voice_bundle.json` (the winning voice + settings)
- `results/voice-delivery.tsv` (the delivery climb)

## How it climbs

The "genome" is the voice itself — `{model, stability, similarity_boost, style, speed,
use_speaker_boost}` plus inline emotion tags. Each iteration re-reads the judge's
per-dimension feedback and pulls the single lever it implicates:

- **model upgrade** — the headline lever: swap the last-gen voice for a newer, more
  expressive one (the default targets ElevenLabs `eleven_v3`).
- **numeric settings** — lower stability for range, raise style for energy, etc.
- **emotion tags** (`eleven_v3`) — place `[excited]` / `[warmly]` / `[slow]` where a
  dimension is thin — a *semantic* lever the numeric knobs can't reach.

Each candidate is rendered and pairwise-judged against the champion (both orderings,
debiased) — kept only if it genuinely sounds better.

## Configuration

| env var | default | purpose |
|---|---|---|
| `ELEVENLABS_API_KEY` | — | **required** (TTS) |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | — | **required** (audio judge) |
| `VOICE_SCRIPT` | `examples/voice-note.txt` | the note to render + improve |
| `VOICE_RUBRIC` | `criteria/voice-note.md` | the delivery rubric |
| `VOICE_RESULTS` | `./results` | where the climb TSV is written |
| `ELEVEN_VOICE_ID` | a stock voice | which ElevenLabs voice |
| `ELEVEN_MODEL` / `ELEVEN_BASELINE_MODEL` | `eleven_v3` / `eleven_multilingual_v2` | upgrade target / baseline |

`make_voice.py` also works on its own: `python3 make_voice.py --text "Hello." --out hi.mp3`.
