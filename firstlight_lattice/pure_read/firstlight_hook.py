#!/usr/bin/env python3
"""
firstlight_hook.py — Claude Code UserPromptSubmit hook.

Drop-in pre-step that runs BEFORE Claude processes each prompt. It reads the
prompt, routes it against your skills library (pure Python, zero deps), and
injects a short advisory readout as additional context — so Claude starts each
turn knowing which skill the request resembles, the expected output shape, the
compute budget, and how confident the read is.

Contract (per Claude Code hooks spec):
  - input:  a JSON object on STDIN, including {"prompt": "...", "cwd": "..."}.
  - output: a JSON object on STDOUT with hookSpecificOutput.additionalContext,
            then exit 0. (Bare stdout text is unreliable for this event; the
            structured JSON envelope is the supported path.)
  - never blocks: any error -> exit 0 with no context, so a hook failure can
    never stop the user's prompt from going through. This is a read-only advisor.

Cache resolution: the hook finds its cache without assuming a working directory.
Order: $FIRSTLIGHT_CACHE env var -> a cache next to this file's install dir ->
the most recent .firstlight_cache_*.json under the install dir. If no cache is
found it exits silently (0) rather than erroring.
"""

import sys
import os
import json
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _silent_exit(context=None):
    """Emit the hook envelope (with optional context) and exit 0. Never blocks."""
    out = {}
    if context:
        out = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            }
        }
    try:
        sys.stdout.write(json.dumps(out))
    except Exception:
        pass
    sys.exit(0)


def _find_cache(cwd):
    # 1. explicit override
    env = os.environ.get("FIRSTLIGHT_CACHE")
    if env and os.path.isfile(env):
        return env
    # 2 & 3. search common roots for a built cache
    roots = [HERE, os.path.dirname(HERE), cwd or os.getcwd()]
    found = []
    for root in roots:
        if root and os.path.isdir(root):
            found += glob.glob(os.path.join(root, ".firstlight_cache_*.json"))
    if not found:
        return None
    # most recently built wins
    return max(found, key=os.path.getmtime)


def main():
    # read the hook payload from stdin
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        _silent_exit()
    prompt = (payload.get("prompt") or "").strip()
    cwd = payload.get("cwd") or os.getcwd()
    if not prompt:
        _silent_exit()

    cache_path = _find_cache(cwd)
    if not cache_path:
        _silent_exit()  # no cache built yet -> stay silent, never error

    try:
        import pure_router as PR
        import read as RD
        cache = PR.load_cache(cache_path)
        r = RD.read_prompt(cache, prompt)
    except Exception:
        _silent_exit()  # any failure -> no context, prompt proceeds untouched

    # Build a compact, plain-text advisory block. Keep it short — it's prepended
    # to every turn, so it must be cheap to read and never bossy.
    lines = ["[FirstLight — advisory routing read, not a directive]"]
    routes = r.get("routes", [])
    if routes:
        top = routes[0]
        lines.append(f"closest skill: {top['room']}  (score {top['score']:.3f}, via {top['via']})")
        if len(routes) > 1:
            alts = ", ".join(f"{x['room']} ({x['score']:.2f})" for x in routes[1:3])
            lines.append(f"alternatives: {alts}")
    g = r.get("gate")
    if g and g.get("vetoed"):
        lines.append(f"output-shape: {'/'.join(g.get('prompt_worlds') or ['?'])}; "
                     f"ruled out {g['vetoed']} categorically-mismatched skill(s)")
    d = r.get("dashboard")
    if d:
        b = d.get("compute_budget", {})
        ts = d.get("turn_shape", {})
        if b:
            lines.append(f"compute budget: {b.get('level','?')}")
        if ts:
            lines.append(f"turn shape: {ts.get('method','?')} · {ts.get('output','?')}")
        if d.get("posture"):
            lines.append(f"posture: {'; '.join(d['posture'][:2])}")
    if r.get("low_confidence"):
        lines.append(f"⚠ low confidence: {r.get('confidence_note','')} — treat as a weak hint.")
    so = r.get("second_opinion")
    if so and so.get("status") == "unconfirmed":
        lines.append("⚠ second opinion disagrees with the top route; the read is uncertain.")
    lines.append("(FirstLight suggests; you decide. It does not constrain your response.)")

    _silent_exit("\n".join(lines))


if __name__ == "__main__":
    main()
