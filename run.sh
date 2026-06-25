#!/usr/bin/env bash
# firstlight_lattice — prompt reader, in two arms.
#
#   ./run.sh build                          analyze your skills ONCE (needs numpy
#                                           + scikit-learn); writes a cache.
#   ./run.sh "your prompt text"             read a prompt against your skills
#                                           (PURE PYTHON — zero dependencies).
#   ./run.sh --json "your prompt"           machine-readable read
#   ./run.sh --selftest                     verify the engine (uses the heavy arm)
#   ./run.sh --rooms PATH build             build a cache for a different library
#   ./run.sh --rooms PATH "your prompt"     read against that library's cache
#
# The split: BUILD runs the corpus analysis (SVD / tf-idf / clustering) and needs
# the scientific-Python stack. READ routes a live prompt from the cache BUILD
# wrote and needs nothing but Python — so the per-turn path is free. If you add
# or edit skills, READ warns that the cache is stale and tells you to rebuild;
# it never silently routes against the wrong library, but it never blocks either.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE="$HERE/firstlight_lattice/core"
PUREDIR="$HERE/firstlight_lattice/pure_read"
ENGINE="$CORE/firstlight.py"
SKILLS_DEFAULT="$HERE/drop_your_skills_here"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "error: python3 not found. Install Python 3 and re-run." >&2
  exit 1
fi

# ---- parse an optional leading --rooms PATH --------------------------------
ROOMS="$SKILLS_DEFAULT"
if [ "${1:-}" = "--rooms" ]; then
  ROOMS="${2:?--rooms needs a path}"
  shift 2
fi
# cache path is derived from the library path so multiple libraries don't collide
CACHE="$HERE/.firstlight_cache_$("$PY" - "$ROOMS" <<'PYEOF'
import sys, hashlib, os
print(hashlib.sha256(os.path.abspath(sys.argv[1]).encode()).hexdigest()[:12])
PYEOF
).json"

require_heavy_deps() {
  if ! "$PY" -c "import numpy, sklearn" >/dev/null 2>&1; then
    echo "error: this step needs numpy + scikit-learn, which aren't installed." >&2
    echo "       install them with:" >&2
    echo "         $PY -m pip install -r requirements.txt" >&2
    echo "       (only the one-time 'build' uses these; the per-turn read is" >&2
    echo "        pure Python and needs nothing.)" >&2
    exit 1
  fi
}

build_cache() {
  require_heavy_deps
  # corpus-size guard: axis discovery needs >=3 records to fit
  COUNT=$(find "$ROOMS" -type f \( -name '*.md' -o -name '*.txt' -o -name '*.yml' \
          -o -name '*.yaml' -o -name '*.json' \) \
          ! -name 'ROOM_CONTRACT.md' ! -name 'LICENSE.skills.txt' ! -name '.*' \
          2>/dev/null | wc -l | tr -d ' ')
  if [ "${COUNT:-0}" -lt 3 ]; then
    echo "error: '$ROOMS' has ${COUNT} readable file(s); need at least 3 to" >&2
    echo "       discover dimensions across a corpus." >&2
    exit 2
  fi
  FIRSTLIGHT_CORE="$CORE" "$PY" "$PUREDIR/build_cache.py" "$ROOMS" "$CACHE"
}

# ---- selftest: uses the heavy engine directly ------------------------------
if [ "${1:-}" = "--selftest" ]; then
  require_heavy_deps
  exec "$PY" "$ENGINE" --selftest
fi

# ---- build subcommand ------------------------------------------------------
if [ "${1:-}" = "build" ]; then
  build_cache
  echo "cache ready. read with:  ./run.sh \"your prompt\"" >&2
  exit 0
fi

# ---- no args: usage --------------------------------------------------------
if [ "$#" -eq 0 ]; then
  echo "usage: ./run.sh build              (analyze skills once)" >&2
  echo "       ./run.sh \"your prompt\"      (read — pure python)" >&2
  echo "       ./run.sh --selftest" >&2
  exit 64
fi

# ---- read path (default): pure python, auto-build cache if missing ---------
if [ ! -f "$CACHE" ]; then
  echo "note: no cache yet for this library — building it once..." >&2
  build_cache
fi
exec "$PY" "$PUREDIR/read.py" "$CACHE" "$@"
