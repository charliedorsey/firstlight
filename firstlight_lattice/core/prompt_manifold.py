#!/usr/bin/env python3
"""
prompt_manifold.py — self-calibrating axis discovery for a prompt library.

THE PROBLEM (measured, not assumed): different people's prompt libraries have
structurally DISJOINT shapes. the example rooms: 0% role-scaffold, 0 slots, ~386
lines, prose-heavy. Generic templates: 100% role-scaffold, ~5.7 slots, tables,
~59 lines. An axis-set authored on ONE corpus is blind to the other's defining
features (the generic set's #1 discriminator — [SLOTS] — does not exist in
in the example library at all). Therefore: axes MUST be derived per-upload, from whatever was
dropped in. This module does that.

ARCHITECTURE (proven half + honest stub):
  1. prompt_witness(text)  — a FIXED, prompt-native structural reader. Not fastq.
     Reads the features a PROMPT has: role scaffold, sections, [SLOTS], tables,
     numbered steps, fences, length, bullet density. General across anyone's
     prompts; does not encode any one corpus's vocabulary.
  2. derive_axes(witnesses) — runs the CV (coefficient-of-variation) test over
     the uploaded set and KEEPS ONLY the witness fields that actually vary within
     THIS library. Those high-variance fields ARE this library's structural axes.
     Self-calibrating: the corpus defines its own dimensions.
  3. score(text, axes) — projects any prompt/room onto the discovered axes,
     z-normalized against the library so the coordinate is comparable.
  4. SEMANTIC LAYER — NOT BUILT. Structural axes separate prompts by SHAPE, not
     SUBJECT (beekeeping vs tax law read identically here). topic_signal() is an
     explicit stub with the interface a real embedder/AI-selector would fill.
     Shipping a fake version would be the elegant-fiction failure; it is named,
     not faked.

Ingests .md .markdown .txt .yml .yaml .json from any folder.

Usage:
    python3 prompt_manifold.py --rooms ./any_folder            # derive + show axes
    python3 prompt_manifold.py --rooms ./any_folder --json
    python3 prompt_manifold.py --selftest
"""
from __future__ import annotations
import sys, os, re, glob, json, argparse, statistics as st


# ── 1. prompt-native structural witness (FIXED, corpus-agnostic) ──────────────
_SLOT = re.compile(r'\[[A-Z][A-Z0-9 _/\-]{1,40}\]')          # [TOPIC], [OPTION A]
_HEADER = re.compile(r'^\s*(?:#{1,6}\s|\d+\.\s|\*\*[A-Z])', re.M)
_NUMBERED = re.compile(r'^\s*\d+\.\s', re.M)
_BULLET = re.compile(r'^\s*[-*]\s', re.M)
_ROLE = re.compile(r'^\s*(?:you are an?|act as|your role is|as an?)\b', re.I)

def _flatten_json_or_yaml(text):
    """If the file is JSON (or simple YAML), flatten values to text so the witness
    reads the CONTENT, not the punctuation. Best-effort; falls back to raw."""
    t = text.strip()
    if t.startswith('{') or t.startswith('['):
        try:
            obj = json.loads(t)
            out = []
            def walk(x):
                if isinstance(x, dict):
                    for k, v in x.items(): out.append(str(k)); walk(v)
                elif isinstance(x, list):
                    for v in x: walk(v)
                else: out.append(str(x))
            walk(obj)
            return '\n'.join(out)
        except Exception:
            return text
    return text


def prompt_witness(text: str) -> dict:
    """Structural facts about a prompt/room. Prompt-native, no fastq, no
    corpus-specific vocabulary. Every field is a surface-verifiable count."""
    text = _flatten_json_or_yaml(text)
    lines = text.splitlines()
    nlines = max(len(lines), 1)
    return {
        'role_scaffold':  1.0 if _ROLE.match(text.strip()) else 0.0,
        'section_count':  float(len(_HEADER.findall(text))),
        'slot_count':     float(len(set(_SLOT.findall(text)))),
        'numbered_steps': float(len(_NUMBERED.findall(text))),
        'bullet_density': round(len(_BULLET.findall(text)) / nlines, 3),
        'has_table':      1.0 if ('|--' in text or '| ---' in text) else 0.0,
        'has_fence':      1.0 if '```' in text else 0.0,
        'len_lines':      float(nlines),
    }

WITNESS_FIELDS = ['role_scaffold', 'section_count', 'slot_count', 'numbered_steps',
                  'bullet_density', 'has_table', 'has_fence', 'len_lines']


# ── 2. derive the library's OWN axes via the CV test ──────────────────────────
def derive_axes(witnesses: list[dict], cv_threshold: float = 0.5) -> list[dict]:
    """Keep only the witness fields that actually VARY within this library.
    A field with high coefficient of variation discriminates the rooms; a flat
    field carries no routing information for THIS corpus. The surviving fields
    are this library's structural axes. Self-calibrating by construction."""
    axes = []
    n = len(witnesses)
    for f in WITNESS_FIELDS:
        col = [w[f] for w in witnesses]
        mean = st.mean(col)
        sd = st.pstdev(col)
        cv = (sd / mean) if mean else 0.0
        # also admit binary fields that split the set (mean near 0.5) even if CV math is degenerate
        is_splitting_binary = (set(col) <= {0.0, 1.0}) and (0.15 < mean < 0.85)
        if cv >= cv_threshold or is_splitting_binary:
            axes.append({'field': f, 'mean': round(mean, 3), 'std': round(sd, 3),
                         'cv': round(cv, 3), 'reason': 'splits' if is_splitting_binary else 'varies'})
    return axes


