# Embeddings — the optional highest-precision route tier

The lexical tiers (coherence, tf-idf, char) match on *words*. They can't cross a
synonym/paraphrase gap: "optimize this slow sql query" shares no winning words
with a `query-optimizer` skill, so tf-idf misroutes it to `index-advisor`. An
embedding tier matches on *meaning* and fixes that class of case.

It is **off by default** and adds **no heavy dependency**. The default install
stays pure-Python and never touches the network. Embeddings are an opt-in upgrade.

## How it fits the two-arm model

- **build arm** embeds each skill's text ONCE and stores L2-normalized vectors in
  the cache (`embed_vectors`, `embed_dim`). Skills change rarely, so this is a
  one-time cost.
- **read arm** embeds the single incoming prompt, then does cosine against the
  cached skill vectors. The cosine is pure stdlib; only *getting the prompt
  vector* calls out to a provider.

If embeddings are present in the cache AND a provider is configured, the router
tries the `embed` tier first (cosine floor 0.25); otherwise it silently uses the
lexical tiers exactly as before.

## Option A: Local embeddings with Ternlight (recommended)

[Ternlight](https://github.com/soycaporal/ternlight) is an ultra-compact semantic
embedding model (~7MB WASM, 384-dim, L2-normalized, ~5ms per embed, distilled from
all-MiniLM-L6). It runs locally via Node — no API key, no network, no cost.

One-time setup:

```bash
cd firstlight_lattice/pure_read
npm install                    # installs @ternlight/base (~7MB)
cd ../..
./run.sh build                 # now also embeds the 52 skills via ternlight
./run.sh "optimize sql query"  # routes via [embed] — crosses synonym gaps
```

That's it. No env vars needed. `default_provider()` detects ternlight automatically
when `node_modules/@ternlight/base` is present.

### How chunking works

Ternlight has a 128-token input window. Skills are 100-180 lines (800-1500+ tokens).
The output specification, verification steps, and "when NOT to use" sections at the
END of each skill carry critical routing signal that naive truncation would lose.

The build arm splits each skill into overlapping ~100-token chunks (20-token overlap
to cover section boundaries), embeds ALL chunks in one batch call (one WASM load),
and stores every chunk vector plus a map from vector to skill. At read time, the
prompt is cosined against all chunks, and the **max score per skill** determines the
route. If ANY chunk of a skill matches the prompt well, that skill scores high —
a prompt about "verifying API errors" matches the verification chunk at the end of
`api-error-handler` even though the opening chunk talks about error classes.

Cache fields when ternlight is used:
  - `embed_vectors`: all chunk vectors (flat list, more entries than skills)
  - `embed_skill_map`: maps each vector index to its skill index in `names`
  - `embed_dim`: 384
  - `embed_chunked`: true

### Smaller/faster alternative

Edit `package.json` to use `@ternlight/mini` (5MB, ~2ms, Spearman 0.820) instead
of `@ternlight/base` (7MB, ~5ms, Spearman 0.844). Both produce 384-dim vectors.

## Option B: Remote API embeddings

The API provider (`embed_provider.py`) calls an OpenAI-style embeddings endpoint
using only stdlib `urllib` — no `requests`, no SDK, no `torch`. Configure via
environment variables, then rebuild so the skills get embedded:

```bash
export FIRSTLIGHT_EMBED_ENDPOINT=https://api.openai.com/v1/embeddings
export FIRSTLIGHT_EMBED_KEY=sk-...
export FIRSTLIGHT_EMBED_MODEL=text-embedding-3-small

./run.sh build                 # embeds the 50 skills (one network pass)
./run.sh "optimize sql query"  # read embeds the prompt, routes via [embed]
```

The same model must be used for build and read (the vectors have to live in the
same space) — that's why the model is an env var both arms read. API providers
store one vector per skill (no chunking — API models typically have higher token
limits).

## Option C: Bring your own provider

`embed_provider.callable_provider(fn)` wraps any `text -> list[float]` function —
e.g. a local `sentence-transformers` model — if you're willing to take on that
dependency yourself. The router only ever sees the callable; it doesn't care where
the vector came from.

## Cost & honesty notes

- **Ternlight (local)**: zero cost per read. Build-time cost is ~52 skills × ~8
  chunks × 5ms = ~2 seconds total. Read-time cost is one Node subprocess (~50ms
  including startup) for the prompt embed, then pure-stdlib cosine against ~400
  cached chunk vectors (<1ms).
- **API provider**: per read, adds one HTTP round-trip (~100ms) and a fraction of a
  cent. Build-time cost is 50 API calls (once per library change).
- "Zero dependencies" remains true for the default install. With ternlight, the
  honest claim is "Node + a 7MB npm package, no network." With the API provider,
  "stdlib `urllib` plus an endpoint you provide."
