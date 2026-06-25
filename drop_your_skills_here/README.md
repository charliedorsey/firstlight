# drop_your_skills_here — replace these with your own

This folder is what FirstLight reads by default (`./run.sh "your prompt"` routes against whatever is in here).

It currently ships with **50 default skills** — the open `claude-skills-free` set — so the tool works out of the box and you can see real routing immediately. They are stored in the real Claude-skill shape, one directory per skill:

```
drop_your_skills_here/
  e2e-test-writer/SKILL.md
  api-error-handler/SKILL.md
  ...
```

**You should replace these with your own.** FirstLight is most useful read against the library you actually run. Two ways:

1. Point it at your real library without touching this folder:
   ```
   ./run.sh --rooms ~/.claude/skills "your prompt"
   ```
2. Or make your skills the default: delete these and drop your own `skill-name/SKILL.md` directories in here, then `./run.sh "your prompt"`.

How it reads them: if any `SKILL.md` is present, FirstLight is in **skills-aware mode** — exactly one record per skill directory (its `SKILL.md`), ignoring `scripts/`, `references/`, and `assets/` so a skill's reference file never competes with the skill itself. A folder with no `SKILL.md` falls back to treating every `.md`/`.txt`/`.yml`/`.json` as its own prompt record. It needs at least 3 records to discover dimensions across the corpus.

Nothing here is sacred — the defaults are scaffolding. The point is your library.

## Attribution

The 50 bundled example skills are **not** original to this project. They are the
`claude-skills-free` set, copyright (c) 2026 Samarth Bhamare, used and
redistributed here under the MIT License (full text in `LICENSE.skills.txt`).
They are included only as a ready-made starter corpus so the tool runs out of
the box; all credit for them belongs to the original author. If you replace them
with your own skills, this attribution no longer applies.
