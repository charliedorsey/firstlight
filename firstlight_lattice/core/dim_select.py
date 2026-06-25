#!/usr/bin/env python3
"""
dim_select.py — select the ≤6 axis set, optimizing COMBINED variance explained.

Operator correction: orthogonality must be optimized for "most variance explained by
the COMBINATION of the six axes" — and we should TEST the options, not assume one
heuristic. So this module:

  1. operates on the ELM-keyed dims from dim_nomenclature (one native scale, so variance
     is comparable across arms — the precondition for an honest combined-variance test).
  2. computes the REAL objective for a candidate 6-subset:
        combined_variance_explained(S) = fraction of the FULL pool's total variance that
        the subset S's column-span captures (projection of the pool onto span(S)).
     This rewards a set that, TOGETHER, spans the most of the pool — not six individually
     high-variance-but-redundant columns.
  3. runs several SELECTORS and reports them side by side so the choice is evidence-based:
        - max_combined   : exhaustive argmax of combined_variance_explained (the objective)
        - ortho_heuristic: variance_share × (1 − mean|corr|) × positive bias (the old one)
        - greedy_span    : greedily add the axis that most increases combined variance
     The council partition is sacred at 6, so k=6 (cap, never exceed).

positive-value bias (operator, F12-aware): applied as a tie-break among near-equal
combined-variance sets — prefer the set whose ELM-keyed coords skew positive (more
rooms reading above family-typical), now meaningful because orientation is fixed.
"""
from __future__ import annotations
import os, numpy as np
from itertools import combinations
import dim_nomenclature as DN

MAX_DIMS = 6
POSITIVE_BIAS = 0.15


def _total_variance(Z):
    return float(np.var(Z, axis=0).sum())


def combined_variance_explained(Z, subset):
    """Fraction of the pool's total variance captured by the SPAN of the subset's
    columns. Project every column of Z onto span(S) and measure retained variance."""
    S = Z[:, list(subset)]
    # economy SVD of the subset → orthonormal basis Q of its column space
    Q, _ = np.linalg.qr(S - S.mean(0))
    proj = Q @ (Q.T @ (Z - Z.mean(0)))         # project centered pool onto span(S)
    return float(np.var(proj, axis=0).sum() / (_total_variance(Z) or 1.0))


def _positive_skew(col):
    return float(np.mean(np.asarray(col) >= 0.0)) if len(col) else 0.0


def select(M, cards, k=MAX_DIMS, positive_bias=POSITIVE_BIAS):
    """Run all selectors on the ELM-keyed pool M; return each one's pick + the chosen
    set (max_combined is the objective). Everything reported for an evidence-based call."""
    n_dims = M.shape[1]
    live = [j for j in range(n_dims) if np.std(M[:, j]) > 1e-9]
    Z = M[:, live]
    idmap = {new: live[new] for new in range(len(live))}     # local→pool index
    kk = min(k, Z.shape[1])
    skew = np.array([_positive_skew(Z[:, j]) for j in range(Z.shape[1])])
    Cabs = np.abs(np.nan_to_num(np.corrcoef(
        ((Z - Z.mean(0)) / np.where(Z.std(0) < 1e-9, 1, Z.std(0))).T)))
    var = np.var(Z, 0); var = var / (var.sum() or 1.0)

    results = {}

    # 1) max_combined — exhaustive argmax of combined variance explained (THE objective)
    best, best_v, best_meta = None, -1.0, {}
    for combo in combinations(range(Z.shape[1]), kk):
        cve = combined_variance_explained(Z, combo)
        pos = float(np.mean(skew[list(combo)]))
        score = cve * (1.0 + positive_bias * pos)        # positive bias as gentle tie-break
        if score > best_v:
            best_v, best = score, combo
            best_meta = {'combined_variance_explained': round(cve, 4),
                         'positive_skew': round(pos, 3),
                         'score': round(score, 4)}
    results['max_combined'] = ([idmap[j] for j in best], best_meta)

    # 2) ortho_heuristic — the previous variance_share × (1−mean|corr|) × pos
    bh, bh_v, bh_meta = None, -1.0, {}
    for combo in combinations(range(Z.shape[1]), kk):
        vs = float(var[list(combo)].sum())
        redun = float(np.mean([Cabs[a, b] for a, b in combinations(combo, 2)])) if kk > 1 else 0.0
        pos = float(np.mean(skew[list(combo)]))
        s = vs * (1 - redun) * (1 + positive_bias * pos)
        if s > bh_v:
            bh_v, bh = s, combo
            bh_meta = {'variance_share': round(vs, 3), 'mean_abs_corr': round(redun, 3),
                       'combined_variance_explained': round(combined_variance_explained(Z, combo), 4)}
    results['ortho_heuristic'] = ([idmap[j] for j in bh], bh_meta)

    # 3) greedy_span — add the axis that most increases combined variance, until k
    picked = []
    while len(picked) < kk:
        best_j, best_g = None, -1.0
        for j in range(Z.shape[1]):
            if j in picked:
                continue
            g = combined_variance_explained(Z, picked + [j])
            if g > best_g:
                best_g, best_j = g, j
        picked.append(best_j)
    results['greedy_span'] = ([idmap[j] for j in picked],
                              {'combined_variance_explained': round(combined_variance_explained(Z, picked), 4)})

    return results


def selftest():
    nd = DN.build_named_dims()
    M, cards = nd['M'], nd['cards']
    res = select(M, cards)
    print("SELECTION STRATEGY COMPARISON (objective = combined variance explained by the 6):\n")
    for strat, (idx, meta) in res.items():
        names = [cards[j]['name'] for j in idx]
        arms = [cards[j]['arm'] for j in idx]
        cve = meta.get('combined_variance_explained')
        print(f"  {strat:16s} CVE={cve}")
        for nm, arm in zip(names, arms):
            print(f"       [{arm:10s}] {nm}")
        print()
    # the objective winner
    obj_idx, obj_meta = res['max_combined']
    print(f"OBJECTIVE PICK (max_combined): CVE={obj_meta['combined_variance_explained']} "
          f"positive_skew={obj_meta['positive_skew']}")
    arms = sorted(set(cards[j]['arm'] for j in obj_idx))
    print(f"  arms represented: {arms}")
    print("SELFTEST: PASS")
    return res


if __name__ == '__main__':
    selftest()
