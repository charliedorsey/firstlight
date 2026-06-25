#!/usr/bin/env python3
"""
dim_nomenclature.py — nomenclature + valence + ELM re-key for the candidate dim pool.

Operator ask (F3/F12/F13), corrected after a first wrong pass:
  - re-keying must be in ELM-NATIVE terms (the stack's 2^(1/24) base, via compose's
    keying convention) — NOT an invented percentile scaling.
  - naming must reflect what each dim FUNCTIONALLY measures (which rooms cluster high
    vs low), not the raw SVD top-term salad.
  - orientation (valence) so positive = the more-descriptive pole, recorded.
Selection (combined variance explained, tested strategies) lives in dim_select.py.

WHAT EACH ARM MEASURES (functional, read off the room poles):
  semantic (residual-SVD over scaffold-stripped vocab): each axis is a CONTRAST in
    subject space — e.g. builder/produce rooms at one pole vs presence/reflection at the
    other. Named by the rooms at each pole, not the bare terms.
  structural (prompt_manifold shape): section_count / numbered_steps / len_lines — how
    much surface scaffolding the room carries. Positive = more structure.
  move (move-SVD over the 10 cognitive moves): each axis is a CONTRAST between move
    families a room demands — e.g. CONSTRAIN-heavy vs EVIDENCE-heavy.

ELM RE-KEY (the native convention, from compose._elm_key):
  ELM = 2^(1/24). A value is keyed as the number of ELM steps it sits above/below the
  FAMILY MEDIAN (robust norm), tanh-squashed over a one-octave (~24-step) window to
  [-1,+1]. positive = above the family-typical; this is the council-ready magnitude.
  For signed SVD coords we key the ORIENTED coordinate against the family median of the
  oriented coordinates, using the same step-ratio logic shifted to handle centered data.
"""
from __future__ import annotations
import os, math, statistics as st, numpy as np
import semantic_lattice as SL
import grammar_seed as GS
import prompt_manifold as PM
from compose import _elm_key, ELM      # the native ELM keying + base (do not reinvent)
try:
    import move_dimensions as MD
    _HAVE_MOVE = True
except Exception:
    _HAVE_MOVE = False


# ── ELM keying for a full dim column ─────────────────────────────────────────
def elm_key_column(col, return_median=False):
    """Re-key a dim's coordinates to ELM-native [-1,+1] against the column's family
    median, using the stack's 2^(1/24) step logic (compose._elm_key convention).

    compose._elm_key is built for absolute move-magnitudes vs a positive mean. SVD
    coords are signed/centered, so we key the SHIFTED-positive column (so ratios are
    well-defined) against its median, which is mathematically the same ELM-step measure:
    steps = log_ELM(value/median); magnitude = tanh(steps/24). Structural z-scores and
    move/semantic coords all go through the identical transform → one native scale.

    return_median=True also returns (lo, med) so a PROMPT can be keyed against the SAME
    family reference the rooms used (projection must not re-derive its own median)."""
    col = np.asarray(col, float)
    lo = col.min()
    shifted = col - lo + 1e-6            # make strictly positive so log-ratio is defined
    med = st.median(shifted) or 1e-6
    out = []
    for v in shifted:
        steps = math.log((v + 1e-9) / (med + 1e-9), ELM)   # ELM steps above/below median
        out.append(round(math.tanh(steps / 24.0), 4))      # one-octave squash to [-1,+1]
    keyed = np.array(out)
    if return_median:
        return keyed, lo, med
    return keyed


def _elm_key_one(value, lo, med):
    """Key a SINGLE value (a prompt's coord on one dim) against the room family's stored
    (lo, med) — identical transform to elm_key_column, so prompt and rooms share a scale.
    A prompt can fall below the room family's floor (more extreme than any room); clamp
    the shifted value to stay strictly positive so the log-ratio is defined (it just keys
    to the bottom of the [-1,+1] range)."""
    shifted = max(value - lo + 1e-6, 1e-9)
    steps = math.log(shifted / (med + 1e-9), ELM)
    return round(math.tanh(steps / 24.0), 4)


# ── orientation (valence) — PRINCIPLED RULE ──────────────────────────────────
# Operator intent: "positive = more descriptive of the variance." The pole where the
# variance-carrying DISTINCTIVE rooms live (largest |coord|) is the side doing the
# discriminating; the opposite pole is the near-zero "default/absent" cluster. So:
#   ORIENT each SVD axis so its EXTREME pole (max |coord|) is positive.
# This is deterministic, reproducible, and puts + on the active/distinctive side of each
# locked name (verified: sem[4]+ = hunting/debug = "what's wrong"; sem[3]+ = gtm =
# "external audience"; sem[5]+ = multipart/charge = "artifact output"; etc.).
# Structural axes are already signed by a real quantity (more sections/steps/lines), so
# they are NOT re-oriented — positive already means "more surface structure."
def _orient(col):
    """Orient an SVD axis so its extreme (variance-carrying) pole is positive. Returns
    the oriented column and the sign applied (+1 kept, -1 flipped)."""
    col = np.asarray(col, float)
    if abs(col.min()) > abs(col.max()):
        return -col, -1
    return col, +1


