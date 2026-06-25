# FirstLight — read this first

Plain version, since the internals use their own vocabulary.

**What it is:** a dispatch layer. Given an incoming request and a library of options, it tells you which option the request most resembles and how confident it is. Point it at `~/.claude/skills` and the "options" are your skills — it reads each `SKILL.md` as one record and routes against them.

**Where it sits:** in front of execution, not inside it. It runs outside the model, so it costs zero tokens. It does not replace your workflow; it reads the moment *before* a workflow fires — which skill does this want, and is the prompt even well-formed.

**What's honest about it:** it's a prototype. On clear requests it routes with high conviction; on ambiguous ones it reports low conviction rather than guessing confidently, and every readout is advisory — it suggests, you decide. Run `./run.sh --selftest` and you'll see both the confident and the unconfident cases. I'd rather you see where it's weak than oversell where it's strong.

**Why it's the bridge artifact:** it's the most direct test of whether my approach and yours connect, because it reads *your* library in your terms. If it's useful, it's useful as a layer on top of the stack you already run — not a thing you'd have to adopt wholesale.

```bash
./run.sh "write end-to-end tests for the checkout flow"   # against the 50 default skills
./run.sh --rooms ~/.claude/skills "your real prompt"        # against your real library
./run.sh --selftest                                         # see confident + unconfident routing
```

**Default skills:** `drop_your_skills_here/` ships with 50 ready-made skills (the open `claude-skills-free` set, MIT) so it works out of the box. **Replace them with your own** — see `drop_your_skills_here/README.md`. The tool is most useful read against the library you actually run.

The `firstlight_lattice/` folder holds the routing math and its own naming conventions; you don't need to read it to use the tool.

## What's missing — the piece that doesn't exist yet

Be straight about the current limitation, because it's the real one. Right now FirstLight links the prompt and the skill by **similarity** — it reads the prompt's character and the skill's character on discovered dimensions and matches the ones that resemble each other. That's useful, but it's matching *surface shape*, not *fit*.

The piece that's actually needed, and does not exist yet: **project the type of response the prompt wants to receive, and link that to the type of deliverable the skill is wired to produce.** A prompt implicitly asks for a *kind* of output — a runnable script, a decision, a critique, a verified proof, a short answer. A skill is built to *emit* a kind of output. Best matching is response-type ↔ deliverable-type, not similarity of vocabulary. Two requests can read nearly identical on the current dimensions yet want completely different deliverables; two skills can look similar yet produce different artifacts. Until the router models *what the prompt wants back* and *what the skill produces* and matches those, it's approximating the right answer with resemblance. That projection layer is the next real step, and it's the difference between "which skill looks like this" and "which skill will actually give this prompt what it's asking for."
