#!/usr/bin/env python3
"""
deliverable_gate.py — STAGE ONE of two-stage routing: the deliverable-class veto.

The architecture (Charlie's spec):
  STAGE 1 (this file): rule out skills whose OUTPUT SHAPE is categorically wrong
      for what the prompt asks. A loose, high-certainty VETO — not a ranker. It
      does nothing most of the time (e.g. all technical-production requests pass
      through) and only fires when there is a true categorical gulf (e.g. an
      emotional/reflective prompt vs. a code-generating skill). Keeps a BUCKET.
  STAGE 2 (pure_router): semantic / keyword discrimination WITHIN the survivors.

Why a veto and not a score: a stage-one false REJECT is unrecoverable (the right
skill never reaches stage two), while a false ACCEPT is cheap (stage two filters
it). So the gate errs loose: when the prompt's shape is unknown, it vetoes nothing.

Signal source (the common case): most users state the wanted deliverable INLINE in
the prompt ("write tests", "explain", "help me decide"). A skill's deliverable
class comes from its DECLARED PURPOSE (the SKILL.md `description` line / room title),
NOT its full body — a long body mentions every shape and is too noisy to gate on.

This is pure standard library (re only), so it runs on the free read path.
"""

import re

# Coarse output-shape categories. A text can carry several. These are deliberately
# broad — the gate only needs to separate *worlds* of output, not fine types.
SHAPES = {
    'MAKE_CODE':  r'\b(test|tests|code|function|implement|script|api|endpoint|build|'
                  r'set ?up|setup|create|add|generate|scaffold|migration|server|app|'
                  r'configure|install|write a|component)\b',
    'TRANSFORM':  r'\b(optimi[sz]e|refactor|convert|migrate|improve|slim|reduce|'
                  r'rewrite|fix|tune|speed up)\b',
    'DIAGNOSE':   r'\b(diagnose|debug|root cause|investigate|trace|find the|analy[sz]e|'
                  r'detect|scan|audit|leak|decode|inspect)\b',
    'EXPLAIN':    r'\b(explain|describe|summar|overview|teach|guide|document|'
                  r'walk ?through|how does)\b',
    'REVIEW':     r'\b(review|critique|evaluate|assess|feedback|grade)\b',
    'PLAN':       r'\b(plan|strategy|roadmap|approach|outline|decide|position|launch|'
                  r'prioriti[sz]e)\b',
    'REFLECT':    r'\b(feel|feeling|sit with|reflect|emotional|cope|grappl|hard time|'
                  r'anxious|overwhelm|process this)\b',
    'WRITE_PROSE': r'\b(poem|story|essay|song|lyric|write me a|creative|narrative|'
                   r'blog post|article)\b',
}

# Deliverable WORLDS. Veto fires only ACROSS worlds, never within one. All the
# code-adjacent shapes share a world (they all yield code/artifacts and a skill
# that "optimizes" can serve a "build" request), so they never veto each other.
WORLDS = {
    'TECHNICAL': {'MAKE_CODE', 'TRANSFORM', 'DIAGNOSE', 'REVIEW', 'EXPLAIN', 'PLAN'},
    'HUMAN':     {'REFLECT'},
    'CREATIVE':  {'WRITE_PROSE'},
}


def shapes_of(text):
    return {s for s, rx in SHAPES.items() if re.search(rx, text, re.I)}


def worlds_of(text_or_shapes):
    shp = text_or_shapes if isinstance(text_or_shapes, set) else shapes_of(text_or_shapes)
    out = set()
    for world, members in WORLDS.items():
        if shp & members:
            out.add(world)
    return out


def skill_purpose(skill_text):
    """The DECLARED purpose: SKILL.md `description:` frontmatter, or a room's first
    prose/title line. This is the narrow signal the gate reads — not the full body."""
    m = re.search(r'^description:\s*(.+)$', skill_text, re.M)
    if m:
        return m.group(1).strip()
    # room/yaml: try a name/title/intent field
    m = re.search(r'^(?:name|title|intent|purpose):\s*(.+)$', skill_text, re.M)
    if m:
        return m.group(1).strip()
    # fallback: first non-empty, non-frontmatter prose line
    for line in skill_text.splitlines():
        s = line.strip()
        if s and not s.startswith(('---', '#', '>', 'tags:', 'category:', 'version:')):
            return s
    return ''


def build_gate_index(rooms):
    """Precompute each skill's deliverable worlds from its declared purpose.
    rooms: {name: text}. Returns {name: set(worlds)} for the gate to use.
    Stored in the build cache so the read arm doesn't re-scan bodies."""
    return {n: sorted(worlds_of(skill_purpose(t))) for n, t in rooms.items()}


def gate(prompt, gate_index):
    """STAGE ONE. Return (survivors, vetoed).
    gate_index: {name: list(worlds)} from build_gate_index (cache-friendly).
    A skill survives if it shares a world with the prompt OR has no detected world
    (unknown shape -> never veto). Veto only fires across distinct worlds."""
    pw = worlds_of(prompt)
    if not pw:
        # prompt shape unknown -> gate is a no-op (loose by design)
        return list(gate_index), []
    survivors, vetoed = [], []
    for name, worlds in gate_index.items():
        ws = set(worlds)
        if not ws or (ws & pw):
            survivors.append(name)
        else:
            vetoed.append(name)
    # safety: never veto the entire library. If the gate would eliminate everyone
    # (e.g. a prompt world with no matching skills at all), pass everyone through
    # and let stage two decide — a false reject of the whole library is the worst
    # possible outcome.
    if not survivors:
        return list(gate_index), []
    return survivors, vetoed


if __name__ == '__main__':
    import sys
    import glob
    import os
    # quick demo over the shipped skills
    folder = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join(os.path.dirname(__file__), '..', '..', 'drop_your_skills_here')
    rooms = {}
    for d in glob.glob(os.path.join(folder, '*')):
        sk = os.path.join(d, 'SKILL.md')
        if os.path.isfile(sk):
            rooms[os.path.basename(d)] = open(sk, encoding='utf-8', errors='replace').read()
    idx = build_gate_index(rooms)
    for p in ['help me sit with a hard feeling', 'write end-to-end tests',
              'optimize this slow sql query', 'write me a poem about the sea']:
        surv, veto = gate(p, idx)
        print(f"'{p}': shapes={sorted(shapes_of(p))} worlds={sorted(worlds_of(p))}")
        print(f"   survivors {len(surv)}/{len(idx)}, vetoed {len(veto)}"
              + (f" (e.g. {veto[:4]})" if veto else ""))
