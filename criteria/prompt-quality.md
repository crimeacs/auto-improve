# System Prompt — Quality Criteria

Score an LLM system prompt. Anchors: **50 = average, 70 = good, 90+ = exceptional.**
Reward precision — every line should change the model's behavior. Award the top of a
band when the prompt clearly does the right thing.

## Dimensions (total: 100)

### Role & scope (25)
- Names a specific role and a clear scope — not "a helpful assistant" (0-15)
- Says what's out of scope and when to defer or refuse (0-10)

### Concrete behavior (25)
- Tells the model HOW to answer — format, length, tone — with specifics, not "be
  helpful" or "give good answers" (0-15)
- Gives rules it can actually follow, not a vibe (0-10)

### Edge cases (20)
- Handles unknowns, ambiguity, and refusals explicitly (0-12)
- Anticipates the common failure mode for this task (0-8)

### Precision (20)
- No filler ("try to give good answers"); every line earns its place (0-12)
- Unambiguous — two readers would follow it the same way (0-8)

### Brevity (10)
- As short as it can be without dropping a rule (0-10)
