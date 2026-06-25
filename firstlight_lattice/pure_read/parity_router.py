#!/usr/bin/env python3
"""
parity_router.py — assert the pure-python router matches the sklearn router.

For each probe prompt it runs BOTH routers over the same corpus and asserts the
full top-k (room, score, via) ranking is identical at 3-decimal precision (the
same rounding the original _rank uses).

Usage:
    FIRSTLIGHT_CORE=/path/to/core \
    python3 parity_router.py <rooms_folder> <cache.json>
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pure_router as PR

_core = os.environ.get('FIRSTLIGHT_CORE')
if _core:
    sys.path.insert(0, _core)
import semantic_lattice as SL


PROBES = [
    "write end-to-end tests for the checkout flow",
    "add redis caching to my api",
    "my dockerfile build is huge, slim it down",
    "scan my deps for vulnerabilities",
    "set up github actions ci",
    "help me debug this KeyError in my python code",
    "generate a rest api scaffold for users",
    "optimize this slow sql query",
    "add dark mode to my react app",
    "write a migration to add a column",
    "set up structured logging in python",
    "create a rate limiter for my endpoints",
    "sanitize user input to prevent xss",
    "what is 2+2",
    "build a websocket server",
    "audit my dependencies for known CVEs",
    "make a multi-stage dockerfile",
    "analyze this stack trace",
    "set up pytest for my project",
    "add caching strategy with TTLs",
]


def sklearn_route(prompt, lattice, k=3):
    return lattice.route(prompt, k=k)


def main():
    folder = sys.argv[1]
    cache_path = sys.argv[2]
    cache = PR.load_cache(cache_path)
    rooms = dict(SL.load_rooms_canonical(folder))
    lattice = SL.SemanticLattice(rooms)

    fails = 0
    print(f"{'prompt':46s} {'sklearn':28s} {'pure':28s} ok")
    print("-" * 112)
    for p in PROBES:
        sk = sklearn_route(p, lattice)
        pr = PR.route(p, cache)
        ok = (sk == pr)
        if not ok:
            fails += 1
        sk_top = f"{sk[0][0][:18]}/{sk[0][1]:.3f}/{sk[0][2][:4]}" if sk else "-"
        pr_top = f"{pr[0][0][:18]}/{pr[0][1]:.3f}/{pr[0][2][:4]}" if pr else "-"
        mark = "✓" if ok else "✗ MISMATCH"
        print(f"{p[:46]:46s} {sk_top:28s} {pr_top:28s} {mark}")
        if not ok:
            print(f"    sklearn full: {sk}")
            print(f"    pure full:    {pr}")

    print()
    print(f"PARITY: {len(PROBES) - fails}/{len(PROBES)} prompts identical "
          + ("✓ ALL MATCH" if fails == 0 else f"✗ {fails} MISMATCH"))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
