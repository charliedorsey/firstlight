# Routing experiments — what was measured, and why the design is what it is

This records the measurements behind the router design so the next person (or
future-you) doesn't re-derive them. All numbers are from a 20-prompt labeled
probe set over the 50-skill starter library.

## The tiers are a CONFIDENCE ranking, not a quality ranking

The router tries tiers in order: embed → coherence → tfidf → char. It's tempting
to read that as "best to worst," but it's really "most certain to least." Each
tier only speaks when it has enough signal; it stays silent (falls through)
otherwise. That silence is a feature — a tier that rarely fires but is right when
it does is exactly what you want at the top.

## Strict coherence: precise but sparse

- Fires on only **4/20** prompts (its descriptive-word vector has to overlap a
  room's coherence vocabulary, which short prompts rarely do).
- When it fires it is **4/4 correct**.
- Ignoring the 0.12 floor doesn't help: its top pick is correct on only 4/20
  regardless. It simply has no opinion on most short prompts.

Conclusion: don't lower the floor, don't try to make it route more. Its value is
precision, not coverage.

## tf-idf: the workhorse

- Carries **16/20** as the fallback, **15/16 correct**.
- Over the whole set, tfidf-alone top-1 accuracy is **18/20** (90%).
- The two misses: "dockerfile is huge → docker-multistage" (gets
  dockerfile-generator) and "optimize sql query → query-optimizer" (gets
  index-advisor). The second is a genuine synonym gap, not a fixable lexical bug.

## "soft coherence": more opinions, but not more accuracy

A variant that scores plain token PRESENCE (not co-occurrence-derived descriptive
words) against the room-word matrix:

- Has an opinion on **20/20** prompts (vs strict coherence's 4).
- Top-1 accuracy **17/20** — good, but *below* tfidf's 18.
- Blending it into tfidf (sum of normalized scores) → **17/20**: worse.
- Selective tie-break (consult it only when tfidf's top two are within 0.05) →
  **17/20**: also worse.

So soft coherence is **not** a better router. Every attempt to let it influence
the route lowered accuracy, because tfidf is already strong and soft coherence
drags it toward soft's own mistakes (it's confidently wrong on "websocket server"
and "make a multi-stage dockerfile").

### Where soft coherence IS useful: confidence calibration

The decisive measurement — accuracy conditioned on whether soft coherence AGREES
with the chosen route:

| condition                         | accuracy |
|-----------------------------------|----------|
| soft agrees with route (≥0.15)    | 16/17 = **94%** |
| soft disagrees (has signal)       | the shaky zone |

Raising the agreement floor trims confirmations without buying accuracy (94% holds
from 0.0 to 0.15, then drops), so the floor is set at **0.15** — "fire less, mean
more."

So soft coherence ships as a **second opinion that calibrates confidence, never as
a router**:
- agree + above floor → route is `confirmed` (the ✓ in the readout),
- has signal but disagrees → `unconfirmed`, the route is flagged uncertain (⚠),
- silent → `no_second_opinion`.

Over the probe set this is **90% confirmed, 10% flagged** — the two flagged are the
genuinely docker-ambiguous prompts. It surfaces uncertainty without becoming noise,
and it never changes the route, so router parity with sklearn is preserved exactly.

## The real ceiling: embeddings

The one prompt that defeats every lexical approach ("optimize sql query") is a
meaning-not-words problem. That's what the optional embedding tier is for — see
`EMBEDDINGS.md`. It's wired as the highest-precision tier and, in a stubbed test,
routes that prompt to query-optimizer where lexical methods land on index-advisor.
