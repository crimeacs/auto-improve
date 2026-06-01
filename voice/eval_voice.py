#!/usr/bin/env python3
"""
eval_voice.py — audio-aware evaluation for the voice auto-improve loop.

Two functions, reusing the verified-working Gemini call shapes from
/tmp/combined_eval_test.py (absolute) and /tmp/pairwise_test.py (pairwise):

  absolute_eval(mp3, script, rubric_path) -> dict
      One Gemini call: audio (inline_data audio/mpeg b64) + script text + rubric.
      Scores CONTENT (script vs rubric) and DELIVERY (audio: naturalness, pacing,
      energy, clarity, robotic-ness) separately, returns a combined JSON.

  pairwise_eval(champ_mp3, cand_mp3, champ_script, cand_script) -> dict
      One Gemini call: champion = Clip A, candidate = Clip B. The STABLE keep/discard
      gate — judges spoken delivery only (naturalness/pacing/energy/clarity/robotic).

Both: temperature 0, thinkingBudget 0, maxOutputTokens 2048, strip ```fences```,
429/503 retry with exponential backoff. Reads GEMINI_API_KEY (or GOOGLE_API_KEY)
from the environment.
"""
from __future__ import annotations
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def google_api_key() -> str:
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not k:
        raise SystemExit("Set GEMINI_API_KEY (https://aistudio.google.com/apikey)")
    return k


def _b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        # drop opening ```json / ``` and trailing ```
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _parse_json(text: str) -> dict:
    t = _strip_fences(text)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def _gemini(parts: list, max_tokens: int = 2048, retries: int = 5) -> str:
    """POST to generateContent with retry/backoff on 429/503. Returns raw text."""
    api_key = google_api_key()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.0,
            "thinkingConfig": {"thinkingBudget": 0},
            "maxOutputTokens": max_tokens,
        },
    }
    data = json.dumps(body).encode("utf-8")
    backoff = 2.0
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=180) as r:
                resp = json.load(r)
            cands = resp.get("candidates") or []
            if not cands:
                raise RuntimeError(f"no candidates: {json.dumps(resp)[:300]}")
            parts_out = cands[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts_out)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 503) and attempt < retries - 1:
                wait = backoff * (2 ** attempt)
                time.sleep(wait)
                continue
            # non-retryable or out of retries
            detail = e.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"Gemini HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            raise
    raise RuntimeError(f"Gemini call failed after {retries} retries: {last_err}")


def absolute_eval(mp3_path: str, script_text: str, rubric_path: str) -> dict:
    """One Gemini call: audio + script + rubric → content/delivery/combined scores."""
    rubric = ""
    if rubric_path and os.path.exists(rubric_path):
        rubric = Path(rubric_path).read_text(encoding="utf-8")

    prompt = f"""You are a strict judge of a spoken voice note. You are given BOTH the audio
and its exact script text. Score two things separately, then combine.

CONTENT (0-100): judge the SCRIPT TEXT against the rubric below.
DELIVERY (0-100): judge the AUDIO's spoken delivery only — naturalness, pacing,
energy, clarity, and human-vs-robotic. Ignore wording for the delivery score
(that's content). Also score each delivery sub-dimension 0-100.

Return ONLY JSON, no fences:
{{"content_score":<int>,"delivery_score":<int>,"combined_score":<int, round(0.6*content+0.4*delivery)>,
"naturalness":<int 0-100>,"pacing":<int 0-100>,"energy":<int 0-100>,"clarity":<int 0-100>,
"robotic_ness":<int 0-100, higher=MORE robotic/worse>,
"delivery_notes":"<1-2 sentences on the spoken delivery>",
"top_delivery_fix":"<one concrete voice-setting or pacing change>",
"top_content_fix":"<one concrete wording change>"}}

## RUBRIC
{rubric[:2500]}

## SCRIPT TEXT
{script_text}
"""
    parts = [
        {"inline_data": {"mime_type": "audio/mpeg", "data": _b64(mp3_path)}},
        {"text": prompt},
    ]
    raw = _gemini(parts, max_tokens=2048)
    out = _parse_json(raw)
    # normalize / fill defaults so callers never KeyError
    def _i(k, d=0):
        try:
            return int(round(float(out.get(k, d))))
        except (TypeError, ValueError):
            return d
    content = _i("content_score")
    delivery = _i("delivery_score")
    combined = out.get("combined_score")
    if combined is None:
        combined = round(0.6 * content + 0.4 * delivery)
    return {
        "content_score": content,
        "delivery_score": delivery,
        "combined_score": int(round(float(combined))),
        "naturalness": _i("naturalness"),
        "pacing": _i("pacing"),
        "energy": _i("energy"),
        "clarity": _i("clarity"),
        "robotic_ness": _i("robotic_ness"),
        "delivery_notes": str(out.get("delivery_notes", "")),
        "top_delivery_fix": str(out.get("top_delivery_fix", "")),
        "top_content_fix": str(out.get("top_content_fix", "")),
    }


