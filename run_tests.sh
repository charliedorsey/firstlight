#!/usr/bin/env bash
# run_tests.sh — verify FirstLight end to end.
#
#   ./run_tests.sh
#
# Checks both arms: the heavy build/selftest (needs numpy + scikit-learn) and the
# pure-python read + cross-router parity. Skips the heavy parts (with a note) if
# the scientific-Python stack isn't installed, so the pure side can be checked
# on any machine with just Python.

set -uo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
PY="${PYTHON:-python3}"
CORE="$ROOT/firstlight_lattice/core"
PURE="$ROOT/firstlight_lattice/pure_read"
SKILLS="$ROOT/drop_your_skills_here"

if [ -t 1 ]; then G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[1m'; N=$'\033[0m'
else G=""; R=""; Y=""; B=""; N=""; fi
pass=0; fail=0; skip=0; declare -a RES
note() { RES+=("$1"); case "$1" in PASS*) pass=$((pass+1));; FAIL*) fail=$((fail+1));; SKIP*) skip=$((skip+1));; esac; }

HAVE_HEAVY=0
"$PY" -c "import numpy, sklearn" >/dev/null 2>&1 && HAVE_HEAVY=1

printf "\n${B}== build arm (heavy) ==${N}\n"
if [ "$HAVE_HEAVY" = 1 ]; then
  if FIRSTLIGHT_CORE="$CORE" "$PY" "$PURE/build_cache.py" "$SKILLS" /tmp/_fl_test_cache.json; then
    note "PASS build: cache written"
  else note "FAIL build"; fi
else
  printf "  ${Y}numpy/scikit-learn not installed — skipping heavy arm${N}\n"
  printf "  install: %s -m pip install -r requirements.txt\n" "$PY"
  note "SKIP build (no numpy/sklearn)"
fi

printf "\n${B}== read arm (pure python) ==${N}\n"
if [ -f /tmp/_fl_test_cache.json ]; then
  if "$PY" "$PURE/read.py" /tmp/_fl_test_cache.json "write end-to-end tests" >/dev/null; then
    note "PASS read: pure-python route ok"
  else note "FAIL read"; fi
else
  note "SKIP read (no cache; build was skipped)"
fi

printf "\n${B}== cross-router parity (pure == sklearn) ==${N}\n"
if [ "$HAVE_HEAVY" = 1 ] && [ -f /tmp/_fl_test_cache.json ]; then
  if FIRSTLIGHT_CORE="$CORE" "$PY" "$PURE/parity_router.py" "$SKILLS" /tmp/_fl_test_cache.json; then
    note "PASS parity (pure router == sklearn router)"
  else note "FAIL parity"; fi
else
  note "SKIP parity (needs heavy arm to compare against)"
fi

printf "\n${B}== engine selftest ==${N}\n"
if [ "$HAVE_HEAVY" = 1 ]; then
  if "$PY" "$CORE/firstlight.py" --selftest >/dev/null 2>&1; then
    note "PASS selftest"
  else note "FAIL selftest"; fi
else
  note "SKIP selftest (no numpy/sklearn)"
fi

printf "\n${B}== read arm with numpy/sklearn BLOCKED (proves zero-dep) ==${N}\n"
if [ -f /tmp/_fl_test_cache.json ]; then
  if "$PY" - <<'PYEOF'
import sys, importlib.abc, os
for m in list(sys.modules):
    if m.split('.')[0] in ('numpy','sklearn','scipy'): del sys.modules[m]
class B(importlib.abc.MetaPathFinder):
    def find_spec(self, n, p, t=None):
        if n.split('.')[0] in ('numpy','sklearn','scipy'):
            raise ImportError(n+" blocked")
        return None
sys.meta_path.insert(0, B())
sys.path.insert(0, 'firstlight_lattice/pure_read')
import read as RD, pure_router as PR
cache = PR.load_cache('/tmp/_fl_test_cache.json')
r = RD.read_prompt(cache, "scan my dependencies for vulnerabilities")
assert r['routes'], "no route produced under import block"
PYEOF
  then note "PASS zero-dep read (heavy libs import-blocked)"
  else note "FAIL zero-dep read"; fi
else
  note "SKIP zero-dep read (no cache)"
fi

printf "\n${B}== stage-one deliverable gate (two-stage routing) ==${N}\n"
if [ -f /tmp/_fl_test_cache.json ]; then
  if "$PY" - <<'PYEOF'
import sys
sys.path.insert(0, 'firstlight_lattice/pure_read')
import pure_router as PR, deliverable_gate as DG
cache = PR.load_cache('/tmp/_fl_test_cache.json')
gi = cache.get('gate_index')
assert gi, "no gate_index in cache"
# technical prompt -> gate silent (vetoes nothing)
s1, v1 = DG.gate("write end-to-end tests for the checkout flow", gi)
assert not v1, f"technical prompt should veto nothing, vetoed {len(v1)}"
# categorical mismatch -> gate fires (vetoes most of a technical library)
s2, v2 = DG.gate("help me sit with a hard feeling", gi)
assert len(v2) > len(s2), f"human prompt should veto the technical bulk, vetoed {len(v2)}"
# gate never empties the library
assert s2, "gate must never empty the library"
PYEOF
  then note "PASS deliverable gate (silent on technical, fires on mismatch)"
  else note "FAIL deliverable gate"; fi
else
  note "SKIP deliverable gate (no cache)"
fi

printf "\n${B}== Claude Code hook (stdin JSON -> additionalContext envelope) ==${N}\n"
if [ -f /tmp/_fl_test_cache.json ]; then
  if printf '{"prompt":"write end-to-end tests","cwd":"%s"}' "$ROOT" \
       | FIRSTLIGHT_CACHE=/tmp/_fl_test_cache.json "$PY" "$PURE/firstlight_hook.py" \
       | "$PY" -c 'import json,sys; d=json.load(sys.stdin); assert d["hookSpecificOutput"]["hookEventName"]=="UserPromptSubmit"; assert d["hookSpecificOutput"]["additionalContext"]; sys.exit(0)' 2>/dev/null; then
    note "PASS hook emits valid UserPromptSubmit envelope"
  else note "FAIL hook envelope"; fi
  # safety: malformed input must still exit 0 with no block
  if echo 'garbage{{{' | "$PY" "$PURE/firstlight_hook.py" >/dev/null 2>&1; then
    note "PASS hook never blocks on bad input"
  else note "FAIL hook blocked on bad input"; fi
else
  note "SKIP hook test (no cache)"
fi

rm -f /tmp/_fl_test_cache.json
printf "\n${B}== summary ==${N}\n"
for r in "${RES[@]}"; do case "$r" in
  PASS*) printf "  ${G}✓${N} %s\n" "${r#PASS }";;
  FAIL*) printf "  ${R}✗${N} %s\n" "${r#FAIL }";;
  SKIP*) printf "  ${Y}–${N} %s\n" "${r#SKIP }";; esac; done
printf "\n  ${G}%d passed${N}, ${R}%d failed${N}, ${Y}%d skipped${N}\n\n" "$pass" "$fail" "$skip"
[ "$fail" -eq 0 ] && exit 0 || exit 1
