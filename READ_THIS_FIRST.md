# FirstLight — read this first

Plain version, since the internals use their own vocabulary.

**What it is:** a turn-start situating layer for an LLM. Before a request is acted on, FirstLight reads
it and produces an *advisory dashboard*: where the request sits in a 6-dimension manifold (with a
confidence per dimension), what response posture it's asking for, which of your skills/rooms actually
fit it, how much compute it warrants, and which known failure modes this kind of request tends to
trigger. It runs **outside the model, at zero token cost**, and it **never decides** — every readout is
a suggestion the model (or you) is free to override.

**The one-line version:** it tells the model *where it is* before it acts — and refuses to take the wheel.

**Where it sits:** in front of execution, not inside it. It reads the moment *before* a workflow fires —
which skill does this want, what does this prompt actually want back, how confident should we be, and is
this even a coordinate where confident action is safe.

## Two things it does

**1 · Routes by deliverable, not by vocabulary.** Most routers match a prompt to a skill by word
similarity, so "write me a poem about debugging" routes to a debug skill on the word "debugging."
FirstLight routes in two stages: first a **deliverable gate** vetoes skills whose *output world*
(technical / human / creative) is categorically wrong for what the prompt asks for, then semantic
discrimination ranks only the survivors. A categorically-wrong skill can't win even if its words match,
because it's removed before scoring. This is the response-type to deliverable-type projection — it is
built, not aspirational (`pure_read/deliverable_gate.py`).

**2 · Reads the turn as a calibrated coordinate.** Beyond routing, the dashboard places the request on
six axes — **stakes, register, form, openness, urgency, scope** — each with its own confidence, and
surfaces the cross-term tensions ("big ask, little time"; "emotional AND urgent: possible distress"),
the compute budget the request warrants, and watch-flags for the failure modes that coordinate invites.
It knows when its own read is thin: a dimension resting on a single keyword is flagged as brittle rather
than asserted. (`core/turn_dashboard.py`)

## Try it

```bash
./run.sh build                                   # analyze your skills ONCE (numpy+sklearn); writes a cache
./run.sh "write end-to-end tests for checkout"   # read a prompt (PURE PYTHON, zero deps)
./run.sh --rooms ~/.claude/skills "your prompt"  # read against your real skill library
./run.sh --selftest                              # verify the engine
```

Point `--rooms` at `~/.claude/skills` and each `SKILL.md` becomes one record it routes against. It ships
with 50 ready-made skills (the open `claude-skills-free` set, MIT) so it works out of the box — replace
them with your own.

## The architecture, briefly (why it's free per turn)

FirstLight splits into a heavy **build** arm and a free **read** arm:

- **build** (once, when your library changes): discovers the dimensions, fits tf-idf, builds the
  coherence matrix — numpy + scikit-learn — and writes a plain-JSON cache.
- **read** (every turn): routes the live prompt against the cache in **pure Python standard library,
  zero dependencies.** The per-turn path needs nothing installed.

The read arm is a faithful reimplementation of the heavy router, verified two ways: **parity**
(`parity_router.py` asserts the pure router returns the identical `(room, score, via)` ranking as the
sklearn router, to 3-decimal precision, across a probe set) and **isolation** (the read path routes
correctly with numpy/scikit-learn/scipy blocked from import). See
`firstlight_lattice/docs/ARCHITECTURE_TWO_ARMS.md` and `docs/TWO_STAGE_ROUTING.md`.

## The governance spine (the part that matters most)

FirstLight is a *reflexive* instrument — the model reading its own turn-situation. That's powerful and
genuinely dangerous: a self-reading tool that could *decide* would be self-reference with no membrane.
So the advisory-only contract is load-bearing, not decorative, and it's enforced as a strict layering:

- **sensors** observe raw prompt-surface facts — no inference, no scoring.
- **transforms** normalize sensor facts into the manifold + cross-terms — calculate, never judge.
- **reads** interpret cross-terms into strength-tagged *suggestions* — a read may suggest; it may not decide.
- **the model is the sovereign choice layer.** The tool briefs; it does not route past you.

A wrong suggestion costs a glance. Nothing gates. That restraint is the design, not a limitation.

## What's honest about it

It's a working tool with a clear scope, and it's candid about the edges. The **manifold coordinate** and
the **watch flags** are the reliable, load-bearing signals; the 5-animal "council" vote is advisory
texture (a 2026-05 measurement found council *direction* doesn't robustly track work-type, so routing
keys off the coordinate, not the vote — and the code says so). On short or vague prompts the read
confidence is honestly low rather than confidently wrong. You'll see both the confident and the
unconfident cases in `--selftest`. The tool would rather show you where it's thin than oversell where
it's strong — which is the whole point of building a calibrated instrument instead of a confident one.

---

MIT licensed. Single-file read modules, stdlib-only on the per-turn path, `--selftest` on the engine —
built to be handed forward and re-checked. `ELM = 2 ** (1/24)`.
