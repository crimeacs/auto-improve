---
name: auto-improve
description: GAN-style iterative improvement loop for any text artifact. Mutates a file, grades each change against a rubric with a SEPARATE model, keeps only verified wins (pairwise-judged), reverts the rest. The git history is the improvement log. Use when the user wants to autonomously improve the quality of a document, email, prompt, landing page, README, contract, or any text file.
user-invocable: true
---

# auto-improve

Autonomous, judge-gated self-improvement for any text artifact. See `README.md` for the
full guide; this is the agent-facing quick reference.

## When to use

The user wants something **measurably** better, not just rewritten — and is willing to
express "better" as a rubric. Good fits: cold emails, landing copy, prompts, skill
definitions, blog posts, cover letters, docs, contracts, menus.

## Run it

```bash
export GEMINI_API_KEY=...        # https://aistudio.google.com/apikey
python3 improve.py \
  --artifact path/to/file.md \   # must be inside a git repo
  --criteria path/to/rubric.md \ # weighted dimensions summing to 100 (see criteria/)
  --tag v1 \                     # → branch improve/v1, results/v1.tsv
  --max-iterations 8
```

Check a finished run: `python3 improve.py --status --tag v1`.
The result lives on the `improve/<tag>` git branch — `git diff main improve/v1 -- <file>`.

## How it decides (the anti-slop part)

1. **Mutate** — best-of-N candidate edits, applied as surgical diffs (crash-proof).
2. **Score** — each candidate graded against the rubric by a *separate* model call.
3. **Decide** — the best candidate is pairwise-judged against the champion (both
   orderings, debiased); **kept only if it genuinely wins**, else reverted.

The mutator never grades its own work, and confident-but-worse rewrites are discarded —
so the climb is real and every commit is a verified gain.

## Writing the rubric

A markdown file of weighted dimensions totaling 100 — anchored (50/70/90), reward-framed,
specific. See `criteria/README.md` and the worked examples in `criteria/`.

## Key rules

- The mutator and evaluator never share context.
- One artifact, one rubric, one `--tag` per run.
- The git branch is the source of truth; `results/<tag>.tsv` is the climb log (untracked).
- Never edit outside the artifact; small surgical diffs, not wholesale rewrites.
