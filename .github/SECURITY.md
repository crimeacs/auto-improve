# Security Policy

## Supported versions

auto-improve is a single-file tool that tracks the latest `main`. Security
fixes land on `main` only — there are no backported release branches. If you're
running an older checkout, `git pull` before reporting.

| Version | Supported |
|---|---|
| latest `main` | ✅ |
| anything older | ❌ — update first |

## Reporting a vulnerability

**Report privately. Do not open a public issue for security problems.**

Use GitHub's private vulnerability reporting:

1. Go to the [Security tab](https://github.com/crimeacs/auto-improve/security)
   of the repo.
2. Click **Report a vulnerability** to open a private GitHub Security Advisory.
3. Include a clear description, reproduction steps, and the impact you observed.

That channel goes straight to the maintainer ([@crimeacs](https://github.com/crimeacs))
and keeps the details out of public view until a fix ships. Expect an initial
response within a few days. Please give a reasonable window to patch before any
public disclosure.

## Secrets are environment-only

auto-improve never reads, writes, or commits API keys. There are **no keys in
this repository** and there never should be.

- All credentials are passed via environment variables — `GEMINI_API_KEY` /
  `GOOGLE_API_KEY` (and `ELEVENLABS_API_KEY` for the optional `voice/` variant).
- The tool only ever reads these from the environment at runtime. It does not
  persist them to disk, the run logs (`results/<tag>.tsv`), or git.
- The improvement branch (`improve/<tag>`) and every commit it makes are over
  *your artifact file* — never over a secret store.

When contributing or filing a report:

- **Never paste a real key** into an issue, advisory, pull request, commit, or
  `--criteria` / `--goal` argument. Redact it (`GEMINI_API_KEY=...`).
- If you believe a key has been committed anywhere — yours or the project's —
  treat it as compromised: **rotate it immediately**, then report privately via
  the advisory flow above so we can scrub history if needed.
- Free Gemini keys come from <https://aistudio.google.com/apikey>; rotating one
  is fast and free.

## Scope

This is a local CLI that mutates a text file in your own git repo and calls a
third-party model API (Google Gemini by default, ElevenLabs for `voice/`). The
main things worth a private report:

- A path that causes auto-improve to leak an environment secret into a file,
  log, commit, or network call it shouldn't.
- A malformed model response or rubric that escapes the diff apply ladder and
  corrupts files outside the targeted artifact.
- Any code path that executes untrusted content from a model response or
  artifact as a command.

Thanks for helping keep auto-improve honest.