# ── functional naming: name from the rooms at each pole ──────────────────────
def _pole_rooms(coords_by_room, n=2):
    items = sorted(coords_by_room.items(), key=lambda kv: -kv[1])
    hi = [k for k, _ in items[:n]]
    lo = [k for k, _ in items[-n:]]
    return hi, lo


def _short(room):
    return room.replace('_room', '').replace('_generic', '').replace('_v', ' v')[:18]


def build_named_dims(rooms_folder=None):
    """ORIENT (extreme-pole rule) → ELM-RE-KEY → attach LOCKED names. Returns per-dim
    cards with id, arm, locked name, the oriented + pole label, orientation sign, the
    ELM-keyed coords, plus M (n_rooms × n_dims) and room_order."""
    if rooms_folder is None:
        rooms_folder = os.path.join(os.path.dirname(__file__), '..', 'rooms')
    recs = SL.load_rooms_canonical(rooms_folder)
    room_order = [n for n, _ in recs]
    cards, cols = [], []

    # LOCKED nomenclature (DIM_NOMENCLATURE.md). Each: (name, +pole label, −pole label).
    # +pole = the variance-carrying / distinctive side after extreme-pole orientation.
    LOCKED = {
        'sem[0]': ('generative slime-mold ↔ linearization', 'slime-mold (branch out)', 'linearization (synthesize)'),
        'sem[1]': ('aesthetic refinement ↔ pragmatic direction', 'aesthetic refinement', 'pragmatic direction'),
        'sem[2]': ('refine ↔ review', 'review (build/assess new)', 'refine (iterate existing)'),
        'sem[3]': ('internal ↔ external audience', 'external audience (market)', 'internal audience (person)'),
        'sem[4]': ("what's wrong ↔ what's right", "what's wrong (diagnose)", "what's right (analyze forward)"),
        'sem[5]': ('artifact output ↔ presence', 'artifact output (objects)', 'presence (be-with)'),
        'str[0]': ('many ↔ few sections', 'many sections', 'few sections'),
        'str[1]': ('step-procedural ↔ freeform', 'step-procedural', 'freeform'),
        'str[2]': ('long ↔ short instructions', 'long instructions', 'short instructions'),
        'mov[0]': ('high specification & rigor ↔ loose', 'high rigor (constrain/evidence/verify)', 'loose / unfocused'),
        'mov[1]': ('constraint-bound ↔ evidence-dependent', 'constraint-bound', 'evidence-dependent'),
        'mov[2]': ('strict output format ↔ freeform', 'strict format (+verify)', 'freeform / abstention'),
        'mov[3]': ('form & voice ↔ evidence & verification', 'form & voice driven', 'evidence & verification driven'),
    }

    def card(idp, arm, raw, structural=False, axis_index=None):
        if structural:
            oriented = np.asarray(raw, float); sign = +1
        else:
            oriented, sign = _orient(raw)
        keyed, lo, med = elm_key_column(oriented, return_median=True)
        nm, pos_lbl, neg_lbl = LOCKED.get(idp, (idp, '+', '−'))
        cbr = {room_order[i]: float(oriented[i]) for i in range(len(room_order))}
        hi, lo_rooms = _pole_rooms(cbr)
        cards.append({'id': idp, 'arm': arm, 'name': nm,
                      'pos_pole': pos_lbl, 'neg_pole': neg_lbl,
                      'pos_rooms': [_short(r) for r in hi], 'neg_rooms': [_short(r) for r in lo_rooms],
                      'orientation_sign': sign, 'elm_keyed': keyed,
                      # projection state: replay the exact transform on a prompt's coord
                      '_proj': {'arm': arm, 'axis_index': axis_index, 'sign': sign,
                                'elm_lo': lo, 'elm_med': med,
                                'field': (raw_field if structural else None)}})
        cols.append(keyed)

    sem = SL.discover_axes(recs)
    sem_fitted = sem['_fitted']
    for i, a in enumerate(sem['axes']):
        card(f"sem[{i}]", 'semantic', [sem['coords'][n][i] for n in room_order], axis_index=i)
    lib = PM.build_library_from_records(recs)
    for i, a in enumerate(lib['axes']):
        raw_field = a['field']
        card(f"str[{i}]", 'structural', [lib['rooms'][r]['coord'][raw_field] for r in range(len(lib['rooms']))],
             structural=True, axis_index=i)
    move_fitted = None
    if _HAVE_MOVE:
        md = MD.discover_move_dims(recs)
        move_fitted = md['_fitted']
        for i, a in enumerate(md['axes']):
            card(f"mov[{i}]", 'move', [md['coords'][n][i] for n in room_order], axis_index=i)

    M = np.array(cols).T if cols else np.zeros((len(room_order), 0))
    # cache the fitted transformers so project_prompt can replay each arm exactly
    fitted = {'semantic': sem_fitted, 'structural': {'axes': lib['axes'], 'norm': lib['norm']},
              'move': move_fitted}
    return {'cards': cards, 'M': M, 'room_order': room_order, 'fitted': fitted}


