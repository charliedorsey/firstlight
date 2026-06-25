#!/usr/bin/env python3
"""
move_dimensions.py — mint NAMED ORTHOGONAL dimensions from a library's move-grammar.

This is the dimension-discovery step that FAILED on word-residual (24x5898 sparse
noise, 35% smeared variance) and now SUCCEEDS on move-profiles (24x10 dense,
discriminating). The moves ARE the dim seeds; SVD over the move-profile matrix
yields orthogonal axes, each named by its top-loading moves. Capped at 6
(crossterm/partition discipline), floored by explained variance (use fewer if
the library doesn't support 6 — honest dimensionality).
"""
from __future__ import annotations
import numpy as np
from sklearn.decomposition import TruncatedSVD
import move_grammar as MG

MAX_DIMS = 6
TARGET_CUM = 0.85
MARGINAL_FLOOR = 0.05

def discover_move_dims(records, max_dims=MAX_DIMS):
    names = [n for n, _ in records]
    profs = [MG.move_profile(t) for _, t in records]
    M = np.array([[p[m] for m in MG.MOVE_NAMES] for p in profs])  # (n_prompts, 10 moves)
    _mean = M.mean(axis=0)                                        # keep for projecting prompts
    M = M - _mean                                                # center
    ceil = max(1, min(max_dims, M.shape[0]-1, M.shape[1]-1))
    svd = TruncatedSVD(n_components=ceil, random_state=0)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        coords = svd.fit_transform(M)
    ev = np.nan_to_num(svd.explained_variance_ratio_, nan=0.0, posinf=0.0, neginf=0.0)
    # honest dimensionality: cap 6, stop at cumulative target or marginal floor
    keep, cum = 0, 0.0
    for i in range(ceil):
        if i >= max_dims: break
        if i > 0 and ev[i] < MARGINAL_FLOOR: break
        keep += 1; cum += ev[i]
        if cum >= TARGET_CUM: break
    keep = max(1, keep)
    axes = []
    for i in range(keep):
        comp = svd.components_[i]
        order = np.argsort(np.abs(comp))[::-1][:3]
        # name by signed top moves: +CONTEXT -FORMAT reads "context-heavy vs format-fixed"
        label = ' / '.join(f"{'+' if comp[j]>=0 else '-'}{MG.MOVE_NAMES[j]}" for j in order)
        axes.append({'index': i, 'name': label,
                     'explained_variance': round(float(ev[i]),4),
                     'top_moves': [MG.MOVE_NAMES[j] for j in order]})
    if keep == max_dims:
        verdict = f"library supports full cap ({keep})"
    elif keep < len(ev):
        verdict = (f"library supports {keep} real move-dimensions (next adds "
                   f"{ev[keep]*100:.1f}% < floor) — using {keep}, not forcing {max_dims}")
    else:
        verdict = (f"library supports {keep} available move-dimension(s); corpus is too small/flat "
                   f"to expose more — using {keep}, not forcing {max_dims}")
    return {'n_axes_kept': keep, 'cap': max_dims,
            'explained_variance_curve': [round(float(x),4) for x in ev],
            'cumulative_at_kept': round(float(sum(ev[:keep])),4),
            'verdict': verdict, 'axes': axes,
            '_fitted': {'svd': svd, 'mean': _mean, 'keep': keep},
            'coords': {names[r]: [round(float(coords[r][i]),4) for i in range(keep)] for r in range(len(names))}}

if __name__ == '__main__':
    import sys, glob, os, json
    def load(folder):
        return [(os.path.splitext(os.path.basename(p))[0], open(p,encoding='utf-8',errors='replace').read())
                for p in sorted(glob.glob(os.path.join(folder,'**','*'),recursive=True))
                if os.path.isfile(p) and p.lower().endswith(('.md','.txt','.yml','.yaml','.json'))]
    r = discover_move_dims(load(sys.argv[1]))
    print(f"axes kept: {r['n_axes_kept']}/{r['cap']}   cumulative variance: {r['cumulative_at_kept']}")
    print(f"verdict: {r['verdict']}")
    print(f"EV curve: {r['explained_variance_curve']}")
    for a in r['axes']:
        print(f"  dim {a['index']}: [{a['name']}]  ev={a['explained_variance']}")
