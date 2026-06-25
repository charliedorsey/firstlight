#!/usr/bin/env python3
"""
firstlight.py — the firstlight_lattice RUNTIME (F1).

One entry point that ties the settled pieces together for a live prompt. Composes
existing modules; reinvents nothing:

  ROUTE    semantic_lattice.SemanticLattice.route  — which room(s) fit the prompt
           (coherence → tf-idf fallback; the settled hybrid router).
  PROJECT  dim_nomenclature.project_prompt          — the prompt's coordinate in the
           oriented/ELM-keyed candidate-dim space (same transform the rooms went through).
  SELECT   dim_pool.build_and_select                — the ≤6 dims that maximize combined
           variance + orthogonality + positive skew (the single selector, dim_select).
  READ     council.council_read                     — conviction over the prompt's vector
           on the SELECTED dims (the sacred-hexagon read when 6).

Two modes:
  build_mode()  — run the corpus passes ONCE, cache the selected dims + per-dim
                  projection state + room coords + a manifest. (The expensive part.)
  run_mode(prompt, built) — cheap per-prompt: route + project + council read → ONE
                  advisory readout. Claims are advisory_not_truth: the lattice suggests a
                  room and reads the prompt's character; it does not pronounce a verdict.

The positive-skew bias is SELECTOR logic (which dims describe the corpus with max
orthogonality+variance+positive skew) — applied in build_mode's selection, NOT in how an
individual prompt projects. Where a single prompt falls per-dim is a descriptive read
(e.g. a short prompt reading -1 on long-instructions is correct, not an error); it informs
the room suggestion, it is not itself biased.
"""
from __future__ import annotations
import os, sys, json, argparse
import semantic_lattice as SL
import dim_nomenclature as DN
import dim_pool as DP
import council as CO

try:
    import turn_dashboard as TD
    _HAVE_DASH = True
except Exception:
    _HAVE_DASH = False

# Confidence thresholds for the no-forced-room mechanism. A route reads as low-confidence
# (the lattice declines to force a pick) when the top score is weak OR barely beats the
# runner-up. Tuned conservatively; the probe set is meant to expose where these should move.
LOW_CONF_SCORE = 0.08    # top semantic score below this = weak match
LOW_CONF_GAP = 0.03      # top minus second below this = router can't separate the leaders


def _rooms_folder(folder=None):
    return folder or os.path.join(os.path.dirname(__file__), '..', 'rooms')


# ── BUILD MODE — the once-per-corpus passes, cached ──────────────────────────
def build_mode(rooms_folder=None, strategy='max_combined'):
    """Run the corpus discovery ONCE: build the candidate dim pool, orient + ELM-key
    (dim_nomenclature), select the ≤6 dims (dim_select via dim_pool). Returns a cached
    'built' bundle the run-mode reuses for every prompt + a manifest summarizing it."""
    folder = _rooms_folder(rooms_folder)
    built = DN.build_named_dims(folder)              # oriented + ELM-keyed dims + fitted state
    sel = DP.build_and_select(folder, strategy=strategy)
    # Per-room breadth + soul, computed across THIS corpus (the seeded room list, or a
    # user-uploaded prompt library — same code, whatever folder is passed). These are
    # corpus-relative PROPERTIES OF EACH ROOM (rank-projected across the corpus), not
    # scores for any live prompt. A routed prompt inherits its destination room's values.
    room_faces = {}
    try:
        import breadth as BR, soul as SO
        recs = SL.load_rooms_canonical(folder)
        b = BR.breadth_axis(recs); s = SO.soul_axis(recs)
        for nm in b:
            room_faces[nm] = {'breadth': b[nm]['breadth'],
                              'effective_moves': b[nm]['raw_effective_moves'],
                              'soul': s.get(nm, {}).get('soul'),
                              'refusal_clauses': s.get(nm, {}).get('refusal_clauses')}
    except Exception:
        pass
    # map selected pool IDs → their column index in built['cards'] (for prompt projection)
    id_to_col = {c['id'].split('::')[0] if '::' in c['id'] else c['id']: j
                 for j, c in enumerate(built['cards'])}
    sel_cols = []
    for did in sel['selected_dims']:
        base = did.split('::')[0]
        sel_cols.append(id_to_col.get(base))
    manifest = {
        'rooms_folder': os.path.abspath(folder),
        'pool_size': sel['pool_size'],
        'arm_counts': sel['arm_counts'],
        'strategy': sel['strategy'],
        'combined_variance_explained': sel['selection'].get('combined_variance_explained'),
        'selected_dims': [{'id': c['id'], 'name': c['name'],
                           'pos_pole': c['pos_pole'], 'neg_pole': c['neg_pole']}
                          for j, c in enumerate(built['cards']) if j in sel_cols],
        'strategy_comparison': {s: v['meta'].get('combined_variance_explained')
                                for s, v in sel.get('strategy_comparison', {}).items()},
    }
    return {'built': built, 'selection': sel, 'selected_cols': sel_cols,
            'room_faces': room_faces, 'manifest': manifest}


