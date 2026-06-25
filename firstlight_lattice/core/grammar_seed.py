#!/usr/bin/env python3
"""
grammar_seed.py — a lightweight, embeddable fork of the pocketed-stream
compressor's GRAMMAR mechanism, retargeted from FASTQ to prompts.

LINEAGE: the settled compressor (family_first) finds structure by promoting the
SHARED substructure across records to a dictionary, then encoding each record as
(shared grammar + its deviations). The original is FASTQ-bound (header/seq/plus/
quality, archive readers, ~hundreds of lines). This fork keeps ONLY the mechanism
and applies it to prompt-shaped records. This module is stdlib only — no numpy, no sklearn, no
torch — so it embeds anywhere.

THE MOVE (pocketed-stream, prompt-native):
  - SCAFFOLD = grammar shared across MANY prompts (role lines, section headers,
    slot syntax, governance dialect). High recurrence = conserved = boilerplate.
  - POCKET   = where each prompt DEVIATES from the shared grammar. Low recurrence
    = variable = the discriminating signal.
  - DIM SEED = each prompt's deviation profile. The recurring grammar is removed
    as scaffold; what's LEFT is what makes this prompt itself.

WHY THIS MIGHT BEAT TF-IDF on a HOMOGENEOUS library: when every room speaks one
governance dialect, TF-IDF drowns in the shared vocabulary. This explicitly
IDENTIFIES the shared dialect as scaffold and routes on the residue. (Whether
that actually separates low-variance corpora is the empirical question this file
is built to MEASURE, not assume.)
"""
from __future__ import annotations
import re, math
from collections import Counter

_TOK = re.compile(r'[a-z][a-z0-9_]{2,}')
# structural shingles too: section-header skeletons, slot patterns, list markers
_HEADER = re.compile(r'^\s*(?:#{1,6}\s*|\d+\.\s*|\*\*)([A-Za-z][A-Za-z &/]{2,30})', re.M)
_SLOT = re.compile(r'\[[A-Z][A-Z0-9 _/\-]{1,40}\]')


def _features(text):
    """A prompt's raw grammar features: content tokens + structural shingles.
    Mixing lexical and structural so 'shared grammar' captures BOTH a shared
    dialect (words) and a shared skeleton (section headers)."""
    low = text.lower()
    feats = Counter(_TOK.findall(low))
    # structural shingles, namespaced so they don't collide with words
    for h in _HEADER.findall(text):
        feats['§hdr:' + h.strip().lower()] += 1
    feats['§slots'] += len(set(_SLOT.findall(text)))
    feats['§nlines'] += 0  # placeholder; length handled by structural manifold
    return feats


def build_grammar(records, scaffold_quantile=0.6):
    """records: list of (name, text). Returns the shared-grammar dictionary
    (scaffold) and each record's deviation profile (pocket).

    A feature is SCAFFOLD if it recurs across many records (document-frequency
    above the quantile threshold). Everything else is POCKET — the per-record
    deviation that carries identity."""
    n = len(records)
    df = Counter()
    per = []
    for name, text in records:
        f = _features(text)
        per.append((name, f))
        for k in f:
            df[k] += 1
    # scaffold = features present in >= quantile fraction of records
    thresh = max(2, math.ceil(scaffold_quantile * n))
    scaffold = {k for k, d in df.items() if d >= thresh}
    # deviation profile = each record's features with scaffold removed,
    # weighted by rarity (rarer surviving feature = stronger identity signal)
    profiles = {}
    for name, f in per:
        prof = {}
        for k, c in f.items():
            if k in scaffold:
                continue
            idf = math.log((n + 1) / (df[k] + 0.5))
            prof[k] = c * idf
        profiles[name] = prof
    return {
        'scaffold': sorted(scaffold),
        'scaffold_size': len(scaffold),
        'profiles': profiles,
        'df': df, 'n': n,
    }


def cosine(a, b):
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values())) or 1.0
    nb = math.sqrt(sum(v * v for v in b.values())) or 1.0
    return dot / (na * nb)


