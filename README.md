# auto-improve

**A GAN-style self-improvement loop for any text artifact.** Point it at a file —
**bring a rubric, or let auto-improve write one from the artifact.** It then mutates the
file, grades the result with a *separate* model, keeps only the changes that genuinely
win, and reverts the rest. The git history becomes the improvement log — every commit is
a verified gain.

Works on anything text: emails, landing pages, prompts, READMEs, API designs, configs,
blog posts, cover letters. Don't have a rubric? Pass a one-line `--goal` (or nothing) and
it infers the right criteria first. Inspired by Karpathy's autoresearch.

```text
$ python3 improve.py --artifact examples/cold-email.txt \
                     --criteria criteria/cold-email-quality.md --tag email

[Baseline] Score: 48/100
[Iter 1] [KEEP] specific hook beats the generic opener        48 -> 52
[Iter 2] [KEEP] concrete metric replaces "does a lot"         52 -> 56
[DONE] email: 48 -> 56
```

**Before** → *"I wanted to reach out because I think our product could really help your
team. We've built an AI tool that does a lot of things…"*
**After** → *"I saw your engineering team is scaling up deployment velocity this quarter,
which usually strains QA. We cut regression cycles from 12 hours to under 15 minutes…"*

---

## Why it's different

The trap with "ask an LLM to improve this" is **slop**: the model rewrites confidently
and you can't tell if it actually got better. auto-improve fixes that with two rules:

1. **A separate judge.** The model that *mutates* never *grades* — grading is a fresh
   call against your rubric, so it can't grade its own homework.
2. **A pairwise keep/discard gate.** Each change is A/B'd against the current champion
   (both orderings, to debias position) and **kept only if it genuinely wins**.
   Confident-but-worse rewrites get reverted, not shipped.

The result is a monotonic climb you can trust — and a git branch where every commit is
a real improvement, fully diffable.

## How it works

```
for each iteration:
  MUTATE   → ask the model for N candidate edits (best-of-N), applied as surgical diffs
  SCORE    → grade each candidate against the rubric (parallel, separate model)
  DECIDE   → pairwise-judge the best candidate vs. the champion; keep iff it wins
  COMMIT   → git-commit a keep (advance the branch) / discard the rest
```

- **Surgical diffs, not rewrites** — a crash-proof apply ladder (exact → unicode-canon
  → fuzzy) means a malformed edit is skipped, never corrupts the file.
- **Best-of-N** — N candidates per round, so one bad draw doesn't stall the climb.
- **The git history is the artifact** — `git log improve/<tag>` is your improvement trail.

## Install

```bash
git clone https://github.com/crimeacs/auto-improve && cd auto-improve
pip install requests
export GEMINI_API_KEY=...        # free key: https://aistudio.google.com/apikey
```

Python 3.9+. One dependency (`requests`). Uses Google Gemini by default.

## Quickstart

Run it on the bundled example (a weak cold email + a rubric):

```bash
python3 improve.py --artifact examples/cold-email.txt \
                   --criteria criteria/cold-email-quality.md --tag email
git log --oneline improve/email          # the improvement trail
git diff main improve/email -- examples/cold-email.txt
```

Or skip the rubric entirely — describe the goal and it writes the criteria first:

```bash
python3 improve.py --artifact path/to/your/file.md --tag v1 \
                   --goal "a landing hero that makes a developer try the product"
# → [Rubric] inferred from the artifact (saved to results/v1.rubric.md), then it climbs
```

> The artifact must live inside a **git repo** — that's how keeps and discards are
> checkpointed. Run from your project root.

## Usage

```
improve.py --artifact FILE --tag NAME [--criteria RUBRIC.md] [options]

  --artifact        file to improve (inside a git repo)
  --criteria        markdown rubric, dimensions totaling 100 (see criteria/).
                    OPTIONAL — omit it and a rubric is inferred from the artifact.
  --goal            one-line intent to steer the auto-generated rubric (optional)
  --tag             run id → git branch improve/<tag>, results/<tag>.tsv
  --max-iterations  default 10
  --candidates      candidate edits per round (best-of-N), default 3
  --eval-runs       eval passes averaged per candidate, default 2 (1 = faster)
  --threshold       stop when the score reaches this, default 90
  --status          show a finished run's results table
```

## The rubric (optional)

The rubric is the spec auto-improve optimizes against. You don't have to write one —
omit `--criteria` and it infers a rubric from the artifact first (steer it with
`--goal`, and inspect the result it saves to `results/<tag>.rubric.md`). **Bring your
own when you want control**: a rubric is a markdown file with weighted dimensions that
sum to 100. See [`criteria/README.md`](criteria/README.md) for the full guide and
[`criteria/cold-email-quality.md`](criteria/cold-email-quality.md) for a worked example.

```markdown
# <Artifact> — Quality Criteria
Anchors: 50 = average, 70 = good, 90+ = exceptional. Reward craft, not length.

## Dimensions (total: 100)
### <Dimension> (N points)
- <what earns the points> (0-X)
```

## Bundled examples

Runnable examples — point `--artifact`/`--criteria` at a pair and watch it climb:

| artifact | rubric | |
|---|---|---|
| `examples/cold-email.txt` | `criteria/cold-email-quality.md` | |
| `examples/blog-post.md`   | `criteria/blog-post-quality.md` | |
| `examples/prompt.txt`     | `criteria/prompt-quality.md` | |
| `examples/api-design.py`  | `criteria/api-design-quality.md` | ← the hard one: a footgun-ridden function interface → a clean, hard-to-misuse API |

## Voice notes — improve spoken *delivery*

The same loop applied to how a note *sounds*, not just the words: it mutates the
text-to-speech voice + settings (and inline emotion tags), renders a clip, and an
**audio model** scores it — keeping the takes that genuinely sound better. See
[`voice/`](voice/) (needs an ElevenLabs key). Run it alongside the text loop for a note
that reads well *and* lands when spoken.

## Watch it climb (Rust plot)

A tiny [macroquad](https://macroquad.rs) app in [`plot/`](plot/) renders a run **live** —
score vs iteration, green keeps / red resets / gold retries — and re-reads the TSV as the
loop runs, so you watch the climb build in real time.

```bash
cd plot && cargo build --release
./target/release/plot ../results/<tag>.tsv     # or pass a dir to auto-pick the latest run
```

Run `improve.py` in one terminal and the plot in another to watch it climb. Headless check
(no window): `./target/release/plot --dump ../results/<tag>.tsv`.

## Configuration

| env var | default | purpose |
|---|---|---|
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | — | **required** |
| `IMPROVE_MUTATOR` | `gemini-flash-latest` | model that proposes edits |
| `IMPROVE_EVALUATOR` | `gemini-flash-latest` | model that grades + judges |
| `RESULTS_DIR` | `./results` | where `<tag>.tsv` climb logs are written |
| `IMPROVE_EVENTS_LOG` | — | optional path to append run events as JSONL |

## License

MIT — see [LICENSE](LICENSE).
