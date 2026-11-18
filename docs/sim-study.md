# Does Self-Improvement Memory help auto-improve? A small paired study

**Short answer: possibly a small benefit, not established.** Four pairs is too few. Below is
exactly what was run and what came out.

## Design

This follows the cross-dataset setting of *Self-Improvement Memory Enables Continual
Recursive Self-Improvement* (arXiv 2611.18856), scaled down to one domain.

- **Source run:** `examples/cold-email.txt` with `criteria/cold-email-quality.md`, run with
  `--sim`. This builds a memory: 6 attempts across 4 or 5 problems (rubric dimensions).
- **Target runs:** a second cold email (`experiments/sim_study/target-email.txt`, a fictional
  logistics vendor with the same generic weaknesses) is improved twice from the same start.
  One run uses **no memory** (the default TSV excerpt). The other uses **the source run's
  memory**, which it extends.
- **Matched budgets:** 6 iterations, 3 candidates, 1 eval run, threshold 99. Mutator and
  evaluator are both `gemini-flash-latest`.
- **Pairs:** 4. Each pair has its own source run, so each target-with-memory arm inherits a
  different memory.
- **Endpoint:** fixed before results. The two final target emails are compared by the
  pairwise judge in both orders (votes counted; a 1–1 split is a tie). Each final email is
  also scored by the rubric evaluator, averaged over 3 runs.
- **Judge check:** the target scored 21 at baseline. A deliberately bad email scored 5, so the
  judge passes the known-bad probe.

Reproduce with `GEMINI_API_KEY=… ITERS=6 PAIRS=4 python3 experiments/sim_study/run_study.py`.

## Results (2026-11-18, `experiments/sim_study/study-2026-11-18.json`)

| Pair | Pairwise votes, no memory : memory | Rubric score, no memory / memory |
|---|---|---|
| 1 | 2 : 0 | 92 / 92 |
| 2 | 1 : 1 | 92 / 89 |
| 3 | 0 : 2 | 86 / 92 |
| 4 | 0 : 2 | 89 / 91 |

The memory arm wins 2 pairs, loses 1 and ties 1. The mean rubric score is 91.0 against
89.75, a difference of +1.25.

## Reading it

- **Underpowered.** With n = 4 this cannot separate a real effect from run-to-run variance.
  The paper needed 10 paired source runs for its coding result (+2.36, p = 0.003).
- **Ceiling.** Both arms finish near 90/100 on a short email, so there is little room left
  to show a difference. Longer artifacts with more dimensions are the better test.
- **Look at the artifacts, not the numbers.** The final emails from pairs 1 and 3 are in
  `experiments/sim_study/final-*.txt`. They differ in style more than in quality. In pair 3
  the memory arm ended with a lower-friction call to action ("2-minute breakdown" rather
  than "10-minute look this Thursday").
- **Both arms invent proof.** The rubric rewards concrete metrics and named customers, so the
  mutator makes them up ("FreightCorp", "22% in their first quarter"). The memory makes this
  no better or worse. Source-check any output before using it.

## What would establish it

Ten or more paired source runs, two or three domains (email, blog post, prompt), a longer
target artifact, and a held-out human or different-family judge for the final comparison.
