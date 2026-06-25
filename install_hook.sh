#!/usr/bin/env bash
# install_hook.sh — wire FirstLight into Claude Code as a UserPromptSubmit pre-step.
#
#   ./install_hook.sh [path-to-your-skills]
#
# Does three things:
#   1. builds the routing cache from your skills library (needs numpy + sklearn,
#      one time — the per-prompt hook itself is pure Python and needs nothing).
#   2. merges a UserPromptSubmit hook into ~/.claude/settings.json WITHOUT
#      clobbering any hooks you already have.
#   3. prints how to verify and how to remove it.
#
# The hook runs on every prompt, reads it, and injects a short advisory routing
# read as context before Claude responds. It never blocks: any failure = the
# prompt proceeds untouched.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PURE="$HERE/firstlight_lattice/pure_read"
HOOK="$PURE/firstlight_hook.py"
SKILLS="${1:-$HERE/drop_your_skills_here}"
PY="${PYTHON:-python3}"
SETTINGS="$HOME/.claude/settings.json"

echo "FirstLight → Claude Code hook installer"
echo

# ---- 1. build the cache ----------------------------------------------------
echo "1) building routing cache from: $SKILLS"
if ! "$PY" -c "import numpy, sklearn" >/dev/null 2>&1; then
  echo "   error: building the cache needs numpy + scikit-learn (one time)." >&2
  echo "          install: $PY -m pip install -r \"$HERE/requirements.txt\"" >&2
  echo "          (the hook itself, which runs per-prompt, needs nothing.)" >&2
  exit 1
fi
CACHE="$HERE/.firstlight_cache_$("$PY" - "$SKILLS" <<'PYEOF'
import sys, hashlib, os
print(hashlib.sha256(os.path.abspath(sys.argv[1]).encode()).hexdigest()[:12])
PYEOF
).json"
FIRSTLIGHT_CORE="$HERE/firstlight_lattice/core" "$PY" "$PURE/build_cache.py" "$SKILLS" "$CACHE"
echo "   cache: $CACHE"
echo

# ---- 2. merge the hook into settings.json ----------------------------------
echo "2) registering the UserPromptSubmit hook in $SETTINGS"
mkdir -p "$(dirname "$SETTINGS")"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"

# Use python to merge safely: add our hook only if an identical one isn't present.
FIRSTLIGHT_CACHE_EXPORT="$CACHE" HOOK_PATH="$HOOK" PY_BIN="$PY" "$PY" - "$SETTINGS" <<'PYEOF'
import json, os, sys
settings_path = sys.argv[1]
hook_cmd = f'FIRSTLIGHT_CACHE="{os.environ["FIRSTLIGHT_CACHE_EXPORT"]}" {os.environ["PY_BIN"]} "{os.environ["HOOK_PATH"]}"'
try:
    with open(settings_path) as f:
        settings = json.load(f)
except Exception:
    settings = {}
hooks = settings.setdefault("hooks", {})
ups = hooks.setdefault("UserPromptSubmit", [])
# already installed? (look for our hook path in any command)
installed = any(
    os.environ["HOOK_PATH"] in h.get("command", "")
    for grp in ups for h in grp.get("hooks", [])
)
if installed:
    print("   already installed — updating cache path")
    for grp in ups:
        for h in grp.get("hooks", []):
            if os.environ["HOOK_PATH"] in h.get("command", ""):
                h["command"] = hook_cmd
else:
    ups.append({"matcher": "", "hooks": [{"type": "command", "command": hook_cmd, "timeout": 15}]})
    print("   added FirstLight UserPromptSubmit hook")
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
PYEOF
echo

# ---- 3. verify + uninstall note --------------------------------------------
echo "3) quick self-check (simulating a prompt through the hook):"
printf '{"prompt":"write end-to-end tests for the checkout flow","cwd":"%s"}' "$HERE" \
  | FIRSTLIGHT_CACHE="$CACHE" "$PY" "$HOOK" \
  | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print("   ✓ hook returned context:\n"); print("\n".join("     "+l for l in d.get("hookSpecificOutput",{}).get("additionalContext","(none)").splitlines()))'
echo
echo "Done. Restart Claude Code (or run /hooks to confirm)."
echo "To remove: delete the FirstLight entry under hooks.UserPromptSubmit in $SETTINGS"
echo "To rebuild after changing skills: ./install_hook.sh \"$SKILLS\""
