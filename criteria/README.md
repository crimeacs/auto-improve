# Writing a rubric

A rubric is the spec auto-improve optimizes against — a markdown file whose weighted
dimensions sum to **100**. The evaluator reads it on every pass, scores the artifact
dimension by dimension, and the loop climbs that total. A good rubric is the whole game:
the loop gets very good at exactly what you ask for, so ask for the right things.

## Format

```markdown
# <Artifact> — Quality Criteria

Anchors: 50 = average, 70 = good, 90+ = exceptional. Reward craft, not length.
Award the top of a band when the artifact clearly does the right thing.

## Dimensions (total: 100)

### <Dimension name> (N points)
- <a specific thing that earns points> (0-X)
- <another specific thing> (0-Y)
```

The parser is lenient — it reads the `### Heading (N points)` lines and the bullets
under them. Keep the point values in the headings summing to 100.

## What makes a rubric work

- **Anchor the scale.** State what 50 / 70 / 90 mean, so the judge doesn't drift or
  inflate. Without anchors, everything scores "85."
- **Reward craft, not absence-of-flaws.** Phrase dimensions as "award N when the
  artifact does X well," not only "deduct for Y." A penalty-only rubric caps out low.
- **Be specific.** "Opens with something specific to this recipient" beats "good hook."
  The loop optimizes the literal words of your rubric — vague rubrics get vague gains.
- **Keep dimensions independent.** Overlapping dimensions double-count and skew the climb.
- **5–7 dimensions, ~10–30 points each.** Enough to be discriminating, few enough that
  each move can target one.

## Worked examples

- [`cold-email-quality.md`](cold-email-quality.md) — outreach email
- [`blog-post-quality.md`](blog-post-quality.md) — short blog post / essay
- [`prompt-quality.md`](prompt-quality.md) — LLM system prompt
- [`api-design-quality.md`](api-design-quality.md) — a function's public interface (the hard one)

Copy one, swap the dimensions for your artifact, point `--criteria` at it.
