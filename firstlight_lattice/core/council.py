#!/usr/bin/env python3
"""
council.py — N-dim council, stolen from stack_atlas/analyze/animals.py and
generalized to support fewer than 6 dimensions (our move-axes come out as 4).

WHAT IS STOLEN (substrate-blind, sanctioned by animals.py's own docstring:
"the partition is identical across substrates; substrate knowledge lives in
WHICH dims you choose, not how readers are organized"):
  - crossterms: pairwise products of a dim-vector, tritone-decayed by distance,
    penalized on sign-disagreement. (compute_crossterms)
  - animal_opinion: alignment * magnitude across a reader's owned crossterms.
  - council conviction: COUNT of readers agreeing (opinion>0, confidence>0.3).
    This is the real "quorum" — count-of-agreeing-readers-past-threshold —
    NOT the bacterial diffusion field.

WHAT IS GENERALIZED (the flagged generalization): the 6-dim hexagon with 5
animals and 15 crossterms partitioned 3-3-3-3-3 (raccoon on the 3 diametrics)
is SACRED and SPECIFIC TO 6. It does not exist for 4 or 5 dims. So:
  - N == 6  -> use the exact sacred SPIRIT_ANIMALS partition, unchanged.
  - N != 6  -> derive a principled reader-partition: one reader per dim
    (anchors the pairs touching that dim) plus, when the dim count is even, a
    "diametric reader" for the through-center pairs. Conviction is still
    count-agreeing; feral_priest still = full unanimity. No fake hexagon.

We do NOT force 6. A 4-dim move-manifold gets a 4-dim council. Forcing 6 onto
4 real axes would mint two noise dims — the elegant-over-true failure.
"""
from __future__ import annotations
import math

TRITONE = 2 ** 0.5

# The SACRED 6-dim partition (verbatim from stack_atlas/animals.py). Used ONLY
# when the manifold has exactly 6 dims. Not to be reshaped for other N.
SPIRIT_ANIMALS_6 = {
    'wolf_pup':                 [(0, 1), (0, 4), (0, 5)],
    'tayra':                    [(1, 2), (1, 3), (1, 5)],
    'elk':                      [(0, 2), (2, 3), (2, 4)],
    'technicolor_highland_cow': [(3, 4), (3, 5), (4, 5)],
    'clever_raccoon':           [(0, 3), (1, 4), (2, 5)],
}

# tritone divisors by dim-distance (from animals.py: 1000 * 2^(d/2), the
# tritone-stepped geometric series). Extended to arbitrary distance.
def _divisor(dist):
    return 1000.0 * (2 ** (dist / 2.0))


def compute_crossterms(dims):
    """Pairwise crossterms for an N-dim vector in [-1,+1]. Verbatim logic from
    animals.compute_crossterms, but range(N) instead of range(6)."""
    n = len(dims)
    ct = {}
    for i in range(n):
        for j in range(i + 1, n):
            dist = j - i
            divisor = _divisor(dist)
            a, b = dims[i], dims[j]
            if abs(a) < 0.01 or abs(b) < 0.01:
                ct[(i, j)] = 0.0
            elif (a > 0) == (b > 0):
                sign = 1.0 if a > 0 else -1.0
                ct[(i, j)] = sign * abs(a) * abs(b) * 1000.0 / divisor
            else:
                ct[(i, j)] = -abs(a) * abs(b) * 1000.0 / divisor / TRITONE
    return ct


def _partition_for_n(n):
    """Return {reader_name: [pairs]} for N dims.
    N==6 -> sacred hexagon. Else -> derived: one reader per dim anchoring the
    pairs that touch it (each pair assigned to its LOWER dim's reader so every
    crossterm is owned exactly once), plus a diametric reader when n is even."""
    if n == 6:
        return dict(SPIRIT_ANIMALS_6)
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    part = {f'reader_{i}': [] for i in range(n)}
    diametrics = []
    half = n // 2
    for (i, j) in pairs:
        # a "diametric" pair crosses the center: j - i == n/2 (even n only)
        if n % 2 == 0 and (j - i) == half:
            diametrics.append((i, j))
        else:
            part[f'reader_{i}'].append((i, j))
    # drop empty readers (high-index dims may anchor nothing after diametric pull)
    part = {k: v for k, v in part.items() if v}
    if diametrics:
        part['diametric_reader'] = diametrics
    return part


