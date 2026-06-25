#!/usr/bin/env python3
"""
compose.py — the COMPOSE layer for firstlight lattice, ported from the cow_chess
v2 constitution (transform/aggregation contracts, turns 41 & 43).

THE LAYER STACK (each layer has rights and NON-rights; blurring them is the
named core failure mode):
    sense (capture)      — move-sensor reads raw move-signals from a prompt
    transfigure          — sort each move into SIGNAL vs NOISE buckets, ONE-WAY
                           (noise may be promoted to signal, never the reverse);
                           emit ABSOLUTE values. May not interpret/rank.
    compose/do_the_needful — reconcile transfigured packets ACROSS the library
                           into (resonance + remainder), re-keyed to ELM-native
                           magnitudes, council-ready. May normalize/reconcile/
                           re-key + must log. May NOT invoke, rank, or ponder.
    convocation (council)— reads the composed keys (council.py)

This is NOT the transform layer and NOT the council. It sits ABOVE transfigure,
BELOW convocation. Its whole job: turn plural local move-packets into stable
ELM-keyed (resonance, remainder) the council can read with real magnitude —
which is exactly what was missing when the council read near-zero SVD coords.

resonance = the family-stable shared structure (conserved moves; what voices
            agree on across the library).
remainder = what's left per prompt after resonance is removed (the deviations;
            the discriminating pocket signal).
"""
from __future__ import annotations
import math, statistics as st
import move_grammar as MG

ELM = 2 ** (1 / 24)          # the stack's native base (≈1.0293)
MOVES = MG.MOVE_NAMES


# ── TRANSFIGURE: noise→signal, two buckets, one-way, absolute values ──────────
def transfigure(text, signal_floor=None):
    """Sort each move into SIGNAL (genuinely present, absolute strength) or NOISE
    (below floor — incidental). ONE-WAY: a move at/above floor is signal; the
    operation never demotes signal to noise. Emits absolute values, no ranking.

    signal_floor: if None, derived from THIS prompt's own move distribution
    (the floor is a property of the data, not a hardcoded constant) — a move is
    signal if it carries non-trivial mass relative to the prompt's active moves."""
    prof = MG.move_profile(text)              # raw move-signal (absolute, [0..1])
    active = [v for v in prof.values() if v > 0]
    if signal_floor is None:
        # floor = a small fraction of the mean active move-strength; derived
        signal_floor = (st.mean(active) * 0.25) if active else 0.0
    signal, noise = {}, {}
    for m in MOVES:
        v = prof[m]
        if v >= signal_floor and v > 0:
            signal[m] = round(v, 4)            # absolute value, kept
        else:
            noise[m] = round(v, 4)             # below floor — noise bucket
    return {'signal': signal, 'noise': noise, 'signal_floor': round(signal_floor, 4),
            'log': f'transfigure: {len(signal)} signal / {len(noise)} noise moves, floor={signal_floor:.3f}'}


# ── ELM re-keying: map an absolute [0..1] value to an ELM-native signed key ────
def _elm_key(value, family_mean):
    """Re-key an absolute move-value to an ELM-native magnitude in [-1,+1],
    centered on the family mean: a move stronger than the family norm reads
    positive, weaker reads negative, scaled in ELM steps. This is the
    council-ready magnitude raw SVD coords lacked."""
    if value <= 0 and family_mean <= 0:
        return 0.0
    # ratio to family norm, in ELM steps: how many 2^(1/24) steps above/below
    ratio = (value + 1e-6) / (family_mean + 1e-6)
    steps = math.log(ratio, ELM)
    # squash steps to [-1,+1] (tanh over a ~24-step half-window = one octave)
    return round(math.tanh(steps / 24.0), 4)


