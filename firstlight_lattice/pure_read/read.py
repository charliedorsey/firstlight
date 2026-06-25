#!/usr/bin/env python3
"""
read.py — the per-turn READ arm. Pure Python standard library, zero deps.

Loads a cache built by build_cache.py, checks whether the skills library has
changed since the cache was built (warns loudly, proceeds — never gates), routes
the live prompt, and prints the routing readout.

Usage:
    python3 read.py <cache.json> "<prompt>"
    python3 read.py <cache.json> --json "<prompt>"

The routing here is byte-identical to the heavy sklearn router (proven by
parity_router.py). The dashboard panels in turn_dashboard.py are already pure
Python and can be layered on top of the route this returns.
"""

import sys
import os
import json
import re
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pure_router as PR

# turn_dashboard lives in core/ but is PURE python (verified import-blocked), so
# the read arm can use it directly for the full dashboard without pulling in any
# heavy dependency. We add core/ to the path lazily and degrade gracefully if the
# layout differs.
_CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'core')
try:
    sys.path.insert(0, _CORE)
    import turn_dashboard as TD
except Exception:
    TD = None


# ── corpus fingerprint (pure stdlib; mirrors build_cache.compute_fingerprint) ─
# We re-derive the routed record set the same way load_rooms_canonical does, but
# without importing it (that would pull in the heavy module). The rule for a
# skills library: one record per directory containing a SKILL.md; otherwise one
# record per .md/.txt/.yml/.yaml/.json file. This must match the build side, so
# if load_rooms_canonical's rule changes, this mirror must change with it.
_READABLE = ('.md', '.txt', '.yml', '.yaml', '.json')
_SKIP_NAMES = {'ROOM_CONTRACT.md', 'LICENSE.skills.txt'}


