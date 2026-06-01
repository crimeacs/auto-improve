# Support

Need help with auto-improve? Here's where to go.

## How-to & usage questions

For "how do I…", setup help, rubric-writing advice, or anything where you're
not sure if something is broken — open a **[GitHub Discussion](https://github.com/crimeacs/auto-improve/discussions)**.

Good Discussion topics:

- How do I write a rubric, or steer the inferred one with `--goal`?
- Why is my run reverting every candidate?
- Tuning `--candidates`, `--eval-runs`, or `--threshold` for my artifact.
- Running the `plot/` climb chart or the `voice/` variant.
- Sharing a run you're proud of.

Before posting, skim the [README](../README.md) and [`criteria/README.md`](../criteria/README.md) —
most usage questions are answered there.

## Bugs & defects

Found a real defect — a crash, a wrong result, a command that doesn't behave as
documented? File a **[bug report](https://github.com/crimeacs/auto-improve/issues/new)**.

A good bug report includes:

- What you ran (the full `improve.py` command and flags).
- What you expected vs. what happened.
- Python version, OS, and which model env vars are set (`IMPROVE_MUTATOR` / `IMPROVE_EVALUATOR`).
- A minimal artifact + rubric that reproduces it, if you can share one.

The offline core has no network dependency, so many bugs reproduce without an API
key — `improve._parse_candidates`, `improve.apply_diff`, and `improve._DELIMS` are
all testable locally. Include a repro snippet where it helps.

## Security

Don't open a public issue for vulnerabilities. Report privately via
[GitHub Security Advisories](https://github.com/crimeacs/auto-improve/security/advisories/new).

## Not sure which?

If it might be a bug but you're not certain, start a Discussion. We'll convert it
to an issue if it turns out to be a defect.

> All support runs through GitHub — Discussions, Issues, and Security Advisories.
> There's no support email.
