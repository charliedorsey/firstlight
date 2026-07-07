#!/usr/bin/env python3
"""
build_cache.py — the BUILD arm's serializer.

Runs the heavy (numpy + scikit-learn) SemanticLattice fit ONCE over a skills/
rooms folder and writes a pure-JSON cache that pure_router.py can route from
with zero dependencies.

It also records a corpus_fingerprint: a content hash of every routed record, so
the read arm can warn when the library has changed since this cache was built.

Usage:
    python3 build_cache.py <rooms_folder> <out_cache.json>

Cache schema (all column indices are STRING keys, because JSON object keys are
always strings — the pure router reads them as strings consistently):
    {
      "version": 1,
      "names": [room names in order],
      "corpus_fingerprint": {"<record_id>": "<sha256>", ...},
      "stop_words_descriptive": [...],          # _STOP used by descriptive_words
      "coherence": {"cidx": {word: col}, "C": [[...]]},   # row-normalized
      "word_tfidf": {
          "vocabulary": {term: col},
          "idf": [float, ...],                  # aligned to col index
          "doc_rows": [ {"<col>": weight, ...}, ... ]   # L2-normalized sparse
      },
      "char_tfidf": { ... same shape ... } | null   # only emitted if <=10 rooms
    }
"""

import sys
import os
import json
import hashlib

# import the real engine (heavy). Locate core/ via FIRSTLIGHT_CORE env var or a
# default relative guess, so this works wherever the build tree is checked out.
_core = os.environ.get('FIRSTLIGHT_CORE')
if not _core:
    # try common relative locations
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in [
        os.path.join(here, '..', '..', 'firstlight_lattice', 'core'),
        os.path.join(here, '..', 'firstlight_lattice', 'core'),
        os.path.join(here, 'firstlight_lattice', 'core'),
    ]:
        if os.path.exists(os.path.join(cand, 'semantic_lattice.py')):
            _core = cand
            break
if _core:
    sys.path.insert(0, _core)
import semantic_lattice as SL


def _sparse_rows(X, vocab_size):
    """scipy CSR matrix -> list of {str(col): weight} dicts."""
    rows = []
    Xc = X.tocsr()
    for r in range(Xc.shape[0]):
        start, end = Xc.indptr[r], Xc.indptr[r + 1]
        row = {}
        for idx in range(start, end):
            col = int(Xc.indices[idx])
            val = float(Xc.data[idx])
            row[str(col)] = val
        rows.append(row)
    return rows