def match(prompt, grammar):
    """Route a prompt by its deviation profile against the library's profiles."""
    pf = _features(prompt)
    scaffold = set(grammar['scaffold'])
    df, n = grammar['df'], grammar['n']
    pprof = {}
    for k, c in pf.items():
        if k in scaffold:
            continue
        idf = math.log((n + 1) / (df.get(k, 0) + 0.5))
        pprof[k] = c * idf
    scored = sorted(((name, round(cosine(pprof, prof), 3))
                     for name, prof in grammar['profiles'].items()),
                    key=lambda x: -x[1])
    gap = (scored[0][1] - scored[1][1]) if len(scored) > 1 else (scored[0][1] if scored else 0)
    return {'ranked': scored, 'winner': scored[0] if scored and scored[0][1] > 0.03 else None,
            'gap': round(gap, 3)}


# ── measurement: do deviation profiles DISCRIMINATE? (the empirical question) ──
def spread_metric(grammar):
    """How separated are the profiles? Mean pairwise cosine — LOW mean = profiles
    point in different directions = good discrimination; HIGH mean = they still
    look alike = the homogeneity wasn't solved, just relocated."""
    names = list(grammar['profiles'])
    profs = [grammar['profiles'][nm] for nm in names]
    sims = []
    for i in range(len(profs)):
        for j in range(i + 1, len(profs)):
            sims.append(cosine(profs[i], profs[j]))
    if not sims:
        return None
    return {'mean_pairwise_cosine': round(sum(sims) / len(sims), 3),
            'max_pairwise_cosine': round(max(sims), 3),
            'interpretation': 'low mean = profiles discriminate; high mean = still homogeneous'}


if __name__ == '__main__':
    import sys, glob, os
    folder = sys.argv[1] if len(sys.argv) > 1 else '.'
    recs = []
    for p in sorted(glob.glob(os.path.join(folder, '**', '*'), recursive=True)):
        if os.path.isfile(p) and p.lower().endswith(('.md', '.txt', '.yml', '.yaml', '.json')):
            recs.append((os.path.splitext(os.path.basename(p))[0],
                         open(p, encoding='utf-8', errors='replace').read()))
    g = build_grammar(recs)
    print(f"records: {g['n']}   shared-grammar (scaffold) size: {g['scaffold_size']}")
    print(f"spread: {spread_metric(g)}")
    print(f"sample scaffold terms: {g['scaffold'][:12]}")


# ── multiresolution scaffold (lifted from family_coarsening: coarse = fewer
#    anchors / shorter key = broader families / bigger shared scaffold;
#    fine = more anchors = narrower families / smaller scaffold / more pocket) ──
def build_grammar_multires(records, resolution='medium'):
    """resolution dials the scaffold threshold the way coarse/fine anchor-count
    dials family breadth in the compressor. coarse: a feature is scaffold if it
    appears in even a few records (big shared grammar, aggressive stripping).
    fine: scaffold only if nearly universal (small shared grammar, light strip)."""
    q = {'coarse': 0.35, 'medium': 0.6, 'fine': 0.85}[resolution]
    return build_grammar(records, scaffold_quantile=q)


def residual_dims(grammar, top_k=8):
    """Run dim-extraction over the RESIDUAL (post-scaffold pockets): which
    surviving features carry the most cross-record variance? Those are the
    dim seeds the prompt-codec would mint from this library's residual."""
    profiles = grammar['profiles']
    # collect every residual feature and its variance across records
    allfeat = set()
    for p in profiles.values():
        allfeat |= set(p)
    import statistics as st
    var = {}
    n = len(profiles)
    for k in allfeat:
        col = [profiles[nm].get(k, 0.0) for nm in profiles]
        if sum(1 for v in col if v) >= 2:        # appears in >=2 records' residual
            var[k] = st.pstdev(col)
    ranked = sorted(var.items(), key=lambda x: -x[1])[:top_k]
    return ranked
