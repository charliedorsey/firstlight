#!/usr/bin/env python3
"""
move_grammar.py — compress prompts by their COGNITIVE-MOVE GRAMMAR, not vocabulary.

THE REDIRECTION (from the prompting field manual, ch.1/3/5): a strong
prompt is "complete, not long" — its essence is the COGNITIVE ARCHITECTURE it
imposes (the moves it forces: assign a role, decompose, demand a counter-case,
fix a format, require verification). Two prompts can share no vocabulary and be
the same prompt architecturally; share all vocabulary and be opposite. Every
word-based compression we tried read the wrong layer — which is exactly why a
homogeneous corpus (shared dialect, distinct *moves*) defeated it.

THE METHOD (from hunt_prime_grammar.py): don't encode by raw values; encode by
STRUCTURAL MOTIF (the prime hunt used up/down/quartile transitions), then test
whether the motif-class fractions DISCRIMINATE or are a low-pass artifact. Here
the alphabet is cognitive moves; each prompt is a sequence of moves; the
"grammar" is the distribution of move-motifs (n-grams of moves).

MOVE ALPHABET (the structural verbs a prompt can perform, per the book):
  ROLE      assign a persona/role          ("you are a…", "act as")
  DECOMP    decompose into steps/parts     (numbered steps, "first… then…")
  CONSTRAIN set constraints/scope          ("only", "must", "do not", limits)
  CONTEXT   request/supply context         ("my context", "given that", "[SLOT]")
  RESIST    demand counter-case/critique   ("strongest case against", "what's wrong")
  EVIDENCE  separate fact/inference        ("what we know vs assume", "cite", "uncertain")
  FORMAT    fix output shape               ("table", "json", "sections", "bullet")
  VERIFY    require checking/confidence     ("verify", "confidence", "falsify", "test")
  EXEMPLAR  give examples                  ("for example", "e.g.", "like this:")
  TONE      set register/voice             ("concise", "formal", "warm", "plain")

This module is stdlib-only and embeddable. It is a SENSOR (move-detection), deliberately
mid-resolution: not raw words (noise), not binary has-structure (low-pass).
"""
from __future__ import annotations
import re, math
from collections import Counter

# Each move = a set of surface signals. Mid-resolution: enough to fire reliably,
# coarse enough to be a motif not a word. (The book's anatomy is the source.)
MOVES = {
    'ROLE':      [r'\byou are an?\b', r'\bact as\b', r'\byour role\b', r'\bas an? (?:expert|analyst|engineer|specialist)\b'],
    'DECOMP':    [r'^\s*\d+\.\s', r'\bstep \d\b', r'\bfirst\b.*\bthen\b', r'\bbreak (?:it|this) down\b', r'\bdecompose\b'],
    'CONSTRAIN': [r'\bonly\b', r'\bmust\b', r'\bdo not\b', r"\bdon't\b", r'\bnever\b', r'\bno more than\b', r'\bmax(?:imum)?\b', r'\bconstraint'],
    'CONTEXT':   [r'\bmy context\b', r'\bgiven that\b', r'\bcontext:\b', r'\[[A-Z][A-Z0-9 _/\-]+\]', r'\baudience\b', r'\bbackground\b'],
    'RESIST':    [r'\bstrongest case against\b', r"\bwhat'?s wrong\b", r'\bcounter', r'\bobjection', r'\bdevil', r'\bpush back\b', r'\bcritique\b', r'\bweakness', r'\bfailure mode'],
    'EVIDENCE':  [r'\bwhat we (?:know|have)\b', r'\bassum', r'\bcite\b', r'\bevidence\b', r'\buncertain', r'\bfact\b', r'\binference\b', r'\bproof\b', r'\bgaps?\b'],
    'FORMAT':    [r'\btable\b', r'\bjson\b', r'\bbullet', r'\bsection', r'\bformat\b', r'\b\|\s*-+', r'\bmarkdown\b', r'\bheading'],
    'VERIFY':    [r'\bverify\b', r'\bconfidence\b', r'\bfalsif', r'\btest\b', r'\bcheck\b', r'\bvalidat', r'\bquality gate\b'],
    'EXEMPLAR':  [r'\bfor example\b', r'\be\.g\.', r'\blike this\b', r'\bexample:', r'\bsuch as\b'],
    'TONE':      [r'\bconcise\b', r'\bformal\b', r'\bwarm\b', r'\bplain\b', r'\btone\b', r'\bdirect\b', r'\bgrounded\b', r'\bno bullshit\b'],
}
MOVE_NAMES = list(MOVES)
_COMPILED = {m: [re.compile(p, re.I | re.M) for p in pats] for m, pats in MOVES.items()}


