#!/usr/bin/env python3
"""
dim_pool.py — combine ALL candidate dims into one pool, select the top mix.

Resolves the architecture fork (operator: "combine — all are candidate dims; does
structural re-rank semantic, or do they combine into the dim pool? → combine"):

  SEMANTIC arm  (semantic_lattice.discover_axes)  → named semantic candidate dims
  STRUCTURAL arm (semantic_lattice.StructuralFace) → shape candidate dims
        └──────────────────────────┬──────────────────────────┘
                                    ▼
                        ONE CANDIDATE DIM POOL  (semantic + structural together)
                                    ▼
        SELECT ≤6 dims maximizing  coordinate_variance_share × (1 − mean|corr|)
        (orthogonality × combined variance explained), BIASED toward positive
        values — the council partition is sacred at 6, so the pool selects down to 6.
                                    ▼
                        the dim set the council reads (compose → council crossterms)

The selector logic is the charge engine's facet_select (variance × orthogonality,
cap-6) — reused here over the firstlight candidate pool, not reinvented. The
positive-value bias is added per the operator: among comparable mixes, prefer the
set whose room coordinates skew positive (a dim that mostly reads "present /
above-norm" carries more signal than one that mostly reads absence).
"""
from __future__ import annotations
import os, sys, glob
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import semantic_lattice as SL

MAX_DIMS = 6            # council partition is sacred at 6 — never exceed
# (positive-bias lives in dim_select, the single selector)


def load_records(rooms_folder=None):
    """Delegates to the canonical loader (one corpus for both arms)."""
    if rooms_folder is None:
        rooms_folder = os.path.join(os.path.dirname(__file__), '..', 'rooms')
    return SL.load_rooms_canonical(rooms_folder)


def build_pool(records, rooms_folder=None):
    """Assemble the candidate dim pool from all three arms, ORIENTED + RE-KEYED + NAMED
    via dim_nomenclature (F3/F12): every axis is sign-oriented (positive = more-
    descriptive) and normalized to council-native [-1,+1] BEFORE selection, so no arm
    dominates by raw scale and the positive-skew bias is meaningful. Each dim has a
    stable unique ID (Finding 4). Returns ids, M (normalized), room_order, meta."""
    import dim_nomenclature as DN
    nd = DN.build_named_dims(rooms_folder)
    cards = nd['cards']; room_order = nd['room_order']; M = nd['M']
    ids, arm_of, display = [], {}, {}
    counts = {'semantic': 0, 'structural': 0, 'move': 0}
    for c in cards:
        did = f"{c['id']}::{c['name']}"          # stable unique ID + descriptive name
        ids.append(did); arm_of[did] = c['arm']; display[did] = c['name']
        counts[c['arm']] = counts.get(c['arm'], 0) + 1
    return ids, M, room_order, {'arm_of': arm_of, 'display': display,
                                'cards': cards,
                                'n_semantic': counts['semantic'],
                                'n_structural': counts['structural'],
                                'n_move': counts['move']}


# Selection lives in ONE place: dim_select.select (combined-variance objective +
# orthogonality + positive bias, with strategy comparison). build_and_select() below
# calls it. The old standalone select_top_mix heuristic that used to live here was
# removed in the selector consolidation — its objective is subsumed by dim_select's
# ortho_heuristic strategy, so nothing was lost.


def build_and_select(rooms_folder=None, k=MAX_DIMS, strategy='max_combined'):
    """Full pipeline stage: build the ELM-keyed pool → select the ≤6 axis set that
    maximizes COMBINED variance explained (operator's objective), via dim_select.
    All strategies are computed and returned for evidence; `strategy` picks the live one.
    Carries column INDICES end to end (IDs are display only)."""
    import dim_select as DS
    ids, M, room_order, meta = build_pool(load_records(rooms_folder), rooms_folder)
    cards = meta['cards']
    comparison = DS.select(M, cards, k=k)
    selected_idx, sel_meta = comparison[strategy]
    selected_ids = [ids[j] for j in selected_idx]
    coords = {r: [round(float(M[ri, j]), 4) for j in selected_idx]
              for ri, r in enumerate(room_order)}
    return {'pool_ids': ids, 'pool_size': len(ids),
            'arm_counts': {'semantic': meta['n_semantic'], 'structural': meta['n_structural'], 'move': meta.get('n_move', 0)},
            'selected_idx': selected_idx, 'selected_dims': selected_ids,
            'selection': sel_meta, 'strategy': strategy,
            'strategy_comparison': {s: {'dims': [ids[j] for j in idx], 'meta': m}
                                    for s, (idx, m) in comparison.items()},
            'selected_arms': [meta['arm_of'][i] for i in selected_ids],
            'selected_display': [meta['display'][i] for i in selected_ids],
            'coords': coords, 'room_order': room_order}


def selftest():
    out = build_and_select()
    print(f"candidate pool: {out['pool_size']} dims "
          f"({out['arm_counts']['semantic']} semantic + {out['arm_counts']['structural']} structural"
          f" + {out['arm_counts'].get('move', 0)} move)")
    print(f"selected {len(out['selected_dims'])} of {out['pool_size']} (strategy: {out['strategy']}):")
    for nm, arm in zip(out['selected_dims'], out['selected_arms']):
        print(f"  [{arm:10s}] {nm}")
    s = out['selection']
    print(f"  strategy={out['strategy']}  combined_variance_explained={s.get('combined_variance_explained')}")
    # sanity: the mix should draw from MULTIPLE arms (the fork resolved as combine;
    # F5 added the move arm as a third candidate source — selector decides the mix)
    arms = set(out['selected_arms'])
    print(f"  arms in selected mix: {sorted(arms)} ({len(arms)} of 3 candidate arms)")
    # Finding 4: every pool ID must be unique (no duplicate-name index collision)
    assert len(out['pool_ids']) == len(set(out['pool_ids'])), "duplicate pool IDs!"
    print(f"  unique pool IDs: YES ({len(out['pool_ids'])} ids)")
    print("SELFTEST: PASS")
    return out


if __name__ == '__main__':
    selftest()