def _read_text(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception:
        return ''


def _is_skills_library(folder):
    for root, _dirs, files in os.walk(folder):
        if 'SKILL.md' in files:
            return True
    return False


def _canonical_name(path, root):
    """Mirror semantic_lattice's room-id rule: relpath, strip ext, sep -> '__'."""
    rel = os.path.relpath(path, root)
    stem = os.path.splitext(rel)[0]
    return stem.replace(os.sep, '__')


def live_fingerprint(folder):
    """Recompute {record_name: sha256(text)} cheaply, matching the build side.
    Uses the same canonical naming as semantic_lattice.load_rooms_canonical."""
    fp = {}
    if _is_skills_library(folder):
        # one record per skill directory: its SKILL.md, named by its rel path
        for root, _dirs, files in os.walk(folder):
            if 'SKILL.md' in files:
                path = os.path.join(root, 'SKILL.md')
                name = _canonical_name(path, folder)
                text = _read_text(path)
                fp[name] = hashlib.sha256(text.encode('utf-8')).hexdigest()
    else:
        for root, _dirs, files in os.walk(folder):
            for fn in files:
                if fn in _SKIP_NAMES or fn.startswith('.'):
                    continue
                if os.path.splitext(fn)[1].lower() in _READABLE:
                    path = os.path.join(root, fn)
                    name = _canonical_name(path, folder)
                    text = _read_text(path)
                    fp[name] = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return fp


def check_staleness(cache, folder):
    """Compare the cache's stored fingerprint to the live library. Returns a list
    of human-readable warning lines (empty if fresh). Never raises, never gates."""
    stored = cache.get('corpus_fingerprint', {})
    if not folder or not os.path.isdir(folder):
        return []  # can't check (cache may have moved); stay quiet, proceed
    live = live_fingerprint(folder)
    if live == stored:
        return []
    added = sorted(set(live) - set(stored))
    removed = sorted(set(stored) - set(live))
    changed = sorted(k for k in (set(live) & set(stored)) if live[k] != stored[k])
    warn = ["⚠  the skills library has changed since this cache was built:"]
    if added:
        warn.append(f"     added:   {', '.join(added[:6])}"
                    + (f" (+{len(added)-6} more)" if len(added) > 6 else ""))
    if removed:
        warn.append(f"     removed: {', '.join(removed[:6])}"
                    + (f" (+{len(removed)-6} more)" if len(removed) > 6 else ""))
    if changed:
        warn.append(f"     edited:  {', '.join(changed[:6])}"
                    + (f" (+{len(changed)-6} more)" if len(changed) > 6 else ""))
    warn.append("     routing reflects the OLD library. Rebuild to refresh:")
    warn.append("       ./run.sh build")
    return warn


def read_prompt(cache, prompt, k=3):
    # Optional embedding tier: active only if the cache has skill vectors AND an
    # embedding provider is configured (env vars). Default install: provider is
    # None -> route() uses the lexical tiers exactly as before, no network.
    provider = None
    if cache.get('embed_vectors'):
        try:
            import embed_provider as EP
            provider = EP.default_provider()
        except Exception:
            provider = None

    # STAGE ONE — deliverable veto gate. Rules out skills whose output WORLD is
    # categorically wrong for what the prompt asks (e.g. an emotional prompt vs a
    # code skill). Loose by design: most technical prompts veto nothing. Stage two
    # then discriminates within the survivors.
    gate_info = None
    candidates = None
    gi = cache.get('gate_index')
    if gi:
        try:
            import deliverable_gate as DG
            survivors, vetoed = DG.gate(prompt, gi)
            if vetoed:  # only constrain stage two when the gate actually fired
                candidates = survivors
            gate_info = {
                'prompt_worlds': sorted(DG.worlds_of(prompt)),
                'survivors': len(survivors),
                'vetoed': len(vetoed),
            }
        except Exception:
            gate_info = None

    # STAGE TWO — semantic/keyword routing within the survivors.
    routed = PR.route(prompt, cache, k=k, embed_provider=provider, candidates=candidates)
    top = routed[0] if routed else None
    # confidence read: low if top score weak or gap to runner-up tiny
    low_conf = False
    reason = ''
    if not top or top[1] < 0.12:
        low_conf, reason = True, f"weak top score {top[1] if top else 0:.3f}"
    elif len(routed) > 1 and (top[1] - routed[1][1]) < 0.03:
        low_conf, reason = True, f"tiny gap to runner-up ({top[1]-routed[1][1]:.3f})"

    # SECOND OPINION: soft-coherence as a confidence calibrator (never a router).
    # 'confirmed' agreement is a strong positive signal (~94% correct in testing);
    # 'unconfirmed' disagreement is exactly the shaky zone and raises uncertainty.
    second = None
    if top:
        second = PR.confidence_signal(prompt, cache, top[0])
        if second['status'] == 'unconfirmed':
            low_conf = True
            alt = second['soft_top'].replace('__SKILL', '')
            reason = (reason + '; ' if reason else '') + \
                     f"second opinion disagrees (leans {alt})"
        elif second['status'] == 'confirmed' and not low_conf:
            reason = reason or 'second opinion agrees'

    result = {
        'prompt': prompt,
        'routes': [{'room': n, 'score': s, 'via': v} for n, s, v in routed],
        'low_confidence': low_conf,
        'confidence_note': reason,
        'second_opinion': second,
        'gate': gate_info,
        'claim_status': 'advisory_not_truth',
    }
    # FULL DASHBOARD — the per-turn workspace readout. turn_dashboard.analyze()
    # depends only on the prompt text (not on corpus state), and is pure python,
    # so it composes directly onto the free read path. We keep the semantic-
    # lattice ROUTE (the cache-based skill matcher, the better one) as the
    # authoritative route, and attach the dashboard's coordinate + compute budget
    # + turn-shape + posture + council + flags as advisory panels.
    if TD is not None:
        try:
            dash = TD.analyze(prompt)
            result['dashboard'] = {
                'coordinate': dash['coordinate'],
                'overall_confidence': dash['overall_confidence'],
                'compute_budget': dash['compute_budget'],
                'turn_shape': dash['turn_shape'],
                'posture': dash['posture'],
                'flags': dash['flags'],
                'council': dash['council'],
                'confidence_warnings': dash['confidence_warnings'],
                'active_crossterms': dash['active_crossterms'],
            }
        except Exception as e:
            result['dashboard_error'] = str(e)
    return result


def render_text(r, warnings):
    out = []
    for w in warnings:
        out.append(w)
    if warnings:
        out.append('')
    out.append(f"prompt: {r['prompt']}")
    out.append('')
    hdr = 'routes to (advisory):'
    if r['low_confidence']:
        hdr += f"  (LOW CONFIDENCE — {r['confidence_note']}; closest shown, don't lean on it)"
    out.append(hdr)
    g = r.get('gate')
    if g and g.get('vetoed'):
        out.append(f"   (stage 1: ruled out {g['vetoed']} skill(s) as wrong output-shape "
                   f"for {'/'.join(g['prompt_worlds']) or '?'}; {g['survivors']} candidates remain)")
    for rt in r['routes']:
        out.append(f"   {rt['score']:.3f}  {rt['room']}   [{rt['via']}]")

    so = r.get('second_opinion')
    if so:
        if so['status'] == 'confirmed':
            out.append(f"   ✓ second opinion confirms (soft-coherence agrees, {so['soft_score']:.2f})")
        elif so['status'] == 'unconfirmed':
            alt = so['soft_top'].replace('__SKILL', '')
            out.append(f"   ⚠ second opinion DISAGREES — soft-coherence leans "
                       f"{alt} ({so['soft_score']:.2f}); treat the route as uncertain")

    d = r.get('dashboard')
    if d:
        b = d['compute_budget']
        out.append('')
        out.append(f"compute budget:  {b['level']}  —  {b['guidance']}")
        if b.get('drivers'):
            out.append(f"   drivers: {', '.join(b['drivers'])}")
        ts = d['turn_shape']
        out.append(f"turn shape:      {ts['method']}  ·  {ts['output']}")
        if ts.get('run_signals'):
            out.append(f"   run signals: {', '.join(ts['run_signals'])}")
        # coordinate, compact
        coord = d['coordinate']
        coord_str = '  '.join(f"{k} {v:+.2f}" for k, v in coord.items())
        out.append(f"coordinate:      {coord_str}")
        cc = d['council']
        out.append(f"council:         conviction {cc['conviction']}/5 "
                   f"({cc['direction']}; for {cc['lean_for']} / against "
                   f"{cc['lean_against']} / flat {cc['flat']})")
        if d.get('posture'):
            out.append(f"posture:         {'; '.join(d['posture'])}")
        if d.get('flags'):
            out.append(f"watch:           {'; '.join(d['flags'])}")
        if d.get('confidence_warnings'):
            out.append(f"confidence:      {'; '.join(d['confidence_warnings'])}")

    out.append('')
    out.append(f"[{r['claim_status']}] suggestion only — you decide.")
    return '\n'.join(out)


def main():
    args = sys.argv[1:]
    as_json = '--json' in args
    args = [a for a in args if a != '--json']
    if len(args) < 2:
        sys.stderr.write('usage: read.py <cache.json> [--json] "<prompt>"\n')
        sys.exit(2)
    cache_path, prompt = args[0], args[1]
    try:
        cache = PR.load_cache(cache_path)
    except FileNotFoundError:
        sys.stderr.write(
            f"read: no cache at '{cache_path}'. Build one first:\n"
            f"  ./run.sh build\n")
        sys.exit(2)
    folder = cache.get('rooms_folder') or cache.get('manifest', {}).get('rooms_folder')
    warnings = check_staleness(cache, folder)
    r = read_prompt(cache, prompt)
    if as_json:
        if warnings:
            r['staleness_warning'] = warnings
        print(json.dumps(r, indent=2))
    else:
        print(render_text(r, warnings))


if __name__ == '__main__':
    main()
