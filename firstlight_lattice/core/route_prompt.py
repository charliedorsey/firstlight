#!/usr/bin/env python3
"""
route_prompt.py — firstlight_lattice routing entry point.

Routes an incoming prompt to the room that fits it, using the SETTLED router
architecture from the build log (README v0.9.4-v0.9.5):

  ROUTER (primary match) = SEMANTIC surface-area. The best honest router is the
  hybrid: coherence-words first (precise when the prompt's coherent words
  intersect a room's), TF-IDF fallback for coverage on sparse/short prompts.
  Scoreboard from the build log: move-grammar 0/5 -> posture 1/5 ->
  matched-deliverable 0/6 -> plain TF-IDF 4/7 -> coherence-only 2/8 -> HYBRID 5/8.

  (The move-grammar / posture / deliverable cluster is the ROOM ATLAS — it
  describes/separates/prefers rooms and can RE-RANK candidates, but the build log
  established by repeated elimination that it cannot be the primary matcher.
  Structural routing reads how a prompt is shaped; routing needs what it's about.)

Defaults to the bundle's own rooms list (../rooms) when no library is given.

Run:
    python3 core/route_prompt.py "help me debug this KeyError"
    python3 core/route_prompt.py "..." --rooms /path/to/your/prompts
    python3 core/route_prompt.py --selftest

It suggests; you decide. Nothing here gates or auto-runs. An embedding backend
(README's swappable slot) would lift the remaining lexical-ceiling misses; it is
deliberately not bundled.
"""
from __future__ import annotations
import os, sys, glob, argparse

sys.path.insert(0, os.path.dirname(__file__))
import semantic_lattice as HR


def load_rooms(folder=None):
    """Default to the bundle's own rooms list when no folder is supplied."""
    if folder is None:
        folder = os.path.join(os.path.dirname(__file__), '..', 'rooms')
    return {os.path.splitext(os.path.basename(p))[0]: open(p, encoding='utf-8', errors='replace').read()
            for p in glob.glob(os.path.join(folder, '*'))
            if p.lower().endswith(('.yml', '.yaml'))
            and os.path.basename(p) != 'ROOM_CONTRACT.md'}


def main():
    ap = argparse.ArgumentParser(description="firstlight_lattice — route a prompt to its room")
    ap.add_argument("prompt", nargs="?", help="the prompt to route")
    ap.add_argument("--rooms", default=None, help="folder of room/prompt files (default: bundled ../rooms)")
    ap.add_argument("-k", type=int, default=3, help="how many rooms to return")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        HR.selftest()
        return

    rooms = load_rooms(args.rooms)
    src = args.rooms or "bundled rooms"
    print(f"[firstlight_lattice router]  {len(rooms)} rooms from {src}  (hybrid: coherence + tf-idf fallback)")

    if not args.prompt:
        ap.print_help()
        return

    R = HR.HybridRouter(rooms)
    top = R.route(args.prompt, k=args.k)
    print(f"\nprompt: {args.prompt}")
    print("routes to:")
    for name, score, via in top:
        print(f"  {score:>6.3f}  {name}   [{via}]")
    print("\n(advisory — the lattice's suggestion, not a verdict. It suggests; you decide.)")


if __name__ == "__main__":
    main()
