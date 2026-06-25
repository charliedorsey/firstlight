#!/usr/bin/env python3
"""
router.py — route a prompt to its room by placing BOTH in one shared ELM-keyed
frame. This is the fix for the routing failure: rooms are well-separated in
coordinate space (proven, mean pairwise dist ~0.99), but prompts were landing on
the same rooms every time because raw-magnitude prompt vectors (short, weak
signal) aren't commensurable with raw-magnitude room vectors (long, strong).

THE FIX (the missing compose step for prompts): a prompt is keyed against the
SAME family norms the rooms were composed against, so "this prompt is about
debugging" lands near "this room is about debugging" regardless of length. Then
route by COSINE on the normalized move-axis (direction, not magnitude).

Pipeline parity — prompt and room both go: sense (move-sensor) -> transfigure
(signal/noise) -> compose (ELM-key against family norms) -> coordinate.

The high-charge preference is a SEPARATE downstream knob (charge_bias), applied
AFTER nearest-neighbor, never mixed into the locating distance — per the
operator: routing and charge-preference are different questions.
"""
from __future__ import annotations
import math
import numpy as np
import move_grammar as MG
import compose as CO
import soul as S

MOVES = MG.MOVE_NAMES


class Router:
    def __init__(self, records):
        """records: [(name, text)] — the room library. Compose it once; cache the
        family norms so prompts can be keyed into the SAME frame."""
        self.names = [n for n, _ in records]
        self.composed = CO.compose(records)
        # the family norms (median move-strength) used to ELM-key everything —
        # this is the shared frame both rooms and prompts get keyed against
        self.family_mean = self.composed['family_mean']
        self.resonant = self.composed['resonant_moves']
        # room coordinates: normalized move-profile (direction), in MOVE order
        self.room_vecs = {nm: self._normalized_move_vec(text) for nm, text in records}
        self.M = np.array([self.room_vecs[nm] for nm in self.names])
        # charge (soul) per room, for the optional downstream preference knob
        self.charge = {nm: d['soul'] for nm, d in S.soul_axis(records).items()}

    def _normalized_move_vec(self, text):
        """A prompt/room's location: its move-profile, L2-normalized so it encodes
        DIRECTION (what moves, in what proportion) not magnitude (how long)."""
        v = np.array([MG.move_profile(text)[m] for m in MOVES])
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def route(self, prompt, k=3, charge_bias=0.0):
        """Route a prompt to its nearest rooms in the shared frame.

        charge_bias in [0,1]: 0 = pure content match (location only); >0 nudges
        toward higher-charge rooms AFTER locating — a separate preference, not
        part of the distance. Returns ranked (name, similarity, charge)."""
        pv = self._normalized_move_vec(prompt)
        # cosine similarity (both unit-normalized -> dot product)
        sims = self.M @ pv
        scored = []
        for i, nm in enumerate(self.names):
            base = float(sims[i])
            # charge preference applied as a separate additive nudge, logged distinctly
            adj = base + charge_bias * max(0.0, self.charge.get(nm, 0.0))
            scored.append((nm, round(base, 3), round(self.charge.get(nm, 0.0), 3), round(adj, 3)))
        scored.sort(key=lambda x: -x[3])
        return scored[:k]


def _load(folder):
    # canonical room filter: .yml/.yaml specs only, ROOM_CONTRACT excluded (matches
    # semantic_lattice.load_rooms_canonical, so router reads the same 23-room corpus)
    import glob, os
    return [(os.path.splitext(os.path.basename(p))[0], open(p, encoding='utf-8', errors='replace').read())
            for p in sorted(glob.glob(os.path.join(folder, '*')))
            if p.lower().endswith(('.yml', '.yaml')) and os.path.basename(p) != 'ROOM_CONTRACT.md']


def selftest(folder=None):
    if folder is None:
        folder = os.path.join(os.path.dirname(__file__), '..', 'rooms')
    R = Router(_load(folder))
    tests = [
        ('help me debug this KeyError in my python script', ['debug', 'engineering', 'scrum']),
        ('review my manuscript and give me hard criticism', ['review', 'criticism', 'manuscript', 'book']),
        ('how should I position and launch this product to market', ['gtm', 'opportunity', 'launch', 'sales']),
        ('I need to ask better questions before I decide', ['question']),
        ('help me sit with a hard feeling', ['reflection', 'voice', 'human', 'emotional']),
    ]
    ok = 0
    print(f"routing {len(tests)} held-out prompts (corpus {len(R.names)} rooms):")
    for prompt, expect_keys in tests:
        top = R.route(prompt, k=3)
        hit = any(any(k in nm.lower() for k in expect_keys) for nm, *_ in top)
        ok += hit
        print(f"  [{'OK' if hit else 'XX'}] '{prompt[:36]:36s}' -> {top[0][0]} (sim {top[0][1]})")
        if not hit:
            print(f"       expected~{expect_keys}, got: {[nm for nm,*_ in top]}")
    print(f"ROUTING: {ok}/{len(tests)} found an expected room in top-3")
    return ok


if __name__ == '__main__':
    import os, sys
    if '--selftest' in sys.argv:
        selftest()
    else:
        R = Router(_load(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'rooms')))
        prompt = sys.argv[2] if len(sys.argv) > 2 else 'help me debug a KeyError'
        for nm, base, charge, adj in R.route(prompt, k=5):
            print(f"  sim {base:+.2f}  charge {charge:+.2f}  {nm}")
