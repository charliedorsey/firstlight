# FirstLight Lattice

**What it is:** a real, runnable tool built on the same dimensional-analysis pipeline that
powers the chess engine, turned onto **prompts and Claude Code skills**. It reads an incoming
prompt against your skill library and tells you which skill it most resembles, the prompt's
character on a set of discovered dimensions, and how confident the match is.

## The 30-second version (two commands)

```bash
pip install -r requirements.txt          # one-time, for the build step only
./run.sh build                           # analyze the skills library once
./run.sh "write unit tests for the payment module"
```

(If you skip `build`, the first read does it for you.) It reads your prompt
against whatever skills are in `drop_your_skills_here/` (50 example skills ship
in it) and prints **which skill the request most resembles** (the route) and
**how confident** the match is. It never refuses — it tells you how sure it is
and hands the decision back.

**Two arms, and why it matters:** the one-time `build` runs the corpus analysis
(SVD / tf-idf / clustering) and needs `numpy` + `scikit-learn`. Every per-turn
`read` after that is **pure Python standard library — zero dependencies** —
routing from the cache `build` wrote. (Proven byte-identical to the heavy router,
and verified to run with numpy/scikit-learn import-blocked.) If you add or edit
skills, `read` warns the cache is stale and tells you to rebuild — it never
silently routes against the old library, and never blocks you either.

```bash
./run.sh --selftest                       # verify the engine
./run.sh --json "your text"               # machine-readable (route + dims + confidence)
./run.sh --rooms ~/.claude/skills "..."   # read against your REAL skills library
```

## Plug it into Claude Code (runs before every prompt)

```bash
./install_hook.sh                         # bundled starter skills
./install_hook.sh ~/.claude/skills        # or your own skills
```

This registers FirstLight as a `UserPromptSubmit` hook, so it runs as the first
step on every prompt and injects a short advisory routing read (closest skill,
expected output shape, compute budget, confidence) as context before Claude
responds. It is advisory only — it never blocks a prompt and never constrains the
reply, and any failure silently passes the prompt through untouched. The per-prompt
hook is pure stdlib (only the one-time cache build needs numpy/sklearn). Details
and the manual `settings.json` form: `firstlight_lattice/docs/CLAUDE_CODE_HOOK.md`.

## What it is, and what it is NOT

It is **not** a replacement for your Claude Code / skills workflow. It does a *different* job and sits *inside* yours:

- **Your skills** are workflows that **act** (interview -> PRD -> issues -> subagent execution).
- **FirstLight** is a reader that **dispatches**: it reads the *moment before* execution — which skill an incoming request resembles, the request's character (diagnose<->build, rigor<->loose), and whether the prompt is even well-formed — so the right skill gets invoked on a clean prompt.

They compose; they don't compete. `INTEGRATION.md` lays out the full overlay, including the two wiring options (manual dashboard today, or a thin `prompt-dispatch` skill that calls it via `--json`). It runs **outside the model**, so it costs zero tokens.

## Skills-aware

A Claude skill is `skill-name/SKILL.md` with optional `scripts/`, `references/`,
`assets/` loaded on demand. The library loader is **skills-aware**: when it sees any
`SKILL.md` it takes exactly **one record per skill directory** (the `SKILL.md`) and
ignores the on-demand files — so a skill's `references/REFERENCE.md` never competes
with the skill itself as a routing target. The 50-skill starter library loads as
exactly 50 records, each labeled by its skill directory name; `--json` returns each
route as `{room, score, via}` so a dispatch script can branch on the skill name
directly (see the JSON shape under "Machine-readable output" below).

Point `--rooms` at a folder with **no** `SKILL.md` and the loader falls back to
generic mode — every file becomes its own record — so plain prompt libraries work
unchanged.

## The architecture (same engine as the chess work)

The chess engine reads a *position* across six dimensions, lets a council of readers vote, and emits a conviction. FirstLight reads a *prompt* the same way — same kernel, different manifold. **Build:** every room/skill is read through three arms — semantic (TF-IDF->SVD subject axes), structural (surface shape), and **move** (a profile over ~10 named cognitive moves: CONSTRAIN, EVIDENCE, VERIFY, FORMAT, TONE, EXEMPLAR...) -> a 13-axis candidate pool -> select 6 orthogonal axes, re-keyed onto the same `[-1,+1]` ELM lattice the engine uses. **Read:** route to the closest room with an honest confidence flag, project the live prompt through the *same* fitted transforms, and let a council read conviction. Every output is stamped `claim_status: advisory_not_truth`.

The standout capability: **point it at your own library and the dimensions re-discover themselves from your corpus** — it renames the axes to fit your skills/prompts and surfaces the cognitive moves inside them. That makes the otherwise-tacit "dense context packet" method legible and measurable in your toolkit's terms.

## Honest notes (kept, per the discipline of this whole bundle)

- The move-signal is computed by regex on the live prompt today; it's **diagnostic** (it colors the character read), not the primary router. A non-regex sensor is the intended replacement, and the code says so.
- Lexical routing has known misses ("teach me X" / "summarize this" can land on a near-neighbor). Because the tool is advisory and reports confidence, this annotates rather than misleads — which is *why* the route is a suggestion, not a verdict.
- Dimension discovery needs >=3 files in a library to have a space to fit; below that it says so cleanly instead of erroring.

A tool that reports its own confidence and its own known misses is the same "tells you when you're fooling yourself" discipline as the compressor that reports its losses and the paper that marks its own novelty boundary.

## What's here

```
firstlight/
+- run.sh               <- build the cache + read a prompt (the two-arm CLI)
+- run_tests.sh         <- verify everything (8 checks)
+- install_hook.sh      <- wire it into Claude Code as a pre-prompt hook
+- requirements.txt     <- numpy + scikit-learn (for the one-time build only)
+- drop_your_skills_here/   <- your skill folders; 50 example skills ship so it works out of the box
+- firstlight_lattice/
   +- pure_read/        <- THE READ ARM (pure stdlib): build_cache, pure_router, read,
   |                       deliverable_gate, embed_provider, firstlight_hook, parity_router
   +- core/             <- THE BUILD ARM (heavy): semantic_lattice, dim_*, council, move_*, turn_dashboard, ...
   +- rooms/            <- a 20-room example library (posture-differentiated; an alternate `--rooms` target)
   +- docs/             <- architecture, two-stage routing, embeddings, the Claude Code hook, routing experiments
   +- README.md         <- the engine's own README (output format, flags)
```

The everyday path is `pure_read/` (zero-dependency). `core/` only runs during the
one-time `build`. `rooms/` is a second example library you can point `--rooms` at.
