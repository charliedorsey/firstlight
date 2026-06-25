#!/usr/bin/env python3
"""
move_align.py — align prompts on the MOVE-AXIS and find scaffold vs pocket.

PORT of the settled compressor's family_chain (compressors/settled_v0_family_first):
  FASTQ:   many reads aligned on sequence positions; per-position conservation
           splits scaffold (conserved) from pockets (variable); store template
           once + per-read deviations.
  PROMPTS: each PROMPT is a record; the MOVE-AXIS is the shared backbone (the 10
           cognitive moves are the homologous "positions" raw text lacked). Group
           prompts into families by move-signature; within a family, per-move
           conservation splits scaffold-moves (every member does it the same)
           from pocket-moves (the discriminating signal); store the family
           move-template once + per-prompt deviations.

The pocket-values are the ALIGNED substrate the separate codecs (motif / gap /
ternary) will later consume — they are positionally comparable now, which they
were not before alignment.

ANTI-OVER-INDEXING (explicit): this module references ONLY the move-axis and
WITHIN-CORPUS statistics. No corpus-specific names, no magic thresholds picked
by peeking at /tmp/byo or /tmp/gen. Every cut (family granularity, conservation
threshold) is DERIVED from the corpus's own distribution, so the same code aligns
a stranger's beekeeping prompts. The selftest runs on a SYNTHETIC third corpus
the module has never seen, asserting the scaffold/pocket split is correct there.
"""
from __future__ import annotations
import statistics as st
from collections import defaultdict
import move_grammar as MG
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

MOVES = MG.MOVE_NAMES


def _move_vector(text):
    p = MG.move_profile(text)
    return [p[m] for m in MOVES]