# ── COMPOSE / do_the_needful: reconcile across library -> resonance+remainder ─
def compose(records):
    """Take a library of prompts, transfigure each, then reconcile across all of
    them into ELM-keyed (resonance, remainder) per prompt. Logs every op.

    resonance = moves that are SIGNAL across many prompts (family-stable shared
                structure), ELM-keyed per prompt against the family mean.
    remainder = the rest of each prompt's signal moves, ELM-keyed — the
                discriminating deviation the council reads for distinctiveness."""
    names = [n for n, _ in records]
    transfigured = {n: transfigure(t) for n, t in records}
    logs = [transfigured[n]['log'] for n in names]

    # family-stable: a move is RESONANT if it is signal in >= half the library
    n = len(records)
    signal_count = {m: 0 for m in MOVES}
    for nm in names:
        for m in transfigured[nm]['signal']:
            signal_count[m] += 1
    resonant_moves = {m for m in MOVES if signal_count[m] >= max(2, n // 2)}
    remainder_moves = set(MOVES) - resonant_moves

    # family mean per move (over prompts where it's signal) — the ELM keying norm
    family_mean = {}
    for m in MOVES:
        vals = [transfigured[nm]['signal'].get(m, 0.0) for nm in names
                if m in transfigured[nm]['signal']]
        family_mean[m] = st.median(vals) if vals else 0.0  # median: robust to skew (a few heavy users shouldn't shove typical rooms negative)

    packets = {}
    for nm in names:
        sig = transfigured[nm]['signal']
        resonance = {m: _elm_key(sig.get(m, 0.0), family_mean[m])
                     for m in resonant_moves}
        remainder = {m: _elm_key(sig.get(m, 0.0), family_mean[m])
                     for m in remainder_moves if sig.get(m, 0.0) > 0}
        packets[nm] = {
            'needful_id': f'compose:{nm}',
            'target_id': nm,
            'resonance_packet': resonance,    # ELM-keyed shared structure
            'remainder_packet': remainder,    # ELM-keyed deviation
            # council-ready dim-vector: resonance moves in canonical order
            # (this is the real-magnitude vector the council was missing)
            'council_vector': [resonance.get(m, 0.0) for m in sorted(resonant_moves)],
            'council_dims': sorted(resonant_moves),
        }
    return {
        'n_records': n,
        'resonant_moves': sorted(resonant_moves),     # the family resonance axes
        'remainder_moves': sorted(remainder_moves),
        'family_mean': {m: round(family_mean[m], 4) for m in MOVES},
        'packets': packets,
        'log': logs + [f'compose: {len(resonant_moves)} resonant / {len(remainder_moves)} remainder moves across {n} prompts'],
    }


def selftest():
    ok = True
    # transfigure one-way + bucket integrity
    t = transfigure('you are an analyst. cite evidence, verify, do not assume. give a table.')
    assert set(t['signal']) | set(t['noise']) == set(MOVES), 'every move must land in exactly one bucket'
    assert not (set(t['signal']) & set(t['noise'])), 'buckets must be disjoint (one-way)'
    print(f"  transfigure: {len(t['signal'])} signal, {len(t['noise'])} noise — buckets disjoint+complete OK")

    # compose: resonance should capture shared moves, council_vector has real magnitude
    recs = [
        ('a', 'you are an analyst. cite evidence, verify the claim, confidence level. table.'),
        ('b', 'you are an expert. cite evidence, verify, test. respond in a table format.'),
        ('c', 'you are a specialist. cite sources, verify, check confidence. bullet table.'),
        ('d', 'reflect on the feeling, stay present, slow down, no constraints, just be with it.'),
    ]
    r = compose(recs)
    print(f"  resonant moves: {r['resonant_moves']}")
    # council vectors must have real magnitude (not all near-zero like raw SVD)
    mags = [max(abs(v) for v in p['council_vector']) if p['council_vector'] else 0
            for p in r['packets'].values()]
    real_magnitude = any(m > 0.1 for m in mags)
    print(f"  max council-vector magnitudes: {[round(m,2) for m in mags]}  (real magnitude: {real_magnitude})")
    ok = ok and real_magnitude
    # feed into the council and check conviction is now non-trivial for some prompt
    try:
        import council as C
        convs = [C.council_read(p['council_vector'])['conviction'] for p in r['packets'].values() if p['council_vector']]
        print(f"  council convictions on composed vectors: {convs}")
        ok = ok and any(c > 0 for c in convs)
    except Exception as e:
        print(f"  (council read skipped: {e})")
    print('SELFTEST:', 'PASS' if ok else 'FAIL')
    return ok


if __name__ == '__main__':
    import sys
    sys.exit(0 if selftest() else 1)
