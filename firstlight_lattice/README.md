# firstlight_lattice

A prompt-reading tool. You give it a library of prompt files (the "rooms"), and for an
incoming request it tells you **which of your prompts the request most resembles**, reads
the request's **character** along a set of discovered dimensions, and reports how
**confident** the match is. It only ever *suggests* — the reader (you, or an AI) always
decides. Nothing is ever forced.

## Run it

```bash
# from the firstlight/ root, the simplest entry point is run.sh:
./run.sh --selftest                       # verify it works
./run.sh "help me debug this KeyError"    # read a prompt against your skills
./run.sh --json "help me debug this..."   # machine-readable
./run.sh --rooms /path/to/your/prompts "…" # use YOUR own prompt library

# or call the engine directly (advanced):
cd firstlight_lattice/core
python3 firstlight.py --selftest
```

With no `--rooms`, it uses the bundled 23-room library. Point `--rooms` at a folder of
`.md`/`.txt`/`.json`/`.yml`/`.yaml` prompt files to read against your own library — breadth/soul and the
candidate dimensions are recomputed across whatever corpus you give it.

## What the output means

```
routes to (advisory):              ← the suggestion(s): which room the prompt resembles
  0.099  debug_room_v1  [...]         score = match strength; via = which router stage
         ·room: breadth -0.64, soul +0.09   ← properties OF THE ROOM (see below)

prompt reads as:                   ← the prompt's CHARACTER on the selected dimensions
  +0.50  what's wrong (diagnose)      each line: where the prompt sits on one named axis

council conviction: 3/5            ← how coherently the prompt's dims agree (advisory)
```

Plain-language model:

- **semantic route locates the room** — the primary signal: subject-surface resemblance.
- **pooled dims read prompt character** — where the prompt sits on the discovered axes
  (e.g. "what's wrong ↔ what's right"). Advisory colour, not a route.
- **council conviction is advisory** — how coherently those dims point one way.
- **breadth / soul are room properties** — corpus-relative facts about each *room*
  (breadth = how many cognitive moves it exercises; soul = load-bearing density),
  computed across your library. A routed prompt inherits its destination room's values.
- **confidence: low vs clear** — a weak top score, or a tiny gap to the runner-up, reads
  as LOW CONFIDENCE: the closest suggestion is still shown, but don't lean on it. There is
  **no "no room" verdict** — the lattice never refuses, it just tells you how sure it is.
- **claim_status = advisory_not_truth** — every readout is a suggestion. The AI decides.

## Layout

```
core/        the engine. Entry point: firstlight.py
  firstlight.py        build + run the runtime (the thing you call)
  semantic_lattice.py  the router (coherence → tf-idf) + structural face
  dim_nomenclature.py  candidate dims: orient + ELM-key + locked names + project_prompt
  dim_pool.py          assemble the 13-dim candidate pool from 3 arms
  dim_select.py        select the 6 council dims (combined variance + orthogonality)
  council.py           conviction read over a dim vector
  breadth.py soul.py   corpus-relative room property axes
  ... (move_*, prompt_manifold, grammar_seed, compose, router) supporting modules
rooms/       an example prompt library (20 rooms) + ROOM_CONTRACT.md
docs/DIM_BREAKDOWN.md / docs/DIM_NOMENCLATURE.md   what each dimension measures + its name
docs/DATAFLOW.md                              how a prompt flows through build + read
docs/ROOMS_INDEX.md                           all 20 rooms + what each is for
MANIFEST.json                            file inventory (regenerated from the bundle)
```

See `docs/ROOMS_INDEX.md` for the room library, `docs/DATAFLOW.md` for how routing works, and
`docs/DIM_BREAKDOWN.md` / `docs/DIM_NOMENCLATURE.md` for what the character dimensions mean.

## Honest notes

- The move-signal (cognitive-move profile) is computed on the live prompt via regex. It is
  **diagnostic** — it colours the character read; it does not primary-route. A future
  non-regex sensor is intended to replace it.
- Lexical routing has known misses (e.g. "teach me X" / "summarize this" can land on a
  near-neighbour). Because the tool is advisory and reports confidence, this annotates
  rather than misleads — but it's why the route is a suggestion, not a verdict.
