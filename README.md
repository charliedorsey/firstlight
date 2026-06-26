# FirstLight Lattice

**What it is:** a real, runnable tool built on a dimensional-analysis pipeline, aimed at **prompts and Claude Code skills**. Before a request is acted on, it reads the prompt and returns an advisory dashboard: which skill actually *fits* it (routed by deliverable, not just vocabulary), where the prompt sits on a set of discovered dimensions with a confidence per dimension, what response posture and compute budget it warrants, and which failure modes that coordinate tends to trigger. It runs outside the model at zero token cost and never decides — it reports and hands the choice back.

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

## The two things it actually does

**1 · Routes by deliverable, not by vocabulary (two-stage routing).** A flat similarity score lets a
strong word-match override a categorical mismatch — "write me a poem about debugging" routes to a debug
skill on the word "debugging." FirstLight routes in two stages: a **deliverable gate**
(`pure_read/deliverable_gate.py`) first vetoes skills whose *output world* (technical / human / creative)
is categorically wrong for what's asked, then semantic discrimination ranks only the survivors. A
categorically-wrong skill can't win even if its words match, because it's removed before scoring. See
`docs/TWO_STAGE_ROUTING.md`.

**2 · Reads the turn as a calibrated coordinate (the dashboard).** Beyond routing, `core/turn_dashboard.py`
places the request on six axes — stakes, register, form, openness, urgency, scope — each with its own
confidence, and surfaces the cross-term tensions ("big ask, little time"; "emotional AND urgent: possible
distress"), the compute budget, the suggested rooms, and watch-flags for the failure modes that
coordinate invites. It flags its own thin reads (a dimension on a single keyword is marked brittle, not
asserted) rather than projecting false confidence.

## The architecture

FirstLight reads a *prompt* across six dimensions, lets a council of readers vote, and emits a conviction. **Build:** every room/skill is read through three arms — semantic (TF-IDF->SVD subject axes), structural (surface shape), and **move** (a profile over ~10 named cognitive moves: CONSTRAIN, EVIDENCE, VERIFY, FORMAT, TONE, EXEMPLAR...) -> a 13-axis candidate pool -> select 6 orthogonal axes, re-keyed onto the `[-1,+1]` ELM lattice. **Read:** route to the closest room with an honest confidence flag, project the live prompt through the *same* fitted transforms, and let a council read conviction. Every output is stamped `claim_status: advisory_not_truth`.

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
