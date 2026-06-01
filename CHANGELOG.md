# Changelog

All notable changes to **auto-improve** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The git history is already the improvement log for any artifact you run this on —
this file is the improvement log for the loop itself.

## [Unreleased]

## [0.1.0] — 2026-06-01

First public release. A GAN-style self-improvement loop for any text artifact:
mutate a file, grade each candidate with a separate judge model, keep only the
changes that win a debiased pairwise gate, revert the rest. Every commit on
`improve/<tag>` is a verified gain.

### Added
- `improve.py` — the loop. Mutate → score → pairwise-decide → commit, over a
  file inside a git repo.
- Optional rubric inference. Omit `--criteria` and a rubric is inferred from the
  artifact; steer it with `--goal "intent"`.
- Debiased pairwise keep/discard gate — candidate and champion are judged in
  both orderings (`[Candidate, Champion]` and `[Champion, Candidate]`); a
  mutation is kept only on a 2-0 sweep, so position bias can't ship a worse edit.
- Separate judge model — the model that mutates never grades.
- Crash-proof apply ladder: `improve.apply_diff(content, find, replace)` returns
  `(new_or_None, how)` where `how` is one of `exact`, `canon`, `fuzzy`,
  `not-found`, `empty-find`, `delimiter-in-replace`. A malformed edit is skipped,
  never corrupts the file.
- Best-of-N candidates per round via `--candidates` (default 3), so one bad draw
  doesn't stall the climb.
- `--status` — print a finished run's results table:
  `python3 improve.py --status --tag NAME`.
- CLI flags: `--artifact`, `--tag`, `--criteria`, `--goal`, `--max-iterations`
  (default 10), `--candidates` (default 3), `--eval-runs` (default 2),
  `--threshold` (default 90).
- Offline-testable core (no network): `improve._parse_candidates(text)`,
  `improve.apply_diff(...)`, and the `improve._DELIMS` delimiter tuple.
- Bundled examples: `examples/cold-email.txt`, `examples/blog-post.md`,
  `examples/prompt.txt`, `examples/api-design.py`, with matching rubrics in
  `criteria/`.
- Optional Rust live plot in `plot/` (macroquad): renders score vs. iteration as
  the loop runs, re-reading `results/<tag>.tsv`. Headless dump available.
- Optional voice variant in `voice/` (ElevenLabs TTS via `ELEVENLABS_API_KEY`):
  mutates voice + settings, renders a clip, and grades it with an audio model.
- Gemini provider by default. API key via `GEMINI_API_KEY` or `GOOGLE_API_KEY`.
- Single runtime dependency (`requests`), pinned in `requirements.txt`.
  Python 3.9+.

### Security
- No keys in the repo. All API keys are read from the environment only and must
  never be committed.

[Unreleased]: https://github.com/crimeacs/auto-improve/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/crimeacs/auto-improve/releases/tag/v0.1.0