def animal_opinion(pairs, crossterms):
    """alignment * magnitude across a reader's pairs. Verbatim from animals.py."""
    res = [crossterms[p] for p in pairs]
    nz = [r for r in res if abs(r) > 0.01]
    if not nz:
        return {'opinion': 0.0, 'confidence': 0.0}
    signs = [1.0 if r > 0 else -1.0 for r in nz]
    alignment = sum(signs) / len(signs)
    magnitude = sum(abs(r) for r in res)
    return {'opinion': alignment * magnitude, 'confidence': abs(alignment)}


def council_read(dims_vector):
    """Run the council on an N-dim vector. Conviction = count of readers agreeing
    at confidence>0.3 (the real quorum). feral_priest = full unanimity. Verbatim
    logic from animals.council_read, but partition adapts to N."""
    n = len(dims_vector)
    partition = _partition_for_n(n)
    crossterms = compute_crossterms(dims_vector)
    readings = {}
    for reader, pairs in partition.items():
        op = animal_opinion(pairs, crossterms)
        readings[reader] = {
            'opinion': round(op['opinion'], 3),
            'confidence': round(op['confidence'], 3),
            # a reader is CONVICTED when its crossterms cohere (align in one
            # direction, + OR -) with real magnitude. strong-negative is signal,
            # not absence — a room that coherently does-NOT is as distinctive as one
            # that coherently does. (diverges from stack_atlas's positive-only test,
            # which assumed absolute-good dims; ours are relative.)
            'agreeing': abs(op['opinion']) > 0.05 and op['confidence'] > 0.3,
        }
    agreeing = sum(1 for r in readings.values() if r['agreeing'])
    n_readers = len(partition)
    return {
        'n_dims': n, 'n_readers': n_readers,
        'crossterms': crossterms, 'readings': readings,
        'conviction': agreeing,
        'conviction_fraction': round(agreeing / n_readers, 3) if n_readers else 0.0,
        'feral_priest': (agreeing == n_readers and n_readers > 0),
        'sacred_hexagon': (n == 6),
    }


def selftest():
    ok = True
    # 6-dim: must reproduce the sacred 5-animal partition exactly
    r6 = council_read([0.5, 0.4, 0.3, -0.2, 0.6, 0.5])
    ok = ok and r6['n_readers'] == 5 and set(_partition_for_n(6)) == set(SPIRIT_ANIMALS_6)
    print(f"  6-dim: {r6['n_readers']} readers (sacred hexagon: {r6['sacred_hexagon']}), conviction {r6['conviction']}/5")
    # 4-dim (our move case): must NOT force 5 animals; derives its own partition
    r4 = council_read([0.6, 0.5, -0.3, 0.4])
    n_ct_4 = len(compute_crossterms([0.6, 0.5, -0.3, 0.4]))
    ok = ok and n_ct_4 == 6 and not r4['sacred_hexagon'] and r4['n_readers'] >= 2
    print(f"  4-dim: {r4['n_readers']} readers, {n_ct_4} crossterms, conviction {r4['conviction']}/{r4['n_readers']} (forced hexagon: {r4['sacred_hexagon']})")
    # every crossterm owned exactly once in the derived partition
    for n in (3, 4, 5, 7):
        part = _partition_for_n(n)
        owned = [p for ps in part.values() for p in ps]
        all_pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
        assert sorted(owned) == sorted(all_pairs), f'n={n}: partition must cover every crossterm once'
        assert len(owned) == len(set(owned)), f'n={n}: no crossterm owned twice'
    print(f"  partition coverage (n=3,4,5,7): every crossterm owned exactly once  OK")
    print('SELFTEST:', 'PASS' if ok else 'FAIL')
    return ok


if __name__ == '__main__':
    import sys
    sys.exit(0 if selftest() else 1)
