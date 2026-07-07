#!/usr/bin/env python3
"""
embed_provider.py — optional embedding source for the highest-precision route tier.

The router's embed tier needs one thing: a function that turns a prompt string
into a vector. This module defines that interface and ships TWO providers:

  1. ternlight_provider  — local, zero-cost, zero-latency. Uses a Node subprocess
     to call @ternlight/base (WASM, 384-dim, L2-normalized). Activates automatically
     when `npm install` has been run in this directory. No env vars needed.
  2. env_api_provider    — remote, calls an OpenAI-style embeddings endpoint via
     stdlib urllib. Configured by FIRSTLIGHT_EMBED_* env vars.

Contract:
    provider(text: str) -> list[float]      # a dense embedding vector
The vector's length must match the cache's 'embed_dim' (i.e. the same model the
build arm used to embed the skills). If it can't produce a vector it should raise;
the router catches that and falls back to the lexical tiers.

Nothing here is imported by the default read path. It is only wired in when the
user opts into embeddings (see docs/EMBEDDINGS.md). The default install never
touches the network.
"""

import os
import json
import subprocess
import shutil
import urllib.request
import urllib.error

_HERE = os.path.dirname(os.path.abspath(__file__))
_BRIDGE = os.path.join(_HERE, 'ternlight_bridge.js')


# ── ternlight (local WASM embeddings, zero-config) ─────────────────────────

def ternlight_available():
    """True if node is on PATH and @ternlight/base is installed."""
    if not shutil.which('node'):
        return False
    pkg = os.path.join(_HERE, 'node_modules', '@ternlight', 'base')
    return os.path.isdir(pkg) and os.path.isfile(_BRIDGE)


def _ternlight_call(payload):
    """Send JSON to the bridge script, return parsed JSON output."""
    r = subprocess.run(
        ['node', _BRIDGE],
        input=json.dumps(payload).encode('utf-8'),
        capture_output=True,
        timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode('utf-8', errors='replace').strip())
    return json.loads(r.stdout.decode('utf-8'))


def ternlight_provider():
    """Return a provider callable that embeds a single text via ternlight,
    or None if ternlight is not installed."""
    if not ternlight_available():
        return None

    def provider(text):
        return _ternlight_call(text)

    return provider


def ternlight_batch(texts):
    """Embed multiple texts in one subprocess call (one WASM load).
    Returns list[list[float]], one vector per input text.
    Raises if ternlight is not available."""
    if not ternlight_available():
        raise RuntimeError('ternlight not available')
    return _ternlight_call(texts)


# ── chunking (for skills longer than ternlight's 128-token window) ──────────

def chunk_text(text, max_tokens=100, overlap=20):
    """Split text into overlapping chunks of ~max_tokens whitespace-delimited
    words. Overlap ensures section boundaries don't create dead zones.
    Returns at least one chunk even for short/empty texts."""
    words = text.split()
    if len(words) <= max_tokens:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_tokens, len(words))
        chunks.append(' '.join(words[start:end]))
        if end >= len(words):
            break
        start += max_tokens - overlap
    return chunks


# ── env API provider (remote, OpenAI-style) ─────────────────────────────────

def env_api_provider(
    endpoint=None,
    api_key=None,
    model=None,
    text_field='input',
    timeout=10,
):
    """Return a provider callable that POSTs {model, input: text} to an
    OpenAI-style embeddings endpoint and returns data[0].embedding.

    Reads from env by default so nothing secret is hardcoded:
        FIRSTLIGHT_EMBED_ENDPOINT   e.g. https://api.openai.com/v1/embeddings
        FIRSTLIGHT_EMBED_KEY        the bearer token
        FIRSTLIGHT_EMBED_MODEL      e.g. text-embedding-3-small

    Uses urllib only (stdlib) — no requests, no SDK, no numpy.
    """
    endpoint = endpoint or os.environ.get('FIRSTLIGHT_EMBED_ENDPOINT')
    api_key = api_key or os.environ.get('FIRSTLIGHT_EMBED_KEY')
    model = model or os.environ.get('FIRSTLIGHT_EMBED_MODEL', 'text-embedding-3-small')
    if not endpoint or not api_key:
        return None  # not configured -> router stays on lexical tiers

    def provider(text):
        body = json.dumps({'model': model, text_field: text}).encode('utf-8')
        req = urllib.request.Request(
            endpoint, data=body, method='POST',
            headers={'Content-Type': 'application/json',
                     'Authorization': f'Bearer {api_key}'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        # OpenAI-style: {"data": [{"embedding": [...]}]}
        return payload['data'][0]['embedding']

    return provider


def callable_provider(fn):
    """Wrap any user function text->list[float] as a provider. Use this to plug
    in a local model (sentence-transformers, etc.) if you accept the heavier
    dependency. The router only ever sees the callable."""
    return fn


def default_provider():
    """The provider the read path uses if embeddings are enabled.
    Priority: ternlight (local, zero-config) -> env API -> None."""
    tp = ternlight_provider()
    if tp is not None:
        return tp
    return env_api_provider()
