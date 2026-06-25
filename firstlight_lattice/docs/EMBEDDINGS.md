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

## Enabling it

The reference provider (`embed_provider.py`) calls an OpenAI-style embeddings
endpoint using only stdlib `urllib` — no `requests`, no SDK, no `torch`. Configure
via environment variables, then rebuild so the skills get embedded:

```bash
export FIRSTLIGHT_EMBED_ENDPOINT=https://api.openai.com/v1/embeddings
export FIRSTLIGHT_EMBED_KEY=sk-...
export FIRSTLIGHT_EMBED_MODEL=text-embedding-3-small

./run.sh build                 # now also embeds the 50 skills (one network pass)
./run.sh "optimize sql query"  # read embeds the prompt, routes via [embed]
```

The same model must be used for build and read (the vectors have to live in the
same space) — that's why the model is an env var both arms read.

## Bring your own provider

Don't want an API? `embed_provider.callable_provider(fn)` wraps any
`text -> list[float]` function — e.g. a local `sentence-transformers` model — if
you're willing to take on that dependency yourself. The router only ever sees the
callable; it doesn't care where the vector came from.

## Cost & honesty notes

- Per read, the embedding tier adds one HTTP round-trip (~100ms) and a fraction of
  a cent. If that's unacceptable for a given use, leave embeddings off; the lexical
  router is 90% accurate on the probe set without them.
- The build-time embedding pass costs 50 embedding calls (once per library change).
- "Zero dependencies" remains true for the default install. With embeddings on, the
  honest claim is "no heavy dependencies — stdlib `urllib` plus an embeddings
  endpoint you provide."

## Building our own embeddings (future)

A from-scratch embedding model is a real project and deliberately out of scope for
now. The provider interface is the seam where it would plug in later with no change
to the router: implement `text -> list[float]` and pass it as the provider.