def move_profile(text):
    """Fraction-weighted presence of each move in a prompt. A move's strength =
    how many of its signals fire (capped), normalized — so it's a real-valued
    move vector, not just binary present/absent (avoids the low-pass artifact
    the prime hunt warned about)."""
    prof = {}
    for m in MOVE_NAMES:
        hits = sum(len(rx.findall(text)) for rx in _COMPILED[m])
        prof[m] = math.log1p(hits)        # damp; many hits shouldn't dominate
    # normalize to a unit-ish profile so prompts of different length compare
    tot = sum(prof.values()) or 1.0
    return {m: round(v / tot, 4) for m, v in prof.items()}


def move_sequence(text):
    """Order matters: encode the prompt as the SEQUENCE of moves in the order
    they first appear (the prime hunt cares about transitions/n-grams, not just
    counts). Returns a tuple alphabet-sequence for n-gram motif analysis."""
    firsts = []
    for m in MOVE_NAMES:
        pos = min((mt.start() for rx in _COMPILED[m] for mt in [rx.search(text)] if mt), default=None)
        if pos is not None:
            firsts.append((pos, m))
    return [m for _, m in sorted(firsts)]


def move_ngrams(seq, n=2):
    return Counter(tuple(seq[i:i+n]) for i in range(len(seq) - n + 1))


# ── the prime-hunt discrimination test, applied to move-grammar ───────────────
def js_divergence(c1, c2):
    keys = set(c1) | set(c2); n1 = sum(c1.values()) or 1; n2 = sum(c2.values()) or 1
    js = 0.0
    for k in keys:
        p, q = c1.get(k, 0)/n1, c2.get(k, 0)/n2
        m = (p + q) / 2
        if p > 0: js += 0.5 * p * math.log2(p / m)
        if q > 0: js += 0.5 * q * math.log2(q / m)
    return js


def discrimination_report(records):
    """Does the move-grammar DISCRIMINATE prompts, or is it flat (low-pass)?
    Measures spread of move-profiles across the corpus. High spread = the moves
    distinguish prompts (good); low spread = every prompt makes the same moves
    (the corpus is homogeneous even at the move layer)."""
    import statistics as st
    profs = {nm: move_profile(t) for nm, t in records}
    # per-move variance across the corpus: which MOVES discriminate this library?
    move_var = {}
    for m in MOVE_NAMES:
        col = [profs[nm][m] for nm in profs]
        move_var[m] = round(st.pstdev(col), 4)
    # pairwise profile distance (are prompts spread out in move-space?)
    names = list(profs)
    def dist(a, b): return sum(abs(a[m]-b[m]) for m in MOVE_NAMES)
    pair = [dist(profs[names[i]], profs[names[j]])
            for i in range(len(names)) for j in range(i+1, len(names))]
    return {
        'n': len(records),
        'discriminating_moves': sorted(((v, m) for m, v in move_var.items()), reverse=True),
        'mean_pairwise_move_distance': round(st.mean(pair), 4) if pair else 0,
        'profiles': profs,
    }


if __name__ == '__main__':
    import sys, glob, os
    def load(folder):
        return [(os.path.splitext(os.path.basename(p))[0], open(p, encoding='utf-8', errors='replace').read())
                for p in sorted(glob.glob(os.path.join(folder, '**', '*'), recursive=True))
                if os.path.isfile(p) and p.lower().endswith(('.md', '.txt', '.yml', '.yaml', '.json'))]
    folder = sys.argv[1]
    recs = load(folder)
    r = discrimination_report(recs)
    print(f"corpus: {folder}  ({r['n']} prompts)")
    print(f"mean pairwise move-distance: {r['mean_pairwise_move_distance']}  (higher = moves discriminate)")
    print("discriminating moves (variance across corpus):")
    for v, m in r['discriminating_moves']:
        bar = '█' * int(v * 200)
        print(f"  {m:9s} {v:.4f} {bar}")