def score(text: str, axes: list[dict], norm: dict) -> dict:
    """Project a prompt onto the discovered axes, z-normalized against the library
    so coordinates are comparable across axes of different natural scale."""
    w = prompt_witness(text)
    coord = {}
    for ax in axes:
        f = ax['field']
        sd = norm[f]['std'] or 1.0
        coord[f] = round((w[f] - norm[f]['mean']) / sd, 3)
    return coord


# ── 3. SEMANTIC LAYER — explicitly NOT BUILT ──────────────────────────────────
def topic_signal(text: str):
    """STUB. Structural axes separate prompts by SHAPE, not SUBJECT. Two rooms
    about cooking and debugging can have identical structure. Real topic
    discrimination needs a semantic signal (local embeddings, or an AI selector
    quarantined to ambiguous cases). NOT BUILT here — building a fake version
    would be the elegant-fiction failure this whole project is built to refuse.
    The interface is fixed so a real backend drops in without touching the
    structural manifold above."""
    raise NotImplementedError(
        'topic_signal is the unbuilt semantic layer — structural manifold only, by design')


# ── library object ────────────────────────────────────────────────────────────
def build_library_from_records(records):
    """Build the structural manifold from EXPLICIT (name, text) records — the
    canonical-loader-fed path. This is the corpus-honest entry: the caller decides
    which docs are in the library (e.g. the 23 room YAMLs, ROOM_CONTRACT excluded),
    so the structural axes/norm are derived over the SAME corpus as the semantic arm.
    Fixes the prior contamination where build_library() re-scanned *.md and pulled in
    ROOM_CONTRACT.md, building structural axes over 24 docs vs semantic's 23."""
    rooms = []
    for name, raw in records:
        if raw and raw.strip():
            rooms.append({'name': name, 'path': None, 'witness': prompt_witness(raw)})
    if not rooms:
        return {'rooms': [], 'axes': [], 'norm': {}}
    witnesses = [r['witness'] for r in rooms]
    axes = derive_axes(witnesses)
    norm = {ax['field']: {'mean': ax['mean'], 'std': ax['std']} for ax in axes}
    for r in rooms:
        r['coord'] = score_from_witness(r['witness'], axes, norm)
    return {'rooms': rooms, 'axes': axes, 'norm': norm}


def build_library(folder: str):
    """Folder-scanning entry (kept for standalone use). NOTE: scans broadly; for the
    firstlight pipeline use build_library_from_records() with the canonical loader so
    the structural and semantic arms share one corpus (no ROOM_CONTRACT contamination)."""
    pats = ('*.md', '*.markdown', '*.txt', '*.yml', '*.yaml', '*.json')
    paths = []
    for p in pats:
        paths += glob.glob(os.path.join(folder, '**', p), recursive=True)
    records = []
    for path in sorted(set(paths)):
        try:
            raw = open(path, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        records.append((os.path.splitext(os.path.basename(path))[0], raw))
    return build_library_from_records(records)


def score_from_witness(w, axes, norm):
    return {ax['field']: round((w[ax['field']] - norm[ax['field']]['mean']) /
            (norm[ax['field']]['std'] or 1.0), 3) for ax in axes}


# ── selftest ──────────────────────────────────────────────────────────────────
def selftest():
    import tempfile
    ok = True
    # corpus A: slot-heavy generic templates  | corpus B: prose rooms
    with tempfile.TemporaryDirectory() as d:
        for i in range(4):
            open(f'{d}/gen_{i}.md', 'w').write(
                f'You are an analyst.\nDo [TASK_{i}] for [AUDIENCE].\n'
                f'1. STEP ONE\n2. STEP TWO\n3. STEP THREE\n| a |--| b |\n')
        for i in range(4):
            open(f'{d}/prose_{i}.txt', 'w').write(
                'A reflective discipline. ' * (20 + i*40) + '\nStay with what is here.')
        lib = build_library(d)
        fields = {ax['field'] for ax in lib['axes']}
        # the two corpora differ on slots/role/length -> those should be discovered axes
        assert lib['axes'], 'no axes derived'
        assert 'slot_count' in fields or 'role_scaffold' in fields, \
            f'expected slot/role axis to discriminate, got {fields}'
        assert 'len_lines' in fields, f'expected length to discriminate, got {fields}'
        # the slot-heavy and prose rooms should land in different coordinate regions
        gen = [r for r in lib['rooms'] if r['name'].startswith('gen')]
        pro = [r for r in lib['rooms'] if r['name'].startswith('prose')]
        if 'slot_count' in fields:
            gmean = st.mean(r['coord']['slot_count'] for r in gen)
            pmean = st.mean(r['coord']['slot_count'] for r in pro)
            sep = abs(gmean - pmean)
            print(f'  axes discovered: {sorted(fields)}')
            print(f'  slot-axis separation gen vs prose: {sep:.2f} (want > 1.0)')
            ok = ok and sep > 1.0
        # topic layer must remain honestly unbuilt
        try:
            topic_signal('anything'); ok = False; print('  XX topic_signal should raise')
        except NotImplementedError:
            print('  OK topic_signal honestly unbuilt')
    print('SELFTEST:', 'PASS' if ok else 'FAIL')
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rooms')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if not a.rooms:
        ap.error('--rooms FOLDER required')
    lib = build_library(a.rooms)
    if a.json:
        print(json.dumps({'axes': lib['axes'],
                          'rooms': [{'name': r['name'], 'coord': r['coord']} for r in lib['rooms']]},
                         indent=2))
        return
    print(f"\n  derived {len(lib['axes'])} axes from {len(lib['rooms'])} files "
          f"(this library defines its own manifold):")
    for ax in lib['axes']:
        print(f"    {ax['field']:15s}  cv={ax['cv']:.2f}  ({ax['reason']})")
    print("\n  semantic/topic axis: NOT BUILT (structural manifold only — by design)")


if __name__ == '__main__':
    main()