def project_prompt(prompt, built):
    """F2: project a LIVE prompt into the candidate-dim space the rooms live in.

    Runs the prompt through each arm's FITTED transform (the same vectorizer/SVD/norms the
    rooms used), then applies each dim's stored orientation sign and ELM-keys against the
    SAME family (lo, med) the rooms were keyed against — so the prompt's coordinate is
    directly comparable to room coordinates. Returns the prompt's ELM-keyed vector over the
    full candidate pool (same column order as built['cards'])."""
    import numpy as np
    cards = built['cards']; fitted = built['fitted']
    out = []
    # --- semantic: scaffold-strip the prompt, tf-idf transform, svd transform ---
    sf = fitted['semantic']
    scaffold = set(sf['grammar']['scaffold'])
    feats = GS._features(prompt)
    toks = []
    for k, c in feats.items():
        if k in scaffold or k.startswith('§'):
            continue
        toks.extend([k] * int(c))
    sem_vec = sf['vec'].transform([' '.join(toks)])
    sem_coords = sf['svd'].transform(sem_vec)[0]      # prompt's raw semantic coords
    # --- structural: witness the prompt, z-score against stored norm ---
    str_axes = fitted['structural']['axes']; str_norm = fitted['structural']['norm']
    str_coord = PM.score(prompt, str_axes, str_norm)   # {field: z}
    # --- move: move_profile, center by stored mean, svd transform ---
    mv_coords = None
    if fitted['move'] is not None:
        import move_grammar as MG
        prof = np.array([MG.move_profile(prompt)[m] for m in MG.MOVE_NAMES], float)
        prof = prof - fitted['move']['mean']
        mv_coords = fitted['move']['svd'].transform(prof.reshape(1, -1))[0]

    for c in cards:
        p = c['_proj']; arm = p['arm']; i = p['axis_index']
        if arm == 'semantic':
            raw = float(sem_coords[i]) if i < len(sem_coords) else 0.0
        elif arm == 'structural':
            raw = float(str_coord.get(p['field'], 0.0))
        else:
            raw = float(mv_coords[i]) if (mv_coords is not None and i < len(mv_coords)) else 0.0
        raw *= p['sign']                                   # apply stored orientation
        out.append(_elm_key_one(raw, p['elm_lo'], p['elm_med']))   # key vs room family
    return np.array(out)


def selftest():
    out = build_named_dims()
    M = out['cards'] and out['M']
    print(f"{len(out['cards'])} dims — oriented (extreme pole = +), ELM-keyed, locked names:\n")
    for j, c in enumerate(out['cards']):
        col = out['M'][:, j]
        print(f"  {c['id']:8s} {c['arm']:10s} sign{c['orientation_sign']:+d}  {c['name']}")
        print(f"           + = {c['pos_pole']}  →  rooms {c['pos_rooms'][:2]}")
    M = out['M']; rng = (M.min(), M.max())
    print(f"\nELM-keyed range [{rng[0]:+.3f},{rng[1]:+.3f}]  all in [-1,1]: {rng[0]>=-1.0001 and rng[1]<=1.0001}")
    sds = {}
    for j, c in enumerate(out['cards']):
        sds.setdefault(c['arm'], []).append(float(np.std(M[:, j])))
    print("post-ELM-key sd by arm (comparable = no arm dominates by scale):")
    for arm, v in sds.items():
        print(f"  {arm:10s} [{min(v):.3f},{max(v):.3f}]")
    # F2: projection smoke-test — a prompt projects into the space, coords in [-1,1]
    pv = project_prompt("help me debug this KeyError in my python code", out)
    ok = all(-1.0001 <= x <= 1.0001 for x in pv) and len(pv) == len(out['cards'])
    print(f"project_prompt: {len(pv)} coords, all in[-1,1]={ok}")
    print("SELFTEST: PASS")
    return out


if __name__ == '__main__':
    selftest()