# ── RUN MODE — per prompt: route + project + read ────────────────────────────
def run_mode(prompt, cached, k=3, with_posture=True):
    """Read a live prompt: route to room(s), project into the selected dims, council read.
    Returns ONE advisory readout (claim_status: advisory_not_truth)."""
    built = cached['built']; sel = cached['selection']; sel_cols = cached['selected_cols']
    folder = cached['manifest']['rooms_folder']

    # ROUTE — settled semantic router over the SAME canonical corpus used by the
    # lattice build. This is what makes BYO prompt libraries (.md/.txt/.yml/.json)
    # route through the same records the dim pool/council saw.
    rooms = dict(SL.load_rooms_canonical(folder))
    R = SL.SemanticLattice(rooms)
    routed = R.route(prompt, k=k)            # [(room, score, via)]

    # CONFIDENCE / NO-FORCED-ROOM (one gentle mechanism — operator decision).
    # We do NOT pronounce a scary "no room" verdict. Instead every match carries a
    # confidence read. A match is LOW-CONFIDENCE (no forced room) when the top score is
    # weak in absolute terms OR barely beats the runner-up (tiny gap = the router isn't
    # sure which). "what is 2+2" (top ~0) and "what time is it" (top 0.067, gap 0.02) both
    # land here: the lattice shows what it found but declines to force a confident pick.
    top_score = routed[0][1] if routed else 0.0
    second = routed[1][1] if len(routed) > 1 else 0.0
    gap = top_score - second
    low_confidence = (top_score < LOW_CONF_SCORE) or (gap < LOW_CONF_GAP)
    forced_room = not low_confidence

    # PROJECT — prompt's coordinate in the full pool, then restrict to the SELECTED dims
    full_vec = DN.project_prompt(prompt, built)
    prompt_dims = [round(float(full_vec[c]), 4) for c in sel_cols if c is not None]

    # READ — council conviction over the prompt's selected-dim vector
    read = CO.council_read(prompt_dims)

    # Attach each routed room's corpus-computed breadth/soul (a PROPERTY OF THE ROOM,
    # computed in build_mode across the corpus — NOT a score for the prompt).
    room_faces = cached.get('room_faces', {})
    _folder = cached['manifest'].get('rooms_folder')
    routed_with_faces = []
    for n, s, v in routed:
        rf = room_faces.get(n, {})
        routed_with_faces.append({'room': n, 'display_name': _display_name(n, _folder),
                                  'score': s, 'via': v,
                                  'breadth': rf.get('breadth'), 'soul': rf.get('soul')})

    # CHARACTER — name the prompt's strongest dims (the descriptive read)
    cards = built['cards']
    character = []
    for c_i, col in enumerate(sel_cols):
        if col is None:
            continue
        v = prompt_dims[c_i] if c_i < len(prompt_dims) else 0.0
        card = cards[col]
        pole = card['pos_pole'] if v >= 0 else card['neg_pole']
        character.append({'dim': card['name'], 'coord': v, 'reads_as': pole})
    character.sort(key=lambda d: -abs(d['coord']))

    # POSTURE (optional) — turn_dashboard's posture read, if available
    posture = None
    if with_posture and _HAVE_DASH:
        try:
            posture = TD.posture_for_prompt(prompt) if hasattr(TD, 'posture_for_prompt') else None
        except Exception:
            posture = None

    return {
        'claim_status': 'advisory_not_truth',
        'prompt': prompt,
        'rooms_folder': cached['manifest'].get('rooms_folder'),
        'route': routed_with_faces,
        'suggested_room': routed[0][0] if routed else None,
        'suggested_room_name': (_display_name(routed[0][0], cached['manifest'].get('rooms_folder')) if routed else None),
        'suggested_room_faces': (room_faces.get(routed[0][0], {}) if routed else {}),
        'confidence': ('low' if low_confidence else 'clear'),
        'confidence_detail': {'top_score': round(top_score, 3), 'gap_to_second': round(gap, 3),
                              'low_confidence': low_confidence},
        'prompt_character': character[:6],
        'council': {'conviction': read['conviction'],
                    'conviction_fraction': read['conviction_fraction'],
                    'n_readers': read['n_readers'],
                    'feral_priest': read['feral_priest'],
                    'sacred_hexagon': read['sacred_hexagon'],
                    'n_dims': read['n_dims']},
        'posture': posture,
        'note': "The lattice suggests a room and reads the prompt's character. It suggests; "
                "you decide.",
    }


def _display_name(record_id, rooms_folder=None):
    """Prefer a skill's own frontmatter `name:` over the path-derived record id.
    `pdf-processing__SKILL` → `pdf-processing`. Falls back to a de-pathified id."""
    # Try to read the skill's SKILL.md frontmatter name.
    if rooms_folder and record_id.endswith('__SKILL'):
        rel = record_id[:-len('__SKILL')].replace('__', os.sep)
        p = os.path.join(rooms_folder, rel, 'SKILL.md')
        try:
            head = open(p, encoding='utf-8', errors='replace').read(4000)
            import re as _re
            m = _re.search(r'(?m)^\s*name\s*:\s*(.+?)\s*$', head)
            if m:
                return m.group(1).strip().strip('"').strip("'")
        except Exception:
            pass
    # Generic fallback: drop a trailing __SKILL, show last path segment.
    rid = record_id[:-len('__SKILL')] if record_id.endswith('__SKILL') else record_id
    return rid.split('__')[-1]


