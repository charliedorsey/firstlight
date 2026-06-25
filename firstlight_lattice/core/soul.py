#!/usr/bin/env python3
"""
soul.py — the THIRD scoring axis: soul/charge (load-bearing-ness).

WHY (the design calibration): conviction (coherence) and breadth don't reconstruct
the top-tier rooms — they have, "lots of both charge and soul."
This axis measures that. From two donors:

  SOUL  (conservation_bridge.refusals): load-bearing refusal clauses — "do not
        hide risk behind elegance", "never fabricate results". HUNT_FINDINGS:
        a room's soul IS its conserved refusals. Authored rooms carry them;
        machine exhaust does not. Density of these = soul signal.

  CHARGE (corpus_charge.py): rank-projected structural weight. We adapt its
        substrate-agnostic signals to single prompts (no corpus graph here):
        - refusal_density   — soul clauses per kbyte (the load-bearing core)
        - recognition_density — distinct named concepts introduced per kbyte
        - structural_density  — sections/headers/slots per kbyte (scaffolding)
        Each rank-projected across the corpus to [-1,+1] (corpus_charge's move),
        weighted-summed. Per corpus_charge: small-but-dense beats large-but-sparse
        — density per kbyte, not raw size.

This is HEURISTIC (HUNT_FINDINGS is explicit: finds load-bearing structure, not
meaning). It is one COORDINATE, not a quality verdict.
"""
from __future__ import annotations
import re, math, os

# ported verbatim from conservation_bridge.refusals
_REFUSAL = re.compile(r"\b(do not|don't|never|must not|avoid|refuse|do_not)\b", re.I)
def refusal_clauses(txt):
    out = []
    for line in txt.split('\n'):
        l = line.strip().lstrip('-*").\'').strip()
        if _REFUSAL.search(l) and 15 < len(l) < 200:
            out.append(' '.join(l.lower().split()))
    return out

# named-concept proxy: quoted terms, CAPS tokens, [SLOT]s, `code`-spans, defined nouns
_CONCEPT = re.compile(r'\[[A-Z][A-Z0-9 _/\-]+\]|`[^`]+`|"[^"]{3,40}"|\b[a-z]+_[a-z_]+\b')
_STRUCT = re.compile(r'^\s*(#{1,6}\s|\d+\.\s|-\s|\*\s)|\[[A-Z_]+\]', re.M)

def rank_project(values):
    n = len(values)
    if n <= 1: return [0.0]*n
    order = sorted(range(n), key=lambda i: values[i])
    ranks=[0.0]*n; i=0
    while i<n:
        j=i
        while j+1<n and values[order[j+1]]==values[order[i]]: j+=1
        avg=(i+j)/2.0
        for k in range(i,j+1): ranks[order[k]]=avg
        i=j+1
    return [2.0*r/(n-1)-1.0 for r in ranks]

def soul_axis(records, w_refusal=0.5, w_recognition=0.3, w_structural=0.2):
    """Per corpus_charge: density-per-kbyte signals, rank-projected, weighted.
    refusal weighted highest — it's the load-bearing soul per HUNT_FINDINGS."""
    names=[n for n,_ in records]
    refusal_d, recog_d, struct_d, raw_refusals = [],[],[],[]
    for _, txt in records:
        kb = max(0.5, len(txt.encode('utf-8'))/1024.0)   # floor avoids tiny-file blowup
        refs = refusal_clauses(txt)
        raw_refusals.append(len(refs))
        refusal_d.append(len(refs)/kb)
        recog_d.append(len(set(_CONCEPT.findall(txt)))/kb)
        struct_d.append(len(_STRUCT.findall(txt))/kb)
    pr, pg, ps = rank_project(refusal_d), rank_project(recog_d), rank_project(struct_d)
    out={}
    for i,nm in enumerate(names):
        score = w_refusal*pr[i] + w_recognition*pg[i] + w_structural*ps[i]
        out[nm]={'soul': round(max(-1,min(1,score)),3),
                 'refusal_clauses': raw_refusals[i],
                 'refusal_density_rank': round(pr[i],3)}
    return out

if __name__=='__main__':
    import sys, glob, os
    folder=sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(__file__),'..','rooms')
    recs=[(os.path.splitext(os.path.basename(p))[0], open(p,encoding='utf-8',errors='replace').read())
          for p in sorted(glob.glob(os.path.join(folder,'**','*'),recursive=True))
          if os.path.isfile(p) and p.lower().endswith(('.md','.txt','.yml','.yaml','.json'))]
    s=soul_axis(recs)
    ranked=sorted(s.items(), key=lambda x:-x[1]['soul'])
    print(f"SOUL ranking ({len(recs)} rooms), top 15:")
    for nm,d in ranked[:15]:
        print(f"  {d['soul']:+.2f}  ({d['refusal_clauses']} refusals)  {nm}")
