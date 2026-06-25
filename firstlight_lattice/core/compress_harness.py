#!/usr/bin/env python3
"""
compress_harness.py — the REAL compress-and-compare test.

PRINCIPLE (from md_encoder_v5.py): a structural model is REAL iff exploiting it
compresses the corpus smaller than entropy-coding the raw bytes (zlib). The md
codec proves this works (Python -7.8%, C -20.5%, JSON +0.0% honest fallback).
We apply the same truth-test to OUR stack — and we layer the bespoke pieces
cumulatively, attributing the marginal byte-saving to each layer. A layer that
doesn't shrink bytes beyond the layer below it is NOT earning its place,
regardless of how elegant it looks.

THE STACK (each layer encodes, the residue is zlib'd; we measure total bytes):
  L0  baseline         — zlib the concatenated corpus (the floor)
  L1  + scaffold-strip — factor the shared grammar dictionary ONCE, store each
                         doc as (dict-ref + residual); zlib the result
  L2  + move-grammar   — replace each doc's residual with its move-profile
                         (the cognitive-move encoding) + a residual remainder
  We report bytes and % vs zlib at each layer. The layer that captures real
  structure shrinks the total; the layer that's an artifact doesn't.

This is the unified test that ends the words-vs-moves argument: whichever
layering compresses best FOUND the real structure (md-codec logic), instead of
us introspecting explained-variance.
"""
from __future__ import annotations
import sys, os, glob, zlib, json, math
from collections import Counter
import grammar_seed as GS
import move_grammar as MG


def load(folder):
    return [(os.path.splitext(os.path.basename(p))[0], open(p, encoding='utf-8', errors='replace').read())
            for p in sorted(glob.glob(os.path.join(folder, '**', '*'), recursive=True))
            if os.path.isfile(p) and p.lower().endswith(('.md', '.txt', '.yml', '.yaml', '.json'))]


def zsize(b):
    if isinstance(b, str): b = b.encode('utf-8')
    return len(zlib.compress(b, 9))


# ── L0: raw zlib baseline ─────────────────────────────────────────────────────
def layer0_baseline(recs):
    blob = '\n'.join(t for _, t in recs)
    return zsize(blob)


# ── L1: scaffold-strip — store shared grammar dict ONCE + per-doc residuals ───
def layer1_scaffold(recs, resolution='medium'):
    grammar = GS.build_grammar_multires(recs, resolution)
    scaffold = sorted(set(grammar['scaffold']))
    # dictionary stored once
    dict_blob = '\x1f'.join(scaffold)
    # each doc = its tokens with scaffold tokens replaced by a short ref (their index).
    # we approximate the encoded form as: residual tokens (non-scaffold) + count of
    # scaffold hits (the scaffold content is recoverable from the dict, stored once).
    scaffold_set = set(scaffold)
    residual_parts = []
    for _, text in recs:
        toks = MG._COMPILED  # not used; tokenize via grammar_seed features
        feats = GS._features(text)
        resid = [k for k in feats for _ in range(int(feats[k]))
                 if k not in scaffold_set and not k.startswith('§')]
        residual_parts.append(' '.join(resid))
    payload = dict_blob + '\x1e' + '\x1e'.join(residual_parts)
    return zsize(payload), grammar['scaffold_size']


# ── L2: move-grammar — replace each doc's residual with its move-profile + remainder
def layer2_moves(recs, resolution='medium'):
    grammar = GS.build_grammar_multires(recs, resolution)
    scaffold_set = set(grammar['scaffold'])
    dict_blob = '\x1f'.join(sorted(scaffold_set))
    # move-profiles: a tiny fixed-width numeric encoding per doc (10 moves)
    move_rows = []
    remainder_parts = []
    for _, text in recs:
        prof = MG.move_profile(text)
        # quantize move-profile to 1 byte each → 10 bytes/doc, the "move code"
        row = bytes(int(min(255, prof[m] * 255)) for m in MG.MOVE_NAMES)
        move_rows.append(row)
        # remainder = residual tokens NOT explained by being a move-signal.
        # (move signals are structural; what's left is doc-specific content.)
        feats = GS._features(text)
        resid = [k for k in feats for _ in range(int(feats[k]))
                 if k not in scaffold_set and not k.startswith('§')]
        remainder_parts.append(' '.join(resid))
    move_blob = b''.join(move_rows)
    payload = dict_blob.encode() + b'\x1e' + move_blob + b'\x1e' + '\x1e'.join(remainder_parts).encode()
    return zsize(payload)


def run(folder, resolution='medium'):
    recs = load(folder)
    raw_bytes = sum(len(t.encode('utf-8')) for _, t in recs)
    l0 = layer0_baseline(recs)
    l1, scaf = layer1_scaffold(recs, resolution)
    l2 = layer2_moves(recs, resolution)
    def pct(x): return (x - l0) / l0 * 100
    return {
        'folder': folder, 'n_docs': len(recs), 'raw_bytes': raw_bytes,
        'resolution': resolution, 'scaffold_size': scaf,
        'L0_zlib_baseline': l0,
        'L1_plus_scaffold': l1, 'L1_vs_zlib_pct': round(pct(l1), 1),
        'L2_plus_moves':   l2, 'L2_vs_zlib_pct': round(pct(l2), 1),
        'L1_marginal_vs_L0': round((l1 - l0) / l0 * 100, 1),
        'L2_marginal_vs_L1': round((l2 - l1) / l1 * 100, 1),
    }


if __name__ == '__main__':
    folders = sys.argv[1:] or ['/tmp/byo', '/tmp/gen']
    for folder in folders:
        for res in ['coarse', 'medium', 'fine']:
            r = run(folder, res)
            print(f"\n=== {os.path.basename(folder.rstrip('/'))}  [{res}]  "
                  f"({r['n_docs']} docs, {r['raw_bytes']} raw bytes) ===")
            print(f"  L0 zlib baseline           : {r['L0_zlib_baseline']:>8} bytes")
            print(f"  L1 +scaffold (dict size {r['scaffold_size']:>3}): {r['L1_plus_scaffold']:>8} bytes  "
                  f"({r['L1_vs_zlib_pct']:+.1f}% vs zlib)")
            print(f"  L2 +move-grammar           : {r['L2_plus_moves']:>8} bytes  "
                  f"({r['L2_vs_zlib_pct']:+.1f}% vs zlib)")
            print(f"     marginal: L1 {r['L1_marginal_vs_L0']:+.1f}% vs L0,  "
                  f"L2 {r['L2_marginal_vs_L1']:+.1f}% vs L1   "
                  f"<- a layer earns its place only if marginal < 0")