def readout_text(r):
    """Human-readable advisory readout."""
    rooms_folder = r.get('rooms_folder')
    conf = r.get('confidence', 'clear')
    cd = r.get('confidence_detail', {})
    if conf == 'low':
        header = (f"  (LOW CONFIDENCE — top score {cd.get('top_score')}, gap {cd.get('gap_to_second')}; "
                  f"closest suggestion shown, but don't lean on it)")
    else:
        header = ""
    lines = [f"prompt: {r['prompt']}", "", f"routes to (advisory):{header}"]
    for x in r['route']:
        bs = ""
        if x.get('breadth') is not None and x.get('soul') is not None:
            bs = f"   ·room: breadth {x['breadth']:+.2f}, soul {x['soul']:+.2f}"
        lines.append(f"  {x['score']:>6.3f}  {_display_name(x['room'], rooms_folder)}   [{x['via']}]{bs}")
    lines.append("")
    lines.append("prompt reads as:")
    for d in r['prompt_character']:
        lines.append(f"  {d['coord']:+.2f}  {d['reads_as']}   ({d['dim']})")
    c = r['council']
    lines.append("")
    lines.append(f"council conviction: {c['conviction']}/{c.get('n_readers', '?')}"
                 f"  (fraction {c['conviction_fraction']}"
                 f"{', feral_priest' if c['feral_priest'] else ''}"
                 f"{', sacred hexagon' if c['sacred_hexagon'] else ''})")
    lines.append("")
    lines.append(f"[{r['claim_status']}] {r['note']}")
    return "\n".join(lines)


def selftest():
    cached = build_mode()
    m = cached['manifest']
    print(f"BUILD: pool {m['pool_size']} → selected {len(m['selected_dims'])} dims "
          f"(strategy {m['strategy']}, CVE {m['combined_variance_explained']})")
    print(f"  arms: {m['arm_counts']}")
    print("  selected dims:")
    for d in m['selected_dims']:
        print(f"    {d['id']:10s} {d['name']}")
    print()
    for prompt in ["help me debug this KeyError in my python code",
                   "help me sit with a hard feeling and reflect"]:
        r = run_mode(prompt, cached)
        print(f"RUN: '{prompt[:42]}'")
        print(f"  → {r['suggested_room']}  | conviction {r['council']['conviction']}/"
              f"{r['council'].get('n_dims')}  | top read: "
              f"{r['prompt_character'][0]['reads_as'] if r['prompt_character'] else '—'}")
    # invariants
    r = run_mode("test prompt", cached)
    assert r['claim_status'] == 'advisory_not_truth'
    assert isinstance(r['route'], list)
    # confidence model: out-of-scope prompts read LOW confidence (no forced room),
    # but still return a suggestion — the AI always decides, the lattice never forces.
    nr = run_mode("what is 2+2", cached)
    assert nr['confidence'] == 'low', "2+2 should read low-confidence"
    assert nr['suggested_room'] is not None, "still returns a suggestion (never forces a refusal)"
    print(f"confidence model: 'what is 2+2' → {nr['confidence']} confidence "
          f"(top {nr['confidence_detail']['top_score']}), suggestion still offered")
    print("\nSELFTEST: PASS")
    return cached


def main():
    ap = argparse.ArgumentParser(description="firstlight_lattice runtime — read a prompt")
    ap.add_argument("prompt", nargs="?", help="the prompt to read")
    ap.add_argument("--rooms", help="rooms folder (defaults to bundled)")
    ap.add_argument("--json", action="store_true", help="emit JSON readout")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest(); return
    # Friendly guard: axis discovery needs a small corpus to fit. A folder with
    # fewer than 3 readable prompt/skill files would otherwise raise deep in the
    # vectorizer; catch it here and explain, instead of dumping a traceback.
    if args.rooms:
        try:
            import semantic_lattice as _SL
            _n = len(_SL.load_rooms_canonical(args.rooms))
        except ValueError:
            sys.stderr.write(
                f"firstlight: no readable prompt/skill files found in '{args.rooms}'.\n"
                "Expected .md/.txt/.yml/.yaml/.json (a Claude skill is skill-name/SKILL.md).\n")
            sys.exit(2)
        except Exception:
            _n = None
        if _n is not None and _n < 3:
            sys.stderr.write(
                f"firstlight: '{args.rooms}' has {_n} readable file(s); "
                "need at least 3 to read a prompt against a library.\n"
                "Add more skills/prompts to the folder, or point --rooms at the "
                "bundled library (firstlight_lattice/rooms).\n")
            sys.exit(2)
    cached = build_mode(args.rooms)
    if not args.prompt:
        print(json.dumps(cached['manifest'], indent=2)); return
    r = run_mode(args.prompt, cached)
    print(json.dumps(r, indent=2) if args.json else readout_text(r))


if __name__ == '__main__':
    main()