def build(folder, out_path):
    rooms = dict(SL.load_rooms_canonical(folder))
    R = SL.SemanticLattice(rooms)

    # corpus fingerprint: sha256 of each record's text, keyed by name
    fingerprint = {}
    for name in R.names:
        h = hashlib.sha256(rooms[name].encode('utf-8')).hexdigest()
        fingerprint[name] = h

    # descriptive_words stop list (the small _STOP set in semantic_lattice)
    stop_desc = sorted(SL._STOP) if hasattr(SL, '_STOP') else []

    # coherence: C is already row-normalized in __init__ (self.C = C / cn)
    coherence = {
        'cidx': {w: int(i) for w, i in R.cidx.items()},
        'C': [[float(x) for x in row] for row in R.C.tolist()],
    }

    # word tf-idf
    word = {
        'vocabulary': {t: int(c) for t, c in R.vec.vocabulary_.items()},
        'idf': [float(x) for x in R.vec.idf_.tolist()],
        'doc_rows': _sparse_rows(R.X, len(R.vec.vocabulary_)),
    }

    cache = {
        'version': 1,
        'names': list(R.names),
        'rooms_folder': os.path.abspath(folder),
        'corpus_fingerprint': fingerprint,
        'stop_words_descriptive': stop_desc,
        'coherence': coherence,
        'word_tfidf': word,
        'char_tfidf': None,
        'embed_vectors': None,
        'embed_dim': None,
    }

    # char fallback only matters for tiny libraries; only then is it worth the size
    if len(R.names) <= 10:
        cache['char_tfidf'] = {
            'vocabulary': {t: int(c) for t, c in R.char_vec.vocabulary_.items()},
            'idf': [float(x) for x in R.char_vec.idf_.tolist()],
            'doc_rows': _sparse_rows(R.char_X, len(R.char_vec.vocabulary_)),
        }

    # OPTIONAL embedding tier: if an embedding provider is configured, embed each
    # skill's text and store L2-normalized vectors so the read arm can cosine
    # against them. Two paths:
    #   - ternlight (local): chunk each skill into ~100-token windows (ternlight's
    #     128-token limit means tail-end sections like output specs would be lost
    #     without chunking), batch-embed all chunks in one subprocess call, store
    #     ALL chunk vectors + a skill-index map. Read arm max-pools per skill.
    #   - API provider: one vector per skill (API providers typically have higher
    #     token limits; per-call cost makes chunking expensive).
    # Skipped silently if nothing is configured.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import embed_provider as EP
        import math

        if EP.ternlight_available():
            all_chunks = []
            skill_map = []
            for idx, n in enumerate(R.names):
                text = R.texts[R.names.index(n)]
                chunks = EP.chunk_text(text)
                for chunk in chunks:
                    all_chunks.append(chunk)
                    skill_map.append(idx)
            raw_vecs = EP.ternlight_batch(all_chunks)
            vecs = []
            for v in raw_vecs:
                nn = math.sqrt(sum(x * x for x in v)) or 1.0
                vecs.append([x / nn for x in v])
            cache['embed_vectors'] = vecs
            cache['embed_skill_map'] = skill_map
            cache['embed_dim'] = len(vecs[0]) if vecs else None
            cache['embed_chunked'] = True
            sys.stderr.write(
                f'  + embedded {len(R.names)} skills as {len(vecs)} chunks '
                f'(dim {cache["embed_dim"]}, ternlight)\n')
        else:
            provider = EP.default_provider()
            if provider is not None:
                vecs = []
                for n in R.names:
                    v = provider(R.texts[R.names.index(n)])
                    nn = math.sqrt(sum(x * x for x in v)) or 1.0
                    vecs.append([x / nn for x in v])
                cache['embed_vectors'] = vecs
                cache['embed_dim'] = len(vecs[0]) if vecs else None
                cache['embed_chunked'] = False
                sys.stderr.write(
                    f'  + embedded {len(vecs)} skills (dim {cache["embed_dim"]})\n')
    except Exception as e:
        sys.stderr.write(f'  (embedding tier skipped: {e})\n')

    # STAGE-ONE gate index: each skill's deliverable world(s) from its declared
    # purpose, precomputed so the read arm gates without re-scanning bodies.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import deliverable_gate as DG
        cache['gate_index'] = DG.build_gate_index(rooms)
    except Exception as e:
        cache['gate_index'] = None
        sys.stderr.write(f'  (gate index skipped: {e})\n')

    with open(out_path, 'w') as f:
        json.dump(cache, f)
    size = os.path.getsize(out_path)
    sys.stderr.write(
        f'built cache: {len(R.names)} records, '
        f'coherence {len(R.cidx)} dims, word-vocab {len(R.vec.vocabulary_)}, '
        f'{size // 1024}KB -> {out_path}\n')
    return cache


def compute_fingerprint(folder):
    """Cheap, dependency-free: recompute the corpus fingerprint to compare
    against a cache. Mirrors load_rooms_canonical's record set."""
    rooms = dict(SL.load_rooms_canonical(folder))
    return {name: hashlib.sha256(text.encode('utf-8')).hexdigest()
            for name, text in rooms.items()}


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.stderr.write('usage: build_cache.py <rooms_folder> <out_cache.json>\n')
        sys.exit(2)
    build(sys.argv[1], sys.argv[2])
