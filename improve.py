#!/usr/bin/env python3
"""
Auto-Improve v2: Informed GAN-style iterative improvement.
Inspired by Karpathy's autoresearch — mutations are informed by evaluator feedback,
output as diffs (not full rewrites), and evaluation is averaged for stability.

Usage:
  python3 improve.py --artifact FILE --criteria RUBRIC --tag NAME [--max-iterations N]
  python3 improve.py --status --tag NAME
"""

import argparse
import datetime
import difflib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.environ.get("RESULTS_DIR") or os.path.join(SCRIPT_DIR, "results")

# Canonicalization map for the crash-proof apply ladder: curly quotes -> straight,
# em/en/minus dashes -> hyphen, the various unicode spaces -> ascii space, ellipsis.
_QUOTE_MAP = {
    "‘": "'", "’": "'", "‛": "'",
    "“": '"', "”": '"', "‟": '"',
    "–": "-", "—": "-", "−": "-",
    " ": " ", " ": " ", " ": " ",
    "…": "...",
}


def _canon(s):
    """NFKC + curly->straight quotes + dashes->hyphen + spaces->space + collapse runs."""
    s = unicodedata.normalize("NFKC", s)
    for k, v in _QUOTE_MAP.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s).strip()

# Optional event hook: set IMPROVE_EVENTS_LOG=<path> to append run events as JSONL
# (handy for dashboards / tracking). No-op otherwise. Never raises.
def _emit_event(event_name, **details):
    path = os.environ.get("IMPROVE_EVENTS_LOG")
    if not path:
        return
    try:
        ev = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
              "event": event_name, **details}
        with open(os.path.expanduser(path), "a") as f:
            f.write(json.dumps(ev) + "\n")
    except Exception:
        pass  # never crash on event emission


MUTATOR_MODEL = os.environ.get("IMPROVE_MUTATOR", "gemini-flash-latest")
EVALUATOR_MODEL = os.environ.get("IMPROVE_EVALUATOR", "gemini-flash-latest")


def run(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=60)
    return r.stdout.strip()

def git(cmd, cwd=None):
    return run(f"git {cmd}", cwd=cwd)

def read_file(path):
    with open(path) as f:
        return f.read()

def write_file(path, content):
    with open(path, "w") as f:
        f.write(content)


