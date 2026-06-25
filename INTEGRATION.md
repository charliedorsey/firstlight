# INTEGRATION — overlaying the lattice on your Claude Code workflow

*Are FirstLight and a Claude Code skills workflow the same kind of thing, or different things?
Short answer: **different things that compose cleanly**, and the seam is already there — no code
change needed to start. Longer answer below.*

> **For the actual wiring**, FirstLight now ships a real Claude Code hook — one command
> (`./install_hook.sh`) registers it as a `UserPromptSubmit` pre-step. See
> `firstlight_lattice/docs/CLAUDE_CODE_HOOK.md`. The sections below are the conceptual
> background (why the two systems compose); the hook doc is the how-to.

---

## 1. The two systems, honestly compared

| | **Your skills / Claude Code workflow** | **firstlight_lattice (this)** |
|---|---|---|
| **Job** | *Execute* a defined task via a multi-step workflow | *Read* an incoming prompt before execution |
| **Unit** | a skill (`SKILL.md` + scripts) invoked in-session | a prompt, read against your library of skills |
| **Shape** | interview → PRD → issues → subagent execution | route + dimensional read + confidence |
| **When** | once requirements are clear, to *do the work* | the moment before, to *see what the work is* |
| **Output** | artifacts (spec, issues, code) | a dashboard: which skill, what character, how sure |
| **Context cost** | progressive disclosure; loaded when invoked | runs *outside* the model — zero token cost |

They are not the same kind of object. Yours is a **workflow engine**. This is a **prompt
reader / router**. The honest framing: **this is the dispatch layer that decides *which* of
your skills a request wants, and whether the request is even well-formed, before your
workflow spends a single token executing.**

That's why it doesn't threaten the skills standard — it sits one level up from it. Your skills
remain exactly as Anthropic defines them. This just reads them.

---

## 2. The compatibility question, answered from the source

Are they even compatible, or just doing different things? The answer is in the loader rather
than in guesswork. The engine's library loader (`semantic_lattice.load_rooms_canonical`):

- **recurses subfolders** (`glob('**/*', recursive=True)`),
- **reads `.md/.txt/.yml/.yaml/.json`**,
- uses the **relative path as each record's id** (so `pdf-filler/SKILL.md` → `pdf-filler__SKILL`),
- skips hidden / `__MACOSX` / contract files.

A Claude skill is, by spec, `skill-name/SKILL.md` — a markdown file in a subfolder, with
optional `scripts/`, `references/`, `assets/` subdirs the agent loads **only on demand**. The
loader is **skills-aware**: when any `SKILL.md` is present in the library it switches to
skills mode and takes exactly **one record per skill directory** (the `SKILL.md`), ignoring
everything under `scripts/ references/ assets/`. So:

> Pointing the lattice at your skills directory works **today, with zero further changes**.
> `./run.sh --rooms ~/.claude/skills "your prompt"` reads your real skills as the library,
> one record per skill, labeled by each skill's frontmatter `name:`.

I verified this against a spec-shaped library (skills with real `references/REFERENCE.md`,
`FORMS.md`, and `assets/*.json` files): the loader returns exactly one record per skill, the
reference/asset files never appear as routes, and routing lands on the correct skill. Without
this awareness a skill's `REFERENCE.md` would compete with — and could outscore — the skill
itself; that hole is closed.

A library with **no** `SKILL.md` (e.g. a plain folder of `.md` prompts) falls back to the
generic rule (every file is its own prompt), so BYO-prompt libraries still work unchanged.

The one real constraint is **corpus size**: the lattice discovers its dimensions *across* the
library, so it needs ≥3 skills to have a space to read in. Below that it tells you cleanly
instead of erroring. Your real library is well past 3.

The reader labels a routed skill by its frontmatter `name:` (e.g. `pdf-processing`, not a
path id), and `--json` adds `display_name` per route plus a top-level `suggested_room_name` —
so a dispatch script can branch on the skill name directly. Both the skills-aware loading and
the name display are already done in this package.

