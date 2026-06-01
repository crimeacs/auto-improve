<!--
Thanks for improving auto-improve. Keep PRs small and verifiable —
this loop is built on changes that genuinely win, and so is the codebase.
-->

## What this changes

<!-- One or two sentences. What's different, and why. -->

## Type of change

- [ ] Bug fix (the loop, the diff engine, the judge, the plot/voice variants)
- [ ] New feature (flag, env var, example, rubric)
- [ ] Docs / examples only
- [ ] Refactor / cleanup (no behavior change)

## Checklist

- [ ] Branches off `main`; one logical change per PR.
- [ ] **No secrets.** API keys stay in env only (`GEMINI_API_KEY` / `GOOGLE_API_KEY`, `ELEVENLABS_API_KEY`) — nothing committed, nothing hard-coded.
- [ ] Runtime deps unchanged — still the single `requests` in `requirements.txt`. New deps are justified below or avoided.
- [ ] Python 3.9+ compatible.

## If you touched the diff engine

The offline core runs with no network. If you changed `_parse_candidates` or `apply_diff`:

- [ ] Verified `apply_diff(content, find_text, replace_text)` still returns the right `how` (`exact` / `canon` / `fuzzy` / `not-found` / `empty-find` / `delimiter-in-replace`), and a malformed edit is skipped, never written.
- [ ] Checked `_parse_candidates` against tricky input — multiple candidates, `_DELIMS` collisions in the replacement.

## If you changed the loop, judge, or flags

- [ ] Ran a real climb end-to-end on a bundled pair, e.g.:
  ```
  python3 improve.py --artifact examples/cold-email.txt \
                     --criteria criteria/cold-email-quality.md --tag pr-check
  python3 improve.py --status --tag pr-check
  ```
- [ ] Score is monotonic — every `[KEEP]` is a real win, no slop slipped through the pairwise gate.
- [ ] New flags / env vars documented in `README.md` (Usage block or Configuration table).

## If you added an example or rubric

- [ ] `--artifact` / `--criteria` pair runs and climbs.
- [ ] Rubric dimensions sum to 100; pair listed in the Bundled examples table in `README.md`.

## Proof

<!--
Paste the climb. The git history is the artifact — show yours.
Example:
  [Baseline] Score: 48/100
  [Iter 1] [KEEP] specific hook beats the generic opener   48 -> 52
  [DONE] pr-check: 48 -> 56
-->