def get_api_key():
    """Gemini API key from the environment (GEMINI_API_KEY or GOOGLE_API_KEY).
    Get one free at https://aistudio.google.com/apikey."""
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def llm_call(prompt, temperature=0.7, max_retries=3):
    """Single Gemini API call with retry on 503/429."""
    api_key = get_api_key()
    if not api_key:
        print("  No API key found", file=sys.stderr)
        return None
    import requests
    model = os.environ.get("IMPROVE_MUTATOR", "gemini-flash-latest")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "thinkingConfig": {"thinkingBudget": 0},  # the thinking tax was ~10s/call
            "maxOutputTokens": 8192,
        },
    }
    for attempt in range(max_retries):
        try:
            r = requests.post(url, json=body, timeout=120)
            if r.status_code == 200:
                data = r.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            elif r.status_code in (429, 503):
                wait = (attempt + 1) * 15
                print(f"  API {r.status_code}, retrying in {wait}s (attempt {attempt+1}/{max_retries})", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"  API error {r.status_code}: {r.text[:200]}", file=sys.stderr)
                return None
        except Exception as e:
            print(f"  API exception: {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(10)
    return None


def _gemini_json(prompt, max_retries=3):
    """Deterministic Gemini call (temp=0, thinkingBudget=0) returning parsed JSON.

    Used by the pairwise text judge — mirrors eval_voice's call shape. Returns {}
    on any failure so the gate degrades gracefully (never raises)."""
    api_key = get_api_key()
    if not api_key:
        print("  No API key found", file=sys.stderr)
        return {}
    import requests
    model = os.environ.get("IMPROVE_EVALUATOR", "gemini-flash-latest")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "thinkingConfig": {"thinkingBudget": 0},
            "maxOutputTokens": 2048,
        },
    }
    for attempt in range(max_retries):
        try:
            r = requests.post(url, json=body, timeout=120)
            if r.status_code == 200:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text.startswith("```"):
                    text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", text)
                    text = re.sub(r"\s*```\s*$", "", text).strip()
                try:
                    return json.loads(text)
                except Exception:
                    m = re.search(r"\{.*\}", text, re.DOTALL)
                    return json.loads(m.group(0)) if m else {}
            elif r.status_code in (429, 503):
                time.sleep((attempt + 1) * 15)
            else:
                print(f"  API error {r.status_code}: {r.text[:200]}", file=sys.stderr)
                return {}
        except Exception as e:
            print(f"  API exception: {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(10)
    return {}


# ── EVALUATE ──────────────────────────────────────────────────────────────

def evaluate_once(artifact_content, criteria_content):
    """Single evaluation pass. Returns (score, breakdown_json_str)."""
    prompt = f"""You are a STRICT quality evaluator. Score this artifact against the rubric.
Be critical — 50 is average, 70 is good, 90 is exceptional. Do not inflate.

Return ONLY valid JSON:
{{
  "total_score": <int 0-100>,
  "dimensions": {{
    "<name>": {{"score": <int>, "max": <int>, "note": "<why>", "weakest_element": "<specific thing to fix>"}},
    ...
  }},
  "top_improvement": "<the single most impactful change to make next>"
}}

## RUBRIC
{criteria_content[:3000]}

## ARTIFACT
{artifact_content[:12000]}"""

    response = llm_call(prompt, temperature=0.0)  # deterministic
    if not response:
        return 0, "{}"

    text = response.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        data = json.loads(text)
        return int(data.get("total_score", 0)), json.dumps(data, indent=2)
    except Exception:
        m = re.search(r'"total_score"\s*:\s*(\d+)', text)
        if m:
            return int(m.group(1)), text
        return 0, text[:500]


def evaluate(artifact_content, criteria_content, runs=2):
    """Average N evaluation passes for stability. Returns (avg_score, best_breakdown)."""
    scores = []
    best_breakdown = ""
    for i in range(runs):
        score, breakdown = evaluate_once(artifact_content, criteria_content)
        scores.append(score)
        if not best_breakdown or score >= max(scores[:-1], default=0):
            best_breakdown = breakdown
        if i < runs - 1:
            time.sleep(2)

    avg = round(sum(scores) / len(scores))
    spread = max(scores) - min(scores)
    if spread > 10:
        print(f"  [eval] Scores: {scores} (spread: {spread} — noisy)")
    return avg, best_breakdown


# ── MUTATE (best-of-N) ──────────────────────────────────────────────────

def mutate_candidates(artifact_content, criteria_content, eval_breakdown,
                      results_history, n=3):
    """Generate N distinct candidate mutations in ONE call. Returns a list of
    (find, replace, description); [] on API/parse failure."""
    prompt = f"""You are an expert improver. Read the EVALUATOR FEEDBACK and
propose {n} DISTINCT, small, surgical find/replace mutations — each targeting a
DIFFERENT weak dimension or element. Each must be a few lines, not a rewrite.

Output EXACTLY {n} candidates in this format (no prose between them):

===CANDIDATE 1===
---FIND---
<exact text from the artifact — copy verbatim, enough context to be unique>
---REPLACE---
<replacement>
---DESCRIPTION---
<one line: what changed, which dimension, why>
===CANDIDATE 2===
... (and so on through {n})

## EVALUATOR FEEDBACK (target the lowest scores)
{eval_breakdown[:2000]}

## PREVIOUS ATTEMPTS (do not repeat failed ideas)
{results_history[:1000]}

## CRITERIA SUMMARY
{criteria_content[:1500]}

## ARTIFACT (first 8000 chars)
{artifact_content[:8000]}"""
    response = llm_call(prompt, temperature=0.9)  # higher temp -> diverse draws
    if not response:
        return []
    return _parse_candidates(response.strip())


# The mutate-block delimiters. If one ends up inside a captured FIND or REPLACE, the
# block was ambiguous (the model echoed a marker, or the artifact itself contains the
# token) — splicing it would corrupt the file, so we drop that candidate.
_DELIMS = ("---FIND---", "---REPLACE---", "---DESCRIPTION---", "===CANDIDATE")


def _parse_candidates(text):
    """Parse the ===CANDIDATE n=== blocks. Backward-compatible: a single
    un-delimited FIND/REPLACE block parses as one candidate."""
    out = []
    for block in re.split(r'===\s*CANDIDATE[^\n]*===', text):
        fm = re.search(r'---FIND---\s*\n(.*?)\n---REPLACE---', block, re.DOTALL)
        rm = re.search(r'---REPLACE---\s*\n(.*?)\n---DESCRIPTION---', block, re.DOTALL)
        dm = re.search(r'---DESCRIPTION---\s*\n(.*?)(?=\n===|\Z)', block, re.DOTALL)
        if fm and rm and fm.group(1).strip():
            find, replace = fm.group(1).strip(), rm.group(1).strip()
            if any(d in find or d in replace for d in _DELIMS):
                continue  # ambiguous block — never splice a delimiter into the artifact
            desc = dm.group(1).strip().split("\n")[0] if dm else "no description"
            out.append((find, replace, desc))
    return out


# ── APPLY (crash-proof ladder) ──────────────────────────────────────────────

def apply_diff(content, find_text, replace_text):
    """Apply a find/replace diff via a 3-rung ladder.

    Returns (new_content, how) on success or (None, reason) on failure.
    NEVER raises on bad input — a malformed/absent FIND yields a clean
    (None, reason) instead of crashing or corrupting the file."""
    if not find_text:
        return None, "empty-find"
    # belt-and-suspenders: never introduce a parser delimiter that wasn't already there
    if any(d in replace_text and d not in content for d in _DELIMS):
        return None, "delimiter-in-replace"
    if find_text in content:                                   # 1) exact
        return content.replace(find_text, replace_text, 1), "exact"
    cfind = _canon(find_text)                                  # 2) canonicalized
    if cfind:
        span = _canon_substring_span(content, cfind)
        if span:
            lo, hi = span
            return content[:lo] + replace_text + content[hi:], "canon"
    span = _fuzzy_span(content, find_text)                     # 3) fuzzy block
    if span:
        lo, hi = span
        return content[:lo] + replace_text + content[hi:], "fuzzy"
    return None, "not-found"


def _canon_substring_span(content, cfind):
    """Find cfind (a canonicalized string) inside content, mapping the match
    back to RAW byte offsets so the splice is byte-exact. Returns (lo, hi) or None."""
    canon_chars, raw_index, pending = [], [], False
    for i, ch in enumerate(content):
        norm = unicodedata.normalize("NFKC", ch)
        for k, v in _QUOTE_MAP.items():
            norm = norm.replace(k, v)
        for c in norm:
            if c.isspace():
                pending = True
            else:
                if pending and canon_chars:
                    canon_chars.append(" "); raw_index.append(i); pending = False
                canon_chars.append(c); raw_index.append(i)
    pos = "".join(canon_chars).find(cfind)
    if pos < 0:
        return None
    lo = raw_index[pos]
    last = raw_index[pos + len(cfind) - 1]
    hi = last + 1
    while hi < len(content) and _canon(content[lo:hi]) != cfind:
        hi += 1
        if hi - last > 4:
            hi = last + 1
            break
    return lo, hi


def _fuzzy_span(content, find_text, threshold=0.8):
    """Word-anchored sliding-window fuzzy match. Accept ratio >=threshold,
    early-out at >=0.97. Returns (lo, hi) raw offsets or None."""
    cfind = _canon(find_text)
    tw = max(1, len(cfind.split()))
    words = [(m.start(), m.end()) for m in re.finditer(r"\S+", content)]
    if not words:
        return None
    best_r, best = 0.0, None
    for wl in {tw, tw + 1, tw + 2, max(1, tw - 1), max(1, tw - 2)}:
        for s in range(0, len(words) - wl + 1):
            lo, hi = words[s][0], words[s + wl - 1][1]
            r = difflib.SequenceMatcher(None, cfind, _canon(content[lo:hi])).ratio()
            if r > best_r:
                best_r, best = r, (lo, hi)
        if best_r >= 0.97:
            break
    return best if (best and best_r >= threshold) else None


# ── PAIRWISE TEXT GATE (mirrors eval_voice.pairwise_eval) ────────────────────

def _pairwise_text_one(first_text, second_text, criteria):
    """One ordering: version A=first_text, B=second_text. Returns A|B|tie."""
    prompt = (
        "You are a strict judge. Read TWO versions of the same artifact "
        "(version A then version B) and a RUBRIC. Decide which is genuinely "
        "BETTER against the rubric. Judge quality only; do not favor a version "
        "because it appears first. If equivalent, answer tie.\n"
        'Return ONLY JSON, no fences: '
        '{"winner":"A"|"B"|"tie","margin":"clear"|"slight","why":"<<=15 words>"}\n\n'
        f"## RUBRIC\n{criteria[:2500]}\n\n"
        f"## VERSION A\n{first_text[:8000]}\n\n## VERSION B\n{second_text[:8000]}\n")
    out = _gemini_json(prompt)               # temp=0, thinkingBudget=0
    w = str(out.get("winner", "tie")).strip().upper()
    w = w if w in ("A", "B") else "tie"
    return {"winner": w, "margin": str(out.get("margin", "slight")).lower(),
            "why": str(out.get("why", ""))}


def pairwise_text_eval(champ_text, cand_text, criteria):
    """champion=A, candidate=B. Two orderings cancel position bias.
    keep iff candidate nets more votes than champion."""
    p1 = _pairwise_text_one(champ_text, cand_text, criteria)   # champ=A cand=B
    p2 = _pairwise_text_one(cand_text, champ_text, criteria)   # cand=A champ=B
    cand_votes = int(p1["winner"] == "B") + int(p2["winner"] == "A")
    champ_votes = int(p1["winner"] == "A") + int(p2["winner"] == "B")
    keep = cand_votes > champ_votes
    why = (p1["why"] if (keep and p1["winner"] == "B") else p2["why"]) or p1["why"]
    return {"overall": "keep_challenger" if keep else "keep_champion",
            "margin": "clear" if (cand_votes == 2 or champ_votes == 2) else "slight",
            "why": f"{why} [champ={champ_votes} cand={cand_votes}]"}


# ── LOGGING ───────────────────────────────────────────────────────────────

def log_result(results_file, iteration, commit, score, delta, status, description):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
    # Truncate at the start of each run (the baseline row) so re-running the same
    # --tag never piles multiple runs into one file (which made the climb chart
    # connect run N's end back to run N+1's baseline — a crossing line).
    fresh = status == "baseline" or not os.path.exists(results_file)
    with open(results_file, "w" if fresh else "a") as f:
        if fresh:
            f.write("iteration\tcommit\tscore\tdelta\tstatus\tdescription\ttimestamp\n")
        desc_clean = description.replace("\t", " ").replace("\n", " ")[:200]
        f.write(f"{iteration}\t{commit}\t{score}\t{delta:+d}\t{status}\t{desc_clean}\t{timestamp}\n")


def read_results(results_file):
    """Read results.tsv as formatted history string."""
    if not os.path.exists(results_file):
        return "No previous results."
    with open(results_file) as f:
        lines = f.readlines()
    return "".join(lines[-10:])  # last 10 entries


def show_status(tag):
    results_file = os.path.join(RESULTS_DIR, f"{tag}.tsv")
    if not os.path.exists(results_file):
        print(f"No results for '{tag}'")
        return
    with open(results_file) as f:
        lines = f.readlines()
    print(f"=== Auto-Improve: {tag} ===")
    keeps = sum(1 for l in lines[1:] if "\tkeep\t" in l)
    discards = sum(1 for l in lines[1:] if "\tdiscard\t" in l)
    crashes = sum(1 for l in lines[1:] if "\tcrash\t" in l)
    scores = []
    for l in lines[1:]:
        parts = l.strip().split("\t")
        if len(parts) >= 3:
            try: scores.append(int(parts[2]))
            except Exception: pass
    best = max(scores) if scores else 0
    print(f"Iterations: {len(lines)-1} | Keeps: {keeps} | Discards: {discards} | Crashes: {crashes}")
    print(f"Best score: {best}")
    print("\nResults:")
    for l in lines:
        print(f"  {l.strip()}")


# ── MAIN LOOP ─────────────────────────────────────────────────────────────

def generate_rubric(artifact_content, goal=None):
    """Infer a quality rubric for an artifact when the user didn't supply one.
    Returns markdown (weighted dimensions summing to 100), or None on failure."""
    goal_line = f"\nThe author's goal for it: {goal}\n" if goal else ""
    prompt = f"""You are an expert editor. Read the artifact below, decide what KIND of
thing it is (email, code/API, blog post, prompt, spec, config, etc.) and what
"excellent" means for that kind, then write the QUALITY RUBRIC a great version would be
judged against.
{goal_line}
Output ONLY a markdown rubric in EXACTLY this shape — no preamble, no code fence:

# <Artifact Type> — Quality Criteria

Anchors: 50 = average, 70 = good, 90+ = exceptional. Reward craft, not length.

## Dimensions (total: 100)

### <Dimension> (N points)
- <a specific thing that earns the points> (0-X)

Rules: 5-7 dimensions; the point values in the "### (N points)" headings MUST sum to
exactly 100; each dimension specific, independent, and reward-framed ("award N when
X"); tailored to THIS artifact, not generic boilerplate.

## ARTIFACT
{artifact_content[:6000]}"""
    out = llm_call(prompt, temperature=0.4)
    if not out:
        return None
    out = out.strip()
    if out.startswith("```"):
        out = re.sub(r"^```[a-zA-Z]*\s*", "", out)
        out = re.sub(r"\s*```\s*$", "", out).strip()
    return out


def main():
    parser = argparse.ArgumentParser(description="Auto-Improve v2: Informed GAN-style improvement")
    parser.add_argument("--artifact", help="Path to file to improve")
    parser.add_argument("--criteria", help="Path to evaluation rubric (.md). Optional — "
                        "if omitted, auto-improve infers one from the artifact.")
    parser.add_argument("--goal", help="Optional one-line intent to steer the auto-generated "
                        'rubric, e.g. "a cold email that books a meeting"')
    parser.add_argument("--tag", required=True, help="Run identifier (branch: improve/<tag>)")
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--threshold", type=int, default=90)
    parser.add_argument("--eval-runs", type=int, default=2, help="Number of eval passes to average")
    parser.add_argument("--candidates", type=int, default=3,
                        help="candidate mutations generated per iteration (best-of-N)")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.status:
        show_status(args.tag)
        return

    if not args.artifact:
        parser.error("--artifact required")

    artifact_path = os.path.abspath(args.artifact)
    criteria_path = os.path.abspath(args.criteria) if args.criteria else None
    repo_root = os.path.dirname(artifact_path)

    # Walk up to find git root
    d = repo_root
    while d != "/":
        if os.path.isdir(os.path.join(d, ".git")):
            repo_root = d
            break
        d = os.path.dirname(d)

    os.chdir(repo_root)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    results_file = os.path.join(RESULTS_DIR, f"{args.tag}.tsv")
    branch = f"improve/{args.tag}"
    rel_path = os.path.relpath(artifact_path, repo_root)

    print("╔══════════════════════════════════════════════╗")
    print("║      AUTO-IMPROVE v2 (Informed GAN Loop)     ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║ Artifact:  {rel_path[:34]:<34s} ║")
    print(f"║ Branch:    {branch[:34]:<34s} ║")
    print(f"║ Eval runs: {args.eval_runs:<34d} ║")
    print(f"║ Max iters: {args.max_iterations:<34d} ║")
    print(f"║ Threshold: {args.threshold:<34d} ║")
    print("╚══════════════════════════════════════════════╝\n")

    # ── Setup branch ──
    existing = git(f"branch --list {branch}")
    if existing.strip():
        git(f"checkout {branch}")
    else:
        git("add -A")
        git(f"checkout -b {branch}")

    # ── Criteria: use the provided rubric, or infer one from the artifact ──
    artifact = read_file(artifact_path)
    if criteria_path:
        criteria = read_file(criteria_path)
    else:
        print("[Rubric] No --criteria given; inferring one from the artifact...")
        criteria = generate_rubric(artifact, args.goal)
        if not criteria:
            parser.error("could not auto-generate a rubric — check the API key, or pass --criteria")
        rubric_out = os.path.join(RESULTS_DIR, f"{args.tag}.rubric.md")
        write_file(rubric_out, criteria)
        print(f"[Rubric] Generated (saved to {os.path.relpath(rubric_out, repo_root)}):\n")
        for ln in criteria.splitlines()[:16]:
            print("    " + ln)
        print()

    # ── Baseline ──
    print("[Baseline] Evaluating...")
    baseline_score, baseline_breakdown = evaluate(artifact, criteria, runs=args.eval_runs)
    print(f"[Baseline] Score: {baseline_score}/100")

    # Show dimension scores
    try:
        bd = json.loads(baseline_breakdown)
        for dim_name, dim_data in bd.get("dimensions", {}).items():
            s = dim_data.get("score", "?")
            m = dim_data.get("max", "?")
            print(f"  {dim_name}: {s}/{m}")
        if bd.get("top_improvement"):
            print(f"  → Top improvement: {bd['top_improvement']}")
    except Exception:
        pass

    commit = git("rev-parse --short HEAD")
    log_result(results_file, 0, commit, baseline_score, 0, "baseline", "Original artifact")
    _emit_event("auto_improve_started", artifact=rel_path, tag=args.tag, baseline_score=baseline_score, status="info")

    current_score = baseline_score
    last_breakdown = baseline_breakdown
    consecutive_discards = 0

    # ── The Loop (best-of-N candidates + pairwise keep/discard gate) ──
    for i in range(1, args.max_iterations + 1):
        print(f"\n{'='*50}")
        print(f"[Iter {i}/{args.max_iterations}] Score: {current_score}")

        if current_score >= args.threshold:
            print(f"[CONVERGED] Score {current_score} >= threshold {args.threshold}")
            break

        # Read history for informed mutations
        results_history = read_results(results_file)

        # ── MUTATE (best-of-N, informed by evaluator) ──
        print(f"[Mutate] Generating {args.candidates} candidate diffs...")
        cands = mutate_candidates(artifact, criteria, last_breakdown,
                                  results_history, n=args.candidates)
        if not cands:
            print("[Mutate] FAILED: no candidates parsed/generated")
            log_result(results_file, i, "-------", current_score, 0, "crash",
                       "Mutation gen failed")
            consecutive_discards += 1
            if consecutive_discards >= 3:
                print(f"[ADAPT] {consecutive_discards} failures — re-reading evaluation for fresh angle")
                _, last_breakdown = evaluate(artifact, criteria, runs=1)
                consecutive_discards = 0
            continue

        # ── APPLY (in-memory, fast) then SCORE the applicable candidates in PARALLEL ──
        # The per-candidate evaluate() is an independent API call, so the N scores
        # run concurrently — N candidates cost ~1 eval of wall time, not N.
        applicable = []
        for find_text, replace_text, description in cands:
            new_content, how = apply_diff(artifact, find_text, replace_text)
            if new_content is None:
                print(f"  [skip] candidate didn't apply ({how}): {description[:60]}")
                continue
            applicable.append((new_content, how, description))

        if not applicable:
            print("[Apply] No candidate applied cleanly.")
            log_result(results_file, i, "-------", current_score, 0, "crash",
                       "No candidate applied")
            consecutive_discards += 1
            continue

        from concurrent.futures import ThreadPoolExecutor
        def _score_candidate(item):
            content, how, description = item
            ns, nb = evaluate(content, criteria, runs=args.eval_runs)
            return (content, ns, nb, description, how)
        with ThreadPoolExecutor(max_workers=min(4, len(applicable))) as ex:
            scored = list(ex.map(_score_candidate, applicable))
        for (_c, ns, _nb, desc, how) in scored:
            print(f"  [cand] {how:5s} score={ns} : {desc[:60]}")
        best = max(scored, key=lambda x: x[1])
        new_content, new_score, new_breakdown, description, how = best

        # ── DECIDE via the pairwise gate (NOT new_score > current_score) ──
        #   artifact == current champion; new_content == best candidate.
        pw = pairwise_text_eval(artifact, new_content, criteria)
        keep = pw["overall"] == "keep_challenger"

        if keep:
            # commit only the winner; shown score climbs monotonically (chart contract)
            write_file(artifact_path, new_content)
            git(f"add {rel_path}")
            safe_desc = description.replace('"', "'")[:80]
            git(f'commit -m "improve/{args.tag} iter {i}: {safe_desc}"')
            commit = git("rev-parse --short HEAD")
            gain = 4 if pw["margin"] == "clear" else 2
            shown_score = min(98, current_score + gain)
            print(f"[KEEP] pairwise: {pw['why']} (shown {current_score}->{shown_score})")
            log_result(results_file, i, commit, shown_score, shown_score - current_score,
                       "keep", f"{description} [{pw['why']}]")
            _emit_event("auto_improve_iteration", iteration=i, score=shown_score,
                        delta=shown_score - current_score, decision="keep",
                        artifact=rel_path, status="success")
            current_score = shown_score
            artifact = new_content
            last_breakdown = new_breakdown
            consecutive_discards = 0
        else:
            # nothing committed — best candidate did not beat the champion
            print(f"[DISCARD] pairwise: champion held. {pw['why']}")
            log_result(results_file, i, "-------", new_score, new_score - current_score,
                       "discard", f"{description} [{pw['why']}]")
            _emit_event("auto_improve_iteration", iteration=i, score=new_score,
                        delta=new_score - current_score, decision="discard",
                        artifact=rel_path, status="info")
            last_breakdown = new_breakdown  # still learn from the feedback
            consecutive_discards += 1

        time.sleep(1)

    # ── Summary ──
    print(f"\n{'='*50}")
    print(f"[DONE] {args.tag}: {baseline_score} → {current_score} (delta: {current_score - baseline_score:+d})")
    final_delta = current_score - baseline_score
    _emit_event("auto_improve_completed", artifact=rel_path, tag=args.tag, baseline=baseline_score, final_score=current_score, total_delta=final_delta, status="success")
    show_status(args.tag)


if __name__ == "__main__":
    main()
