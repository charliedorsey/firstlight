# Using FirstLight as a Claude Code pre-step (UserPromptSubmit hook)

FirstLight can run automatically before every prompt in Claude Code, injecting a
short routing read as context so Claude starts each turn knowing which skill the
request resembles, the expected output shape, the compute budget, and how
confident the read is. It is advisory — it never blocks a prompt and never
constrains the response.

## One-command install

```bash
./install_hook.sh                       # uses the bundled 50-skill starter library
./install_hook.sh ~/.claude/skills      # or point it at YOUR skills
```

That script: builds the routing cache once (needs numpy + scikit-learn for the
build only), merges a `UserPromptSubmit` hook into `~/.claude/settings.json`
without disturbing any hooks you already have, and runs a self-check. Restart
Claude Code (or run `/hooks`) to confirm.

## What gets injected

On each prompt, Claude receives a block like:

```
[FirstLight — advisory routing read, not a directive]
closest skill: e2e-test-writer__SKILL  (score 0.160, via coherence)
alternatives: unit-test-generator__SKILL (0.08), github-actions-setup__SKILL (0.07)
compute budget: MODERATE
turn shape: WRITE (answer directly) · INLINE (produce a file only if asked)
posture: small scope — keep it short
(FirstLight suggests; you decide. It does not constrain your response.)
```

When the deliverable gate fires (a categorical output-shape mismatch), it adds a
line like `output-shape: HUMAN; ruled out 48 categorically-mismatched skill(s)`,
and low-confidence reads are flagged so Claude knows to treat them as weak hints.

## How it meets the hook contract

- **Input**: reads the hook payload as JSON on stdin (`{"prompt": ..., "cwd": ...}`).
- **Output**: emits `{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
  "additionalContext": "..."}}` and exits 0 — the structured-JSON path, which is
  the reliable way to add context for this event.
- **Never blocks**: empty/malformed input, a missing cache, or any internal error
  all result in exit 0 with no context. A hook failure can never stop your prompt.
- **Fast**: the per-prompt read is pure Python standard library and runs in
  milliseconds, far inside the 30-second UserPromptSubmit budget (the hook is
  registered with a 15s timeout as a safety margin).
- **Zero runtime deps**: only the one-time cache build uses numpy/scikit-learn.
  The hook itself imports nothing outside the standard library — verified by
  running it with numpy/sklearn/scipy import-blocked.

## Cache & staleness

The hook resolves its cache from `$FIRSTLIGHT_CACHE` (the installer sets this in
the registered command), else the newest `.firstlight_cache_*.json` near the
install. If you add or edit skills, re-run `./install_hook.sh <skills>` to rebuild;
the read path also fingerprints the library and the dashboard will note staleness.

## Manual settings.json (if you prefer)

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "FIRSTLIGHT_CACHE=\"/abs/path/.firstlight_cache_XXXX.json\" python3 \"/abs/path/firstlight_lattice/pure_read/firstlight_hook.py\"",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

## Removing it

Delete the FirstLight entry under `hooks.UserPromptSubmit` in
`~/.claude/settings.json`. Nothing else is touched.
