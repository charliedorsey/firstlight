#!/usr/bin/env python3
"""
breadth.py — the SECOND scoring axis: how many moves a room exercises with real
magnitude. Complements council conviction (directional coherence).

WHY (the design calibration): conviction rewards single-mindedness — cooking_helper
(one move, sharp) scores 5/5 while a sophisticated room (spirit_animal_council,
eng, human_voice) scores mid because doing MANY moves pulls crossterms in several
directions = lower directional coherence. But those broad rooms are top-tier. So
breadth is a separate axis: a room is a POINT in (coherence, breadth), not a rank.

MECHANISM (stolen from corpus_charge.py): rank-projection across the corpus.
Each room's raw breadth = count of moves at real magnitude (effective number of
moves, via participation entropy so it's not just a hard threshold count). Then
rank-project that across the corpus to [-1,+1] — robust to skew (no mean/median
fragility), comparable across corpora by construction.
"""
from __future__ import annotations
import math, os
import move_grammar as MG

MOVES = MG.MOVE_NAMES


def raw_breadth(text):
    """Effective number of moves a prompt exercises. Uses participation ratio
    (inverse Simpson) on the move-profile so a room doing 5 moves evenly scores
    higher than one nominally touching 5 but dominated by 1. Continuous, not a
    hard count — avoids threshold brittleness."""
    prof = MG.move_profile(text)
    vals = [prof[m] for m in MOVES if prof[m] > 0]
    if not vals:
        return 0.0
    s = sum(vals)
    p = [v / s for v in vals]
    # inverse Simpson = effective count of moves actually in play
    return 1.0 / sum(pi * pi for pi in p)


def rank_project(values):
    """corpus_charge.py's move: rank each value within the corpus, map to [-1,+1].
    Ties share averaged rank. Robust to skew; comparable across corpora."""
    n = len(values)
    if n <= 1:
        return [0.0] * n
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    # map rank [0..n-1] to [-1,+1]
    return [2.0 * r / (n - 1) - 1.0 for r in ranks]


def breadth_axis(records):
    """Returns {name: breadth_score in [-1,+1]} rank-projected across the corpus."""
    names = [n for n, _ in records]
    raw = [raw_breadth(t) for _, t in records]
    proj = rank_project(raw)
    return {names[i]: {'breadth': round(proj[i], 3), 'raw_effective_moves': round(raw[i], 2)}
            for i in range(len(names))}


if __name__ == '__main__':
    import sys, glob, os
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'rooms')
    recs = [(os.path.splitext(os.path.basename(p))[0], open(p, encoding='utf-8', errors='replace').read())
            for p in sorted(glob.glob(os.path.join(folder, '**', '*'), recursive=True))
            if os.path.isfile(p) and p.lower().endswith(('.md', '.txt', '.yml', '.yaml', '.json'))]
    b = breadth_axis(recs)
    ranked = sorted(b.items(), key=lambda x: -x[1]['breadth'])
    print(f"BREADTH ranking ({len(recs)} rooms), top 15 + bottom 5:")
    for nm, d in ranked[:15]:
        print(f"  {d['breadth']:+.2f}  ({d['raw_effective_moves']:.1f} eff-moves)  {nm}")
    print("  ...")
    for nm, d in ranked[-5:]:
        print(f"  {d['breadth']:+.2f}  ({d['raw_effective_moves']:.1f} eff-moves)  {nm}")
