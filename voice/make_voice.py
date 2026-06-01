#!/usr/bin/env python3
"""
make_voice.py — text → spoken audio (mp3) via ElevenLabs. Self-contained:
reads ELEVENLABS_API_KEY from env (no OpenClaw config needed).

Defaults to the newest, most expressive model — eleven_v3 — which interprets
inline audio tags ([excited], [whispers], [sighs], [slow], [warmly], …) for
semantic control over delivery. Falls back to eleven_multilingual_v2 automatically
if v3 errors (e.g. transient unavailability), so the demo never hard-fails.

Exposes the full advanced settings surface so the auto-improve voice GAN can
anneal them: stability / similarity_boost / style / use_speaker_boost / speed,
plus a deterministic `seed` (so a re-synth of the same settings is reproducible
— a fair A/B for the judge), output_format, and text-normalization mode.

Usage:
  python3 make_voice.py --text-file workspace/voice_script.txt --out cache/baseline.mp3
  python3 make_voice.py --text "[excited] Big news. [warmly] Here's why it matters." --out cache/t.mp3
  python3 make_voice.py --list-voices          # pick a voice_id
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
import urllib.request, urllib.error

# A calm, natural narration voice as the default (ElevenLabs stock "Adam").
DEFAULT_VOICE = os.environ.get("ELEVEN_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
# Newest / most expressive model (supports inline audio tags). Env-overridable.
DEFAULT_MODEL = os.environ.get("ELEVEN_MODEL", "eleven_v3")
# Robust fallback if the primary model errors mid-demo.
FALLBACK_MODEL = os.environ.get("ELEVEN_FALLBACK_MODEL", "eleven_multilingual_v2")
DEFAULT_OUTPUT_FORMAT = os.environ.get("ELEVEN_OUTPUT_FORMAT", "mp3_44100_192")


def api_key() -> str:
    k = os.environ.get("ELEVENLABS_API_KEY")
    if not k:
        raise SystemExit("Set ELEVENLABS_API_KEY (https://elevenlabs.io/app/settings/api-keys)")
    return k


def list_voices() -> int:
    req = urllib.request.Request("https://api.elevenlabs.io/v1/voices",
                                 headers={"xi-api-key": api_key()})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    for v in data.get("voices", []):
        labels = v.get("labels", {})
        desc = ", ".join(f"{k}={val}" for k, val in labels.items() if val)
        print(f"  {v['voice_id']}  {v['name']:<18}  {desc}")
    return 0


def _post_tts(text: str, out: Path, voice_id: str, model: str,
              voice_settings: dict, *, seed: int | None,
              output_format: str, text_normalization: str,
              previous_text: str | None, next_text: str | None) -> int:
    """Single TTS POST. Returns bytes written. Raises urllib HTTPError on failure."""
    payload: dict = {"text": text, "model_id": model, "voice_settings": voice_settings}
    if seed is not None:
        payload["seed"] = seed
    if text_normalization and text_normalization != "auto":
        payload["apply_text_normalization"] = text_normalization
    if previous_text:
        payload["previous_text"] = previous_text
    if next_text:
        payload["next_text"] = next_text

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format={output_format}"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "audio/mpeg", "Content-Type": "application/json",
                 "xi-api-key": api_key()}, method="POST")
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with urllib.request.urlopen(req, timeout=120) as resp, open(out, "wb") as f:
        while (chunk := resp.read(8192)):
            f.write(chunk); n += len(chunk)
    return n


def synthesize(text: str, out: Path, voice_id: str, model: str, *,
               stability: float = 0.45, similarity_boost: float = 0.80,
               style: float = 0.30, use_speaker_boost: bool = True,
               speed: float = 1.0, seed: int | None = None,
               output_format: str = DEFAULT_OUTPUT_FORMAT,
               text_normalization: str = "auto",
               previous_text: str | None = None,
               next_text: str | None = None) -> dict:
    voice_settings = {
        "stability": stability,
        "similarity_boost": similarity_boost,
        "style": style,
        "use_speaker_boost": use_speaker_boost,
        "speed": speed,
    }
    used_model = model
    downgraded = False
    try:
        nbytes = _post_tts(text, out, voice_id, model, voice_settings, seed=seed,
                           output_format=output_format, text_normalization=text_normalization,
                           previous_text=previous_text, next_text=next_text)
    except urllib.error.HTTPError as e:
        # Auto-downgrade to the robust model on a primary-model error (keeps the demo alive).
        if model != FALLBACK_MODEL:
            body = e.read().decode("utf-8", "replace")[:200]
            print(f"⚠ {model} → HTTP {e.code} ({body}); retrying on {FALLBACK_MODEL}", file=sys.stderr)
            used_model, downgraded = FALLBACK_MODEL, True
            nbytes = _post_tts(text, out, voice_id, FALLBACK_MODEL, voice_settings, seed=seed,
                               output_format=output_format, text_normalization=text_normalization,
                               previous_text=previous_text, next_text=next_text)
        else:
            raise
    return {"ok": True, "out": str(out), "bytes": nbytes, "voice_id": voice_id,
            "model": used_model, "downgraded_from": model if downgraded else None,
            "chars": len(text), "settings": voice_settings, "seed": seed,
            "output_format": output_format}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text-file")
    ap.add_argument("--text")
    ap.add_argument("--out")
    ap.add_argument("--voice-id", default=DEFAULT_VOICE)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--list-voices", action="store_true")
    # Advanced voice settings (the GAN's knobs).
    ap.add_argument("--stability", type=float, default=0.45)
    ap.add_argument("--similarity", type=float, default=0.80)
    ap.add_argument("--style", type=float, default=0.30)
    ap.add_argument("--speed", type=float, default=1.0)
    boost = ap.add_mutually_exclusive_group()
    boost.add_argument("--speaker-boost", dest="speaker_boost", action="store_true", default=True)
    boost.add_argument("--no-speaker-boost", dest="speaker_boost", action="store_false")
    ap.add_argument("--seed", type=int, default=None, help="0..4294967295 for reproducible synthesis")
    ap.add_argument("--output-format", default=DEFAULT_OUTPUT_FORMAT)
    ap.add_argument("--text-normalization", choices=["auto", "on", "off"], default="auto")
    args = ap.parse_args()

    if args.list_voices:
        return list_voices()
    if not args.out or not (args.text or args.text_file):
        ap.error("need --out and one of --text/--text-file")
    text = args.text or Path(args.text_file).read_text(encoding="utf-8").strip()
    try:
        info = synthesize(text, Path(args.out), args.voice_id, args.model,
                          stability=args.stability, similarity_boost=args.similarity,
                          style=args.style, use_speaker_boost=args.speaker_boost,
                          speed=args.speed, seed=args.seed,
                          output_format=args.output_format,
                          text_normalization=args.text_normalization)
        print(json.dumps(info, indent=2))
        return 0
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        print(json.dumps({"ok": False, "error": f"HTTP {e.code}",
                          "body": e.read().decode("utf-8", "replace")[:400]}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
