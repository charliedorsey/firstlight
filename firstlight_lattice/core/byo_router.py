#!/usr/bin/env python3
"""
byo_router.py — bring-your-own-room router for firstlight.

THE PROOF THIS ANSWERS: can a user drop a folder of arbitrary prompt files
(.md / .yml / .txt) into firstlight, have them organized + remembered, and have
the right one chosen when a turn comes in — using the SAME six-axis read the
turn_dashboard already computes? If yes, the product is "a turn-router you load
your own rooms into," not "a fixed room library."

DESIGN DISCIPLINE (anti-cathedral): this adds NO new sensing math. It imports
turn_dashboard and reuses sense_prompt + transform_to_dims verbatim, so a room
and a prompt are scored in one shared space. The only new thing is the SENSOR
applied to room files + an affinity match. Everything stays advisory; nothing
gates or auto-runs (the dashboard's governance contract is inherited).

A "room" here is just a text file. Structured rooms (firstlight YAML with
audience/governing_intent/held_tensions) get a richer read; a bare .txt prompt
still works — it's sensed as raw text. BYO means BYO.

Usage:
    python3 byo_router.py --rooms ./my_rooms "the incoming prompt"
    python3 byo_router.py --rooms ./my_rooms --json "the prompt"
    python3 byo_router.py --rooms ./my_rooms --list      # show loaded rooms + signatures
    python3 byo_router.py --selftest
"""
import sys, os, argparse, json, glob

import turn_dashboard as td

DIM_NAMES = ['stakes', 'register', 'form', 'openness', 'urgency', 'scope']


# ── room loading ────────────────────────────────────────────────────────────
def _extract_routing_text(path, raw):
    """What text best represents WHEN this room should fire. For a structured
    firstlight room, the audience + governing_intent + held_tensions describe the
    turn it wants; for a bare prompt file, the whole text is the signal. We pull
    the intent-bearing fields when present, else fall back to the full body."""
    low = raw.lower()
    if 'governing_intent' in low or 'held_tensions' in low or 'audience:' in low:
        keep = []
        for line in raw.splitlines():
            l = line.strip().lower()
            if any(l.startswith(k) for k in (
                'name:', 'audience:', 'stakes:', 'governing_intent', 'architecture',
                'instruction', 'use_when', '- do not', '- ', 'tensions')):
                keep.append(line)
        # intent fields + the held-tensions lines = the room's "when to fire" signal
        return '\n'.join(keep) if keep else raw
    return raw


