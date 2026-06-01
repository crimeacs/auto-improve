# API Design — Quality Criteria

Score a function's public interface — its **signature + docstring** (the API surface,
not the implementation). Anchors: **50 = it works but you'll misuse it, 70 = clean and
predictable, 90+ = hard to use wrong.** "Naming things" is one of the hard problems for
a reason. Reward designs that are obvious and safe, not clever or short.

## Dimensions (total: 100)

### Naming (22)
- Every parameter name says what it is — no single letters (`t`, `r`, `j`, `h`) or
  vague nouns (`data`, `opts`) (0-14)
- The function name names ONE clear job (0-8)

### Hard to misuse (24)
- No boolean traps — flags are keyword-only, or replaced by clearer types/enums (0-12)
- No footguns: no mutable default argument, no silent `**kwargs` catch-all that hides
  the real contract (0-12)

### Error contract (18)
- Failure is explicit — raises a specific error, not "returns the data, or None" that
  callers forget to check (0-10)
- The docstring states what it raises and when (0-8)

### Single responsibility (16)
- Does one thing; doesn't bundle fetch + retry + parse + cache + callback into a single
  surface (0-16)

### Defaults & types (10)
- Sensible defaults; type hints on the parameters and the return value (0-10)

### Docstring (10)
- States what it returns, the shape/units of each argument, and shows one usage
  example; no "gets the data" tautology (0-10)
