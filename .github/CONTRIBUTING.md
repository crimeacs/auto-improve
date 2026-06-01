# Contributing to auto-improve

Thanks for helping make auto-improve better. This is a small, focused project:
one runtime dependency (`requests`), one entry point (`improve.py`), and a core
that's testable offline. Keep contributions in that spirit — surgical, verifiable,
no slop.

## Setup

```bash
git clone https://github.com/crimeacs/auto-improve && cd auto-improve
pip install requests
export GEMINI_API_KEY=...        # free key: https://aistudio.google.com/apikey
```

Python 3.9+. That's the whole toolchain. Keys come from the environment only —
never hardcode one, never commit one (see [Secrets](#secrets)).

## Run it

Climb the bundled cold-email example to confirm your setup works end to end:

```bash
python3 improve.py --artifact examples/cold-email.txt \
                   --criteria criteria/cold-email-quality.md --tag email
git log --oneline improve/email          # the improvement trail
python3 improve.py --status --tag email  # the results table
```

The artifact must live inside a git repo — that's how keeps and discards get
checkpointed. Run from the project root.

Full flag reference is in the [README](../README.md#usage). The ones you'll touch
most while developing:

- `--candidates` — best-of-N per round (default 3); raise to explore more.
- `--eval-runs` — eval passes averaged per candidate (default 2; `1` is faster).
- `--max-iterations` — default 10.

## Test the core offline (no network, no key)

The diff engine is the part most likely to break, and it runs without a model
or a key. Exercise it directly:

```python
import improve

# Parse model output into (find, replace, desc) edits
edits = improve._parse_candidates(text)

# Apply one edit; `how` ∈ {exact, canon, fuzzy, not-found,
#                          empty-find, delimiter-in-replace}
new_content, how = improve.apply_diff(content, find, replace)
```

`apply_diff` must never corrupt a file: a malformed edit returns `None` with a
`how` reason, and the candidate is skipped. If you change the apply ladder
(exact → unicode-canon → fuzzy) or `improve._DELIMS`, cover every `how` branch
before opening a PR. A regression here silently ships bad edits.

## Add an example or rubric

Examples are artifact/rubric pairs that anyone can run. To add one:

1. Drop the artifact in `examples/` (e.g. `examples/cover-letter.txt`).
2. Drop a matching rubric in `criteria/` (e.g. `criteria/cover-letter-quality.md`).
   A rubric is a markdown file with weighted dimensions summing to 100 — see
   [`criteria/README.md`](../criteria/README.md) and
   [`criteria/cold-email-quality.md`](../criteria/cold-email-quality.md) for the shape.
3. Verify it actually climbs:

   ```bash
   python3 improve.py --artifact examples/cover-letter.txt \
                      --criteria criteria/cover-letter-quality.md --tag cover-letter
   ```

4. Add the pair to the **Bundled examples** table in the README.

Start the artifact weak on purpose — the point is to watch it improve. If the
rubric infers cleanly from the artifact alone, mention that; `--criteria` is
optional and a good example shows both paths.

## Commit conventions

- **One logical change per PR.** A diff-engine fix and a new example are two PRs.
- **Conventional Commits** for the subject line:

  ```
  feat: add cover-letter example + rubric
  fix(diff): handle delimiter collision in replace text
  docs: clarify --eval-runs tradeoff
  test: cover fuzzy-apply branch in apply_diff
  ```

- Every commit on `main` should leave the repo runnable. The project's own
  ethos is that history is the improvement log — keep yours just as legible.
- Update docs (README, this file, rubric guides) in the same PR as the behavior
  they describe.

## Before you open a PR

- [ ] Offline core still passes (`_parse_candidates`, `apply_diff`, every `how`).
- [ ] A real climb runs against a bundled example.
- [ ] No secrets, keys, or `results/` artifacts staged (`.gitignore` covers them).
- [ ] Docs updated alongside any behavior change.

## Secrets

API keys are read from the environment (`GEMINI_API_KEY` / `GOOGLE_API_KEY`,
and the optional `ELEVENLABS_API_KEY` for the voice variant) and live nowhere
in the repo. Don't add a key to code, a test fixture, an example, or a commit —
not even a throwaway. If you ever paste one by accident, rotate it immediately
and force-rewrite the branch.

Found a leaked key in the history, or any other security issue? Report it
privately via a [GitHub Security Advisory](https://github.com/crimeacs/auto-improve/security/advisories/new)
rather than a public issue or PR.

## License

By contributing you agree your work is licensed under the project's
[MIT License](../LICENSE).
