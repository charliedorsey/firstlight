# Two-stage routing — deliverable gate (stage 1) + semantic discrimination (stage 2)

This is the architecture FirstLight is moving toward as its spine: route in two
stages instead of one flat score.

```
prompt
  │
  ▼   STAGE 1 — deliverable_gate.py  (pure stdlib, runs on the free path)
  │   Rule out skills whose OUTPUT WORLD is categorically wrong for what's asked.
  │   A loose, high-certainty VETO — not a ranker. Keeps a bucket.
  │     • prompt → output shape(s) → world(s): TECHNICAL / HUMAN / CREATIVE
  │     • skill  → declared-purpose shape → world(s)  (from SKILL.md description,
  │       NOT the noisy full body)
  │     • veto a skill only if its world is disjoint from the prompt's world
  │     • if prompt world is unknown, or veto would empty the library → veto nothing
  ▼
  survivors (a bucket — often the whole library for technical→technical)
  │
  ▼   STAGE 2 — pure_router.route(candidates=survivors)
  │   embed → coherence → tf-idf → char, scoring ONLY the survivors. A
  │   categorically-wrong skill can't win even if its words match, because it was
  │   removed before scoring.
  ▼
  routed result + second-opinion confidence + full dashboard
```

## Why two stages, not one combined score

A flat `move + topic` score lets a strong topic match override a categorical
mismatch — "write me a poem about debugging" could route to a debug skill on the
word "debugging." A staged FILTER can't: if the deliverable world is wrong, the
skill never reaches stage two. The gate is a hard prior, which is the precision
the whole project is built around.

## Why the gate is a VETO, tuned LOOSE

A stage-one false REJECT is unrecoverable (the right skill never reaches stage
two). A false ACCEPT is cheap (stage two filters it). So the gate errs loose:
- it only separates output WORLDS (TECHNICAL/HUMAN/CREATIVE), never fine types;
- all code-adjacent shapes (make/transform/diagnose/review/explain/plan) share the
  TECHNICAL world and never veto each other;
- unknown prompt shape → veto nothing;
- a veto that would empty the library → veto nothing.

## Measured behavior (50-skill technical library)

- **Technical prompt → gate is silent.** "write e2e tests", "optimize sql",
  "scan deps" all keep 50/50 — stage two does the real work. The gate adds nothing
  and costs nothing, which is correct: they're all the same output world.
- **Categorical mismatch → gate fires hard, with high certainty.**
  - "help me sit with a hard feeling" → HUMAN → 48 vetoed, 2 survive.
  - "write me a poem about debugging my heartbreak" → CREATIVE → 48 vetoed.
  In both cases, WITHOUT the gate the router confidently produced an absurd route
  (a feeling → `code-smell-detector`; a poem → `e2e-test-writer`); WITH the gate it
  correctly reports no good match, because this library genuinely has no
  emotional-support or creative-writing skill. **The gate converts a confident
  wrong answer into an honest "nothing here fits."** That is the whole point.

## Known limitation (named, not hidden)

The gate is only as good as its SHAPE DETECTION, which is currently keyword-based.
A prompt that means HUMAN but avoids obvious words slips through:
- "help me emotionally process getting my pull request rejected" → detected world
  is empty (the keywords "process / pull request / rejected" didn't fire REFLECT),
  so the gate stays loose and a technical skill wins.

This is the same lexical brittleness the rest of the system hits — but the fix here
is NOT the same as stage two's. The gate runs on EVERY read, on the pure stdlib-only
free path, so its shape detector MUST stay dependency-free. It cannot become
embedding-backed without breaking the zero-dependency guarantee for the whole read
arm (unlike the stage-two embed tier, which is optional and degrades to lexical).

So the gate's sensor improves only by stdlib-legal means:
- a richer, hand-curated shape lexicon (more synonyms per world, still pure regex);
- light morphological/structural cues (imperative vs. reflective sentence shape,
  first-person-feeling markers) — all computable in stdlib;
- learned-but-frozen weights: a tiny shape classifier can be TRAINED offline (build
  arm, heavy) and SERIALIZED into the cache as plain numbers, so the read arm only
  does a pure-python dot product — never an embedding call.
The gate's *structure* is right; its *sensor* is v1 and must stay stdlib.

## The governing constraint (read this before extending anything)

The free read path is stdlib-only, and that is load-bearing. Any component that
runs on EVERY read — the gate, the lexical tiers, the dashboard — must be pure
Python standard library. Heavy work is allowed in exactly two shapes:

  (a) BUILD-TIME, serialized to plain numbers in the cache. A classifier can be
      trained offline with numpy/sklearn, then stored as floats; the read arm does
      a pure-python dot product. The intelligence is baked in, the dependency is not.
  (b) an OPTIONAL tier that DEGRADES to lexical when its backend is absent (this is
      how the stage-two embed tier works — present a provider and it activates,
      omit one and routing falls back to tf-idf, no error).

What is NOT allowed: making an always-on component (like the stage-one gate) depend
on a network call or a heavy import. That would mean the pure read path can't run
without a provider — breaking the whole two-arm promise. When a sensor needs to get
smarter, reach for (a) or (b), never for "just call the embedding here."

---



This is stage one of the spine. The path forward (from DELIVERABLE_SPINE_FINDINGS):
1. Gate stays the coarse first filter (here, working), with a stdlib-only sensor.
2. Stage two gains the embedding tier for topic discrimination within survivors
   (optional, degrades to lexical — the gate does NOT depend on it).
3. The move/deliverable MATCH (deliverable.py's ask→delivers) becomes a stage-two
   ranker for posture-differentiated libraries, where it has real separability —
   once its prompt→ask read is non-keyword. Note: if that read is embedding-backed
   it lives in the OPTIONAL stage-two tier, never in the always-on gate.
4. Re-key generalization (train the move→deliver projection on more witnessed,
   posture-varied pairs) is the lever for the inferred deliverable faces.

Stage one is the part that's working and shippable now; it degrades to a no-op on
libraries/prompts it can't shape-read, so it never makes routing worse.
