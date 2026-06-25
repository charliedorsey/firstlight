#!/usr/bin/env python3
"""
embed_provider.py — optional embedding source for the highest-precision route tier.

The router's embed tier needs one thing: a function that turns a prompt string
into a vector. This module defines that interface and ships ONE reference
implementation that uses only the Python standard library (urllib) to call an
HTTP embeddings API — so enabling embeddings does NOT add a heavy dependency like
torch. You bring the endpoint + key; the read path stays dependency-light.

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
import urllib.request
import urllib.error


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
    """The provider the read path uses if embeddings are enabled: env-configured
    API, or None (meaning 'no embeddings, use lexical tiers')."""
    return env_api_provider()
