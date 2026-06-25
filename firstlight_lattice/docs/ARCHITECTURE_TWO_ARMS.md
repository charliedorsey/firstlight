# Architecture: the two arms

FirstLight splits into a heavy **build** arm and a free **read** arm. The split
is the whole reason the per-turn cost is zero.

```
  your skills/                ┌──────────────── BUILD (once, heavy) ────────────────┐
  ~/.claude/skills      ───▶  │ semantic_lattice + dim_* + move_*  (numpy, sklearn) │
  (or any prompt lib)         │ → fit dimensions, tf-idf, coherence matrix          │
                              │ → write cache.json  (+ corpus fingerprint)          │
                              └─────────────────────────┬───────────────────────────┘
                                                        │  plain JSON, no pickles
                              ┌─────────────────────────▼───────────────────────────┐
  a live prompt        ───▶  │ READ (every turn, PURE PYTHON, zero deps)            │
                              │ pure_read/read.py:                                   │
                              │   • staleness check (fingerprint vs library)         │
                              │   • route()  → coherence / tf-idf / char tiers       │
                              │   • turn_dashboard panels (already pure)             │
                              │ → advisory readout                                   │
                              └──────────────────────────────────────────────────────┘
```

## Why two arms

The corpus analysis — discovering the dimensions, fitting tf-idf, building the
coherence matrix — is genuinely heavy and genuinely one-time. It only changes
when the *library* changes, not when a new prompt arrives. So it runs once and
its result is cached.

Reading a live prompt against that cached state is cheap linear algebra over
small vectors. We reimplemented it in pure Python standard library, so the
per-turn path needs nothing installed. This was verified two ways:

1. **Parity** — `pure_read/parity_router.py` asserts the pure router returns the
   exact same `(room, score, via)` ranking as the sklearn router, at 3-decimal
   precision, across a probe set. Currently 20/20 on the 50-skill library and
   6/6 on a tiny library (which exercises the char-fallback tier).
2. **Isolation** — the read path was run with `numpy`, `scikit-learn`, and
   `scipy` blocked from import; it routes correctly anyway.

## The cache

`build` writes `.firstlight_cache_<libhash>.json` (one per library path, so
multiple libraries don't collide; gitignored). It contains:

- `names` — the routed records, in order.
- `corpus_fingerprint` — `{record: sha256(text)}` for staleness detection.
- `coherence` — the row-normalized room-word matrix `C` + its vocab index.
- `word_tfidf` — vocabulary, idf vector, and the L2-normalized document rows.
- `char_tfidf` — the char n-gram fallback state, **only** for libraries ≤10
  records (where morphology misses matter); null otherwise to keep the cache small.

## Staleness: warn loudly, never gate

Every `read` recomputes the corpus fingerprint (cheap, stdlib — just hashing the
files) and compares it to the cache's stored fingerprint. If they differ it prints
exactly what changed (added / removed / edited records) and the rebuild command,
then **routes anyway** against the old cache. This matches the tool's whole
philosophy: it advises, it never blocks. You're told the routing is stale; you
decide whether to rebuild now or later.

## What did NOT need porting

The dashboard panels — `compute_budget` (effort estimate), `turn_decision`
(RUN-vs-WRITE, ARTIFACT-vs-INLINE), `posture_hint`, `failure_flags` — were
already pure Python in `turn_dashboard.py`. They consume the routed result, so
once routing is pure, the entire per-turn path is dependency-free.

## Keeping the two routers in sync

The pure router must track any change to the heavy router's logic or constants.
The guard is `parity_router.py`: if someone changes a threshold (e.g. the
coherence floor), a scoring formula, or the tokenization, the parity test fails
until the pure side matches. Run it after any change to `semantic_lattice.py`.