---

## 3. Where it slots into your pipeline

Your sequence (paraphrasing your text): `/grill-with-docs` → `/to-prd` → `/to-issues` →
`/subagent-driven-development`. The lattice has two natural insertion points, both *before*
execution burns tokens:

**(A) Pre-flight dispatch — "which skill does this want?"**
Before you pick a skill by hand, read the raw request against your library:
```bash
./run.sh "the user's raw ask, pasted"
```
The route tells you which skill the request most resembles; the dimensional read tells you its
character (is this a *diagnose* task or a *build* task? high-rigor or exploratory?); the
conviction tells you whether the request is coherent enough to act on or needs an interview
first. This is most useful exactly when you have *many* skills and picking the right one is
itself a decision.

**(B) Prompt hygiene — "is this even well-formed?"**
The lattice's original job is reading a prompt's stakes/openness/scope and flagging the #1
failure: a request that says "fix this" / "it" with no referent. Running it on the user's ask
before `/grill-with-docs` catches the under-specified prompt *before* the interview, so the
interview starts from a known gap rather than discovering it.

Neither replaces a step of yours. Both feed the step that follows them a cleaner input.

---

## 4. Two ways to wire it in

**Option 1 — manual dashboard (zero integration, today).**
Keep it beside your workflow. When a request comes in, run `./run.sh "..."`, read the
dashboard, then proceed into your normal skill pipeline with a clearer picture. This is the
"try it for a week and see if the read earns its place" option. Recommended first.

**Option 2 — a thin dispatch skill (native to your system).**
Wrap the lattice in a Claude skill so it lives *inside* your workflow, the way you displace
workflow logic into scripts that a skill invokes. Sketch:

```
skills/prompt-dispatch/
├── SKILL.md          # "Use this first, to read an incoming request and route it"
└── scripts/
    └── read.sh       # calls firstlight_lattice with --json, returns the route+dims
```

`SKILL.md` instructs the model: *call `scripts/read.sh` on the user's raw request; use the
returned route to choose which downstream skill to invoke, and the conviction to decide
whether to interview first.* The `--json` output is built for exactly this — structured
route + dims + confidence the model can branch on. This is the version that makes the lattice
a first-class citizen of your `/context`-measured, progressive-disclosure system: it costs
nothing until invoked, and when invoked it returns a compact JSON the model acts on.

The progressive-disclosure fit is clean: the dispatch skill's `SKILL.md` is tiny (a few lines
of "when to call this and how to read the result"); the actual reading happens in the script,
out of context, returning only the verdict. That's your own design pattern — workflow logic in
the script, not the prompt — applied to dispatch.

---

## 5. What I'd do, in order

1. **Run it manually for a week (Option 1).** Point `--rooms` at your real skills library and
   read incoming requests against it before you pick a skill. See whether the route + conviction
   actually change your decisions. If they don't earn their place, stop here — no integration debt.
2. **If it earns its place, wrap it as the `prompt-dispatch` skill (Option 2)** so it's native
   and `/context`-free. The `--json` output already carries `suggested_room_name` and per-route
   `display_name`, so the dispatch script can branch on the skill name with no string-munging.
   At that point it's not "my tool beside your workflow" — it's the dispatch layer *of* your
   workflow.

The thing I didn't want to lose — and didn't — is the **model dashboard**: the `prompt reads
as:` dimensional block and the `council conviction` line. That read is the whole point, and
it survives every integration path above. Your skills do the work; this decides which work,
on a clean prompt, before the work starts.

---

## 6. The honest one-liner

Your skills are **workflows that act**. This is a **reader that dispatches**. They're not
competing standards — one routes into the other. The integration is already possible today
(`--rooms` at your skills folder); the only question is whether you want it manual or wired
in as a skill, and that's a "does the read earn its place" question you can answer in a week.