def _pairwise_one(first_mp3: str, second_mp3: str) -> dict:
    """One raw Gemini pairwise call. 'first' is Clip A, 'second' is Clip B.

    Returns {delivery_winner: A|B|tie, content_winner, margin, why}.
    """
    prompt = (
        'You will hear TWO voice-note recordings of the SAME script: clip A then '
        'clip B. Judge ONLY the spoken DELIVERY — naturalness, pacing, energy, '
        'clarity, and human-vs-robotic. Ignore wording, accuracy, and content; '
        'the script text is identical in both. Listen to BOTH fully before '
        'deciding; do not favor a clip merely because it was played first. '
        'Decide which clip has the better-SOUNDING delivery.\n'
        'Return ONLY JSON, no fences: '
        '{"delivery_winner":"A"|"B"|"tie","content_winner":"A"|"B"|"tie",'
        '"margin":"clear"|"slight","why":"<<=12 words>"}'
    )
    parts = [
        {"text": "Clip A:"},
        {"inline_data": {"mime_type": "audio/mpeg", "data": _b64(first_mp3)}},
        {"text": "Clip B:"},
        {"inline_data": {"mime_type": "audio/mpeg", "data": _b64(second_mp3)}},
        {"text": prompt},
    ]
    raw = _gemini(parts, max_tokens=2048)
    out = _parse_json(raw)
    dw = str(out.get("delivery_winner", "tie")).strip().upper()
    dw = dw if dw in ("A", "B") else "tie"
    cw = str(out.get("content_winner", "tie")).strip().upper()
    cw = cw if cw in ("A", "B") else "tie"
    return {
        "delivery_winner": dw.lower() if dw == "TIE" else dw,
        "content_winner": cw.lower() if cw == "TIE" else cw,
        "margin": str(out.get("margin", "slight")).strip().lower() or "slight",
        "why": str(out.get("why", "")),
    }


def pairwise_eval(champ_mp3: str, cand_mp3: str,
                  champ_script: str = "", cand_script: str = "") -> dict:
    """Stable, position-debiased delivery gate. champion=Clip A, candidate=Clip B.

    The raw Gemini pairwise judge has a strong positional bias toward whichever
    clip is played first. So we run it BOTH orderings (champion-first and
    candidate-first), translate each verdict back to champion/candidate, and
    aggregate. The candidate is kept only when it wins the head-to-head net of
    position — it must win at least one ordering and not lose the other.

    Returns:
      overall: 'keep_challenger' | 'keep_champion'
      delivery_winner: 'A' | 'B' | 'tie'   (A=champion, B=candidate; net verdict)
      content_winner:  'A' | 'B' | 'tie'
      why: short string
      margin: 'clear' | 'slight'
    """
    # Pass 1: champion is A, candidate is B.
    p1 = _pairwise_one(champ_mp3, cand_mp3)
    cand_wins_1 = p1["delivery_winner"] == "B"
    champ_wins_1 = p1["delivery_winner"] == "A"

    # Pass 2: swap — candidate is A, champion is B.
    p2 = _pairwise_one(cand_mp3, champ_mp3)
    cand_wins_2 = p2["delivery_winner"] == "A"
    champ_wins_2 = p2["delivery_winner"] == "B"

    cand_votes = int(cand_wins_1) + int(cand_wins_2)
    champ_votes = int(champ_wins_1) + int(champ_wins_2)

    # Candidate kept iff it's net-better across positions: more votes than the
    # champion, AND it never outright loses both passes positionally.
    keep = cand_votes > champ_votes

    if cand_votes > champ_votes:
        net_winner = "B"  # candidate
    elif champ_votes > cand_votes:
        net_winner = "A"  # champion
    else:
        net_winner = "tie"

    # margin: 'clear' only if the winner took BOTH orderings.
    margin = "clear" if (cand_votes == 2 or champ_votes == 2) else "slight"

    # content winner: net across the two passes (B in pass1 == A in pass2 == candidate)
    cand_content = int(p1["content_winner"] == "B") + int(p2["content_winner"] == "A")
    champ_content = int(p1["content_winner"] == "A") + int(p2["content_winner"] == "B")
    content_winner = ("B" if cand_content > champ_content
                      else "A" if champ_content > cand_content else "tie")

    why = (p1["why"] if (keep and cand_wins_1) or (not keep and champ_wins_1)
           else p2["why"]) or p1["why"]
    why = (f"{why} [debiased: champ_votes={champ_votes} cand_votes={cand_votes}]")

    return {
        "overall": "keep_challenger" if keep else "keep_champion",
        "delivery_winner": net_winner,
        "content_winner": content_winner,
        "margin": margin,
        "why": why,
        "pass1": p1["delivery_winner"],
        "pass2_for_candidate": "win" if cand_wins_2 else (
            "loss" if champ_wins_2 else "tie"),
    }


if __name__ == "__main__":
    # standalone: score one clip against a rubric
    import argparse
    ap = argparse.ArgumentParser(description="Audio-judge one mp3 against a rubric")
    ap.add_argument("--mp3", required=True, help="audio clip to score")
    ap.add_argument("--script", required=True, help="the spoken text (transcript)")
    ap.add_argument("--rubric", required=True, help="markdown rubric")
    args = ap.parse_args()
    s = Path(args.script).read_text(encoding="utf-8").strip()
    print(json.dumps(absolute_eval(args.mp3, s, args.rubric), indent=2))