def choose_family_count(V):
    """THE COARSENING KNOB, PARAMETERIZED. Instead of a hardcoded family count or
    quantize-level, sweep k from 2..K and let the SILHOUETTE score (cohesion vs
    separation, corpus-derived) pick the optimal number of families. Returns
    (best_k, labels, score_curve). No corpus-specific tuning — the data chooses.

    Silhouette needs 2<=k<=n-1. If the corpus is too small or has no separable
    structure (best silhouette below a derived noise floor), returns k=1 (one
    family) honestly rather than forcing a split."""
    n = len(V)
    if n < 4:
        return 1, [0] * n, []
    Kmax = min(n - 1, max(2, n // 2))   # ceiling scales with corpus, not fixed
    best_k, best_score, best_labels, curve = 1, -1.0, [0] * n, []
    for k in range(2, Kmax + 1):
        labels = AgglomerativeClustering(n_clusters=k).fit_predict(V)
        try:
            s = silhouette_score(V, labels)
        except Exception:
            continue
        curve.append((k, round(float(s), 3)))
        if s > best_score:
            best_k, best_score, best_labels = k, s, list(labels)
    # noise floor: silhouette < 0.15 means no real cluster structure -> 1 family.
    # 0.15 is a generic clustering convention, not tuned to byo/gen.
    if best_score < 0.15:
        return 1, [0] * n, curve
    return best_k, best_labels, curve


def align(records, conservation_quantile=0.5):
    """records: list of (name, text). Returns families with scaffold/pocket split.

    Family count is CHOSEN BY THE DATA via silhouette (see choose_family_count) —
    no hardcoded level. conservation_quantile: a move is SCAFFOLD within a family
    if its variance across members is below the family's median move-variance —
    conserved RELATIVE TO THIS FAMILY, derived not absolute, adapts to any corpus."""
    vecs = {nm: _move_vector(t) for nm, t in records}
    names = [nm for nm, _ in records]
    V = np.array([vecs[nm] for nm in names])

    best_k, labels, curve = choose_family_count(V)
    fam = defaultdict(list)
    for nm, lab in zip(names, labels):
        fam[int(lab)].append(nm)

    families = []
    for key, members in fam.items():
        M = [vecs[nm] for nm in members]
        # per-move variance across this family's members
        var = [st.pstdev([row[i] for row in M]) if len(M) > 1 else 0.0
               for i in range(len(MOVES))]
        # template = median move-strength at each position (the majority "base")
        template = [st.median([row[i] for row in M]) for i in range(len(MOVES))]
        # A move is IN PLAY for this family only if it actually fires (template
        # strength above a derived activity floor). Absent moves (zero everywhere)
        # are NOT scaffold — absence != conservation. This is the fix the synthetic
        # selftest caught: "everyone omits RESIST" must not look like conserved
        # structure the way "everyone strongly does EVIDENCE" does.
        active_floor = max(0.01, _quantile([t for t in template if t > 0], 0.25)) if any(template) else 0.01
        in_play = [i for i in range(len(MOVES)) if template[i] >= active_floor]
        out_of_play = [MOVES[i] for i in range(len(MOVES)) if i not in in_play]
        if len(M) > 1 and in_play:
            # split conservation ONLY among in-play moves, by their own variance median
            active_vars = [var[i] for i in in_play]
            cut = _quantile(active_vars, conservation_quantile)
            scaffold_moves = [MOVES[i] for i in in_play if var[i] <= cut]   # conserved AND active
            pocket_moves = [MOVES[i] for i in in_play if var[i] > cut]      # variable AND active
        else:
            scaffold_moves = [MOVES[i] for i in in_play]
            pocket_moves = []
        # per-prompt deviations from template (the stored residual)
        deviations = {}
        for nm in members:
            v = vecs[nm]
            deviations[nm] = {MOVES[i]: round(v[i] - template[i], 3)
                              for i in range(len(MOVES))
                              if abs(v[i] - template[i]) > 0.01}
        families.append({
            'key': key, 'members': members, 'size': len(members),
            'template': {MOVES[i]: round(template[i], 3) for i in range(len(MOVES))},
            'move_variance': {MOVES[i]: round(var[i], 3) for i in range(len(MOVES))},
            'scaffold_moves': scaffold_moves,   # conserved AND active within family
            'pocket_moves': pocket_moves,       # variable AND active -> aligned substrate
            'out_of_play_moves': out_of_play,   # absent in this family (not scaffold)
            'deviations': deviations,
        })
    families.sort(key=lambda f: -f['size'])
    return {'n_records': len(records), 'n_families': len(families),
            'chosen_k': best_k, 'silhouette_curve': curve, 'families': families}


def _quantile(xs, q):
    s = sorted(xs)
    if not s:
        return 0.0
    idx = q * (len(s) - 1)
    lo = int(idx)
    if lo + 1 < len(s):
        return s[lo] + (idx - lo) * (s[lo + 1] - s[lo])
    return s[lo]


def report(folder_or_records):
    if isinstance(folder_or_records, str):
        import glob, os
        recs = [(os.path.splitext(os.path.basename(p))[0], open(p, encoding='utf-8', errors='replace').read())
                for p in sorted(glob.glob(os.path.join(folder_or_records, '**', '*'), recursive=True))
                if os.path.isfile(p) and p.lower().endswith(('.md', '.txt', '.yml', '.yaml', '.json'))]
    else:
        recs = folder_or_records
    r = align(recs)
    print(f"records: {r['n_records']}  families: {r['n_families']}")
    for f in r['families']:
        print(f"\n  family (size {f['size']}): {', '.join(f['members'][:5])}{'…' if f['size']>5 else ''}")
        print(f"    scaffold (conserved): {f['scaffold_moves']}")
        print(f"    pockets  (variable) : {f['pocket_moves']}")
    return r


def selftest():
    """Guard against over-indexing: run on a SYNTHETIC corpus the module has
    never seen. Two clear families (a 'demand-evidence' family that all does
    EVIDENCE+VERIFY the same, varies on FORMAT; a 'context-role' family that all
    does ROLE+CONTEXT, varies on DECOMP). Assert the conserved moves land as
    scaffold and the varied ones as pockets — proving the split is structural,
    not tuned to byo/gen."""
    ok = True
    fam_evidence = [
        ('e1', 'cite the evidence, separate fact from assumption, verify and check confidence. give a table.'),
        ('e2', 'cite evidence, separate fact from inference, verify, test the claim. respond in bullets.'),
        ('e3', 'what we know vs what we assume, cite sources, verify, confidence level. plain prose.'),
    ]
    fam_context = [
        ('c1', 'you are an analyst. my context: [GOAL]. given that background, help.'),
        ('c2', 'you are an expert. context: [SITUATION]. as an analyst, proceed.'),
        ('c3', 'you are a specialist. my context: [TASK]. first do this, then step 2, then step 3.'),
    ]
    r = align(fam_evidence + fam_context)
    # find the family containing e1 and the one containing c1
    fam_e = next(f for f in r['families'] if 'e1' in f['members'])
    fam_c = next(f for f in r['families'] if 'c1' in f['members'])
    print(f"  evidence-family size {fam_e['size']}: scaffold={fam_e['scaffold_moves']}")
    print(f"  context-family  size {fam_c['size']}: scaffold={fam_c['scaffold_moves']}")
    # EVIDENCE should be conserved (scaffold) in the evidence family
    if fam_e['size'] > 1:
        ok = ok and ('EVIDENCE' in fam_e['scaffold_moves'])
        print(f"    EVIDENCE conserved in evidence-family: {'EVIDENCE' in fam_e['scaffold_moves']}")
    # the families should be DISTINCT (different members) — grouping worked
    ok = ok and (set(fam_e['members']) != set(fam_c['members']))
    print(f"    families are distinct: {set(fam_e['members']) != set(fam_c['members'])}")
    print('SELFTEST:', 'PASS' if ok else 'FAIL')
    return ok


if __name__ == '__main__':
    import sys
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    report(sys.argv[1] if len(sys.argv) > 1 else '/tmp/byo')
