"""Self-Improvement Memory (SIM) for auto-improve's optimizer.

After "Self-Improvement Memory Enables Continual Recursive Self-Improvement"
(Yu et al., arXiv 2611.18856). The memory belongs to the optimizer (the mutator and
the keep/discard gate), not to the artifact. Each entry is a recurring weakness, here
a rubric dimension the evaluator scores. It holds every selected attempt in order:
what changed, which dimension it targeted, what it PREDICTED before scoring, what was
measured (per-dimension score change, overall change, pairwise verdict), and
provenance (artifact, tag, models). Discarded attempts are kept, and so are kept
edits that were later superseded.

The whole memory goes into the mutator prompt, with no retrieval or truncation of
entries. A memory file can be carried from one run to another (another artifact or
another model), which is the paper's continual setting.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

VERSION = "auto-improve-sim.v1"
GUIDANCE = """How to use this memory:
- Treat entries as prior experience; a different edit is allowed.
- Check the artifact and models behind each entry before reusing it.
- Start from an existing problem when it explains the current weakness.
- Reuse the reasoning behind an edit, but reassess it for this artifact.
- Do not repeat a direction that was already tested unless new evidence justifies it.
- Name a new problem when no existing one explains the weakness."""


def load(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("version") != VERSION:
            raise ValueError(f"{path}: not an auto-improve SIM file")
        return data
    return {"version": VERSION, "problems": {}}


def save(data, path):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def norm_problem(name):
    """Dimension names from the evaluator, or a free-text weakness, as one stable key."""
    return re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")[:80] or "unspecified"


def dimension_scores(breakdown):
    """{dimension: score} from the evaluator's JSON breakdown; {} when it is not JSON."""
    try:
        bd = json.loads(breakdown) if isinstance(breakdown, str) else (breakdown or {})
    except (ValueError, TypeError):
        return {}
    out = {}
    for name, d in (bd.get("dimensions") or {}).items():
        if isinstance(d, dict) and isinstance(d.get("score"), (int, float)):
            out[norm_problem(name)] = d["score"]
    return out


def record(data, *, problem, what, predicted, before_breakdown, after_breakdown, overall_before,
           overall_after, pairwise, kept, context):
    """Append one selected attempt under its problem (paper Eq. 3: U(M, e))."""
    key = norm_problem(problem)
    entry = data["problems"].setdefault(key, {"name": problem or key, "opened": context.get("at"), "attempts": []})
    before, after = dimension_scores(before_breakdown), dimension_scores(after_breakdown)
    entry["attempts"].append({
        "what": what, "predicted": predicted or "",
        "observed": {"dimension_delta": (after.get(key) - before[key]) if key in before and key in after else None,
                     "overall_delta": overall_after - overall_before, "pairwise": pairwise},
        "kept": bool(kept), **context})
    return key


def render(data):
    """The whole memory as prompt text."""
    if not data.get("problems"):
        return "No self-improvement memory yet."
    lines = [GUIDANCE, ""]
    for key, p in data["problems"].items():
        lines.append(f"## {p['name']}  [{key}]")
        for a in p["attempts"]:
            o = a.get("observed", {})
            dd = o.get("dimension_delta")
            lines.append(f"- {'KEPT' if a.get('kept') else 'discarded'} ({a.get('artifact', '?')}, "
                         f"mutator {a.get('mutator', '?')}): {a.get('what', '')}")
            lines.append(f"  predicted: {a.get('predicted') or '(none)'}")
            lines.append(f"  observed: dimension {'n/a' if dd is None else f'{dd:+g}'}, overall "
                         f"{o.get('overall_delta', 0):+g}, pairwise {o.get('pairwise', '?')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def context(artifact, tag, iteration, mutator, evaluator):
    return {"artifact": artifact, "tag": tag, "iteration": iteration, "mutator": mutator,
            "evaluator": evaluator, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