def load_rooms(folder):
    """Load every .md/.yml/.yaml/.txt under folder as a room. Each room is
    sensed onto the same six axes a prompt is. Returns a list of dicts —
    'remembered' simply means: scanned once, signature cached in this object."""
    rooms = []
    pats = ('*.md', '*.markdown', '*.yml', '*.yaml', '*.txt')
    paths = []
    for pat in pats:
        paths += glob.glob(os.path.join(folder, '**', pat), recursive=True)
    for path in sorted(set(paths)):
        try:
            raw = open(path, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        if not raw.strip():
            continue
        routing_text = _extract_routing_text(path, raw)
        facts = td.sense_prompt(routing_text)
        dims = td.transform_to_dims(facts)
        name = os.path.splitext(os.path.basename(path))[0]
        rooms.append({
            'name': name,
            'path': path,
            'signature': dict(zip(DIM_NAMES, [round(d, 3) for d in dims])),
            '_vec': dims,
        })
    return rooms


# ── matching ────────────────────────────────────────────────────────────────
def _affinity(prompt_vec, room_vec):
    """How well does this room fit this turn? Cosine-style alignment on the six
    axes, but axis-weighted: form/openness/stakes/register carry posture; scope
    and urgency are secondary (they're about size/timing, not which discipline).
    Returns (-1..1). Higher = better fit. Deliberately simple and inspectable."""
    w = [0.9, 1.0, 1.0, 1.0, 0.4, 0.5]  # stakes,register,form,openness,urgency,scope
    num = sum(w[i] * prompt_vec[i] * room_vec[i] for i in range(6))
    pn = sum(w[i] * prompt_vec[i] ** 2 for i in range(6)) ** 0.5
    rn = sum(w[i] * room_vec[i] ** 2 for i in range(6)) ** 0.5
    if pn == 0 or rn == 0:
        return 0.0
    return num / (pn * rn)


def route(prompt, rooms, top_k=3):
    facts = td.sense_prompt(prompt)
    pvec = td.transform_to_dims(facts)
    scored = []
    for r in rooms:
        scored.append({
            'name': r['name'], 'path': r['path'],
            'affinity': round(_affinity(pvec, r['_vec']), 3),
            'signature': r['signature'],
        })
    scored.sort(key=lambda x: x['affinity'], reverse=True)
    # advisory confidence: a clear winner = a real gap to #2; a flat field = low conf
    gap = (scored[0]['affinity'] - scored[1]['affinity']) if len(scored) > 1 else scored[0]['affinity'] if scored else 0.0
    conf = 'high' if gap > 0.25 else 'medium' if gap > 0.1 else 'low'
    return {
        'prompt_signature': dict(zip(DIM_NAMES, [round(d, 3) for d in pvec])),
        'ranked': scored[:top_k],
        'winner': scored[0] if scored and scored[0]['affinity'] > 0.15 else None,
        'gap_to_second': round(gap, 3),
        'confidence': conf,
        'note': 'advisory — affinity matches your loaded rooms to this turn; you choose.',
    }


# ── render ───────────────────────────────────────────────────────────────────
def render(result, n_rooms):
    L = []
    L.append('')
    L.append('  ┌─ BYO ROUTER ──────────────────────────────────────────────')
    L.append(f'  │  loaded rooms: {n_rooms}   confidence: {result["confidence"]}'
             f'   gap→2nd: {result["gap_to_second"]}')
    sig = result['prompt_signature']
    L.append('  │  turn signature: ' + '  '.join(f'{k[:4]}{sig[k]:+.2f}' for k in DIM_NAMES))
    L.append('  │  ──────────────────────────────────────────────────────')
    if result['winner']:
        L.append(f'  │  ▸ BEST FIT: {result["winner"]["name"]}  (affinity {result["winner"]["affinity"]:+.2f})')
    else:
        L.append('  │  ▸ no loaded room clears the bar — answer directly, or add a room')
    L.append('  │  ──────────────────────────────────────────────────────')
    L.append('  │  ranked:')
    for r in result['ranked']:
        L.append(f'  │    {r["affinity"]:+.2f}  {r["name"]}')
    L.append('  │  ──────────────────────────────────────────────────────')
    L.append('  │  ' + result['note'])
    L.append('  └────────────────────────────────────────────────────────────')
    return '\n'.join(L)


# ── selftest ──────────────────────────────────────────────────────────────────
def selftest():
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as d:
        # three deliberately different BYO rooms, written as bare prompt files
        open(os.path.join(d, 'debugger.md'), 'w').write(
            'Debugging discipline. Reproduce the failure before theorizing. '
            'Fix the cause not the symptom. Do not call it fixed when only the '
            'error stopped. Run the test, find where reality diverges from belief.')
        open(os.path.join(d, 'feelings.txt'), 'w').write(
            'A room for when I am sad, scared, grieving, or my heart is heavy. '
            'Stay with the feeling. Do not rush to advice. I feel lonely and hurt.')
        open(os.path.join(d, 'builder.yml'), 'w').write(
            'name: builder\naudience: someone who wants to build and ship a '
            'concrete artifact\ngoverning_intent: write the code, create the file, '
            'produce the deliverable, implement and ship it.')
        rooms = load_rooms(d)
        assert len(rooms) == 3, f'expected 3 rooms, got {len(rooms)}'

        cases = [
            ('my code throws an exception, help me find why it is broken', 'debugger'),
            ('i feel so alone and scared tonight, my heart hurts', 'feelings'),
            ('build me a script that creates a pdf report', 'builder'),
        ]
        for prompt, expected in cases:
            res = route(prompt, rooms)
            got = res['winner']['name'] if res['winner'] else None
            mark = 'OK ' if got == expected else 'XX '
            if got != expected:
                ok = False
            print(f'  {mark} {expected:9s} <- "{prompt[:42]}"  got={got}')
    print('SELFTEST:', 'PASS' if ok else 'FAIL')
    return ok


def main():
    ap = argparse.ArgumentParser(description='firstlight BYO-room router')
    ap.add_argument('prompt', nargs='?', default='')
    ap.add_argument('--rooms', help='folder of your own .md/.yml/.txt rooms')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--list', action='store_true', help='show loaded rooms + signatures')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()

    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if not a.rooms:
        ap.error('--rooms FOLDER is required (point it at your prompt files)')
    rooms = load_rooms(a.rooms)
    if a.list:
        print(json.dumps([{'name': r['name'], 'signature': r['signature']} for r in rooms], indent=2))
        return
    if not a.prompt:
        prompt = sys.stdin.read()
    else:
        prompt = a.prompt
    result = route(prompt, rooms)
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        print(render(result, len(rooms)))


if __name__ == '__main__':
    main()
