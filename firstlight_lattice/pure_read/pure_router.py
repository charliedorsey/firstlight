#!/usr/bin/env python3
"""
pure_router.py — dependency-free live routing from a cached build.

This is the READ arm. It reproduces, in pure Python standard library, the exact
routing that semantic_lattice.SemanticLattice.route() produces with numpy +
scikit-learn — by consuming a cache that the BUILD arm wrote (build_cache.py).

Parity contract (mirrors the rsbin-codecs lesson): the pure router must return
the SAME (room, score, via) ranking as the sklearn router for the same prompt
and corpus. parity_router.py asserts this across a probe set. Scores are rounded
to 3 decimals just like the sklearn _rank(), so equality is exact at that
precision.

Routing tiers, in the same order as the original route():
  1. embed     — skipped (no embedding vectors in the base tool); kept for shape.
  2. coherence — descriptive-word vector vs the cached room-word matrix C.
                 Pure python already; this is an exact reimplementation.
  3. tfidf     — sublinear-tf + smooth-idf, L2-normalized, cosine vs cached doc
                 matrix. Faithful reimplementation of TfidfVectorizer.transform
                 + cosine_similarity.
  4. char      — char_wb 3..5-gram fallback, only for libraries <= 10 rooms.

Everything here is stdlib only: math, re, json, collections.
"""

import math
import re
import json
from collections import Counter

COHERENCE_CONFIDENCE_FLOOR = 0.12   # must match semantic_lattice's constant


# ── tokenization (must match semantic_lattice._tokens exactly) ───────────────
# _STOP in the original is a small hand list used by descriptive_words; the
# cache carries it so we stay in lockstep even if it changes upstream.
def _tokens(text, stop):
    return [w for w in re.findall(r'[a-zA-Z][a-zA-Z\-]{2,}', text.lower())
            if w not in stop and len(w) > 2]


def descriptive_words(text, stop, window=12, top_k=12):
    """Exact pure-python copy of semantic_lattice.descriptive_words."""
    toks = _tokens(text, stop)
    if len(toks) < 5:
        return []
    freq = Counter(toks)
    vocab = [w for w, c in freq.items() if c >= 1]
    co = {}
    for i, w in enumerate(toks):
        for j in range(i + 1, min(i + window, len(toks))):
            v = toks[j]
            if v == w:
                continue
            d = j - i
            co[(w, v)] = co.get((w, v), 0.0) + 1.0 / d
            co[(v, w)] = co.get((v, w), 0.0) + 1.0 / d
    strength = {}
    for w in vocab:
        partners = [co[(w, v)] for v in vocab if v != w and (w, v) in co]
        strength[w] = (sum(partners) * math.log1p(freq[w])) if partners else 0.0
    ranked = sorted(strength.items(), key=lambda x: -x[1])
    return [(w, round(s, 2)) for w, s in ranked[:top_k] if s > 0]


# ── small linear-algebra helpers (replace numpy) ─────────────────────────────
def _l2(vec):
    return math.sqrt(sum(x * x for x in vec))


def _matvec(matrix_rows, vec):
    """matrix_rows: list of row lists; returns matrix_rows @ vec."""
    return [sum(r[i] * vec[i] for i in range(len(vec))) for r in matrix_rows]


# ── tier 2: coherence ────────────────────────────────────────────────────────
def coherence_scores(prompt, cache):
    """Reproduces SemanticLattice._coherence_scores: build a normalized prompt
    word vector over the coherence vocab, project onto the normalized room-word
    matrix C (already row-normalized at build time)."""
    cidx = cache['coherence']['cidx']          # {word: col}
    C = cache['coherence']['C']                # row-normalized matrix, list[list]
    n = len(cidx)
    v = [0.0] * n
    for w, s in descriptive_words(prompt, cache['stop_words_descriptive']):
        col = cidx.get(w)
        if col is not None:
            v[col] = s
    norm = _l2(v)
    if norm == 0:
        return None
    v = [x / norm for x in v]
    return _matvec(C, v)


# ── soft coherence: a CONFIDENCE SIGNAL, not a router ────────────────────────
# Strict coherence (above) requires the prompt's *descriptive words* (co-occurrence
# derived) to overlap a room's coherence vocab — precise but it stays silent on
# most short prompts. Soft coherence instead uses plain token PRESENCE against the
# same room-word matrix, so it has an opinion far more often. We deliberately do
# NOT let it route: measurement showed it is confidently wrong on a few prompts
# where strict coherence would rather say nothing, and protecting that "rather say
# nothing" precision is the whole point.
#
# Instead it is a SECOND OPINION used only to calibrate confidence:
#   - it independently scores every room from token presence,
#   - if its top pick AGREES with the chosen route AND clears a small floor, the
#     route is "confirmed" (measured ~94% correct on agreement),
#   - if it has signal but DISAGREES, that is exactly the shaky zone -> we flag it,
#   - if it is silent, there's simply no second opinion.
SOFT_COHERENCE_FLOOR = 0.15   # tuned: fire less, mean more (see ROUTING_EXPERIMENTS.md)


def soft_coherence_scores(prompt, cache):
    """Token-presence vector projected onto the (normalized) room-word matrix.
    Same C / cidx the strict coherence tier uses; pure stdlib."""
    coh = cache.get('coherence')
    if not coh:
        return None
    cidx = coh['cidx']
    C = coh['C']
    n = len(cidx)
    v = [0.0] * n
    seen = False
    for w in re.findall(r'[a-zA-Z][a-zA-Z\-]{2,}', prompt.lower()):
        col = cidx.get(w)
        if col is not None:
            v[col] = 1.0
            seen = True
    if not seen:
        return None
    norm = _l2(v)
    if norm == 0:
        return None
    v = [x / norm for x in v]
    return _matvec(C, v)


def confidence_signal(prompt, cache, chosen_room):
    """Return a dict describing the soft-coherence second opinion on `chosen_room`.
      status: 'confirmed' | 'unconfirmed' | 'no_second_opinion'
    'confirmed'   -> soft-coherence's own top pick == chosen_room, above floor.
    'unconfirmed' -> soft-coherence has signal but prefers a DIFFERENT room
                     (the shaky zone — surface this, don't hide it).
    'no_second_opinion' -> soft-coherence stayed silent (no token overlap)."""
    scores = soft_coherence_scores(prompt, cache)
    names = cache['names']
    if scores is None or max(scores) <= 0:
        return {'status': 'no_second_opinion', 'soft_top': None, 'soft_score': 0.0}
    si = max(range(len(scores)), key=lambda i: scores[i])
    soft_top = names[si]
    soft_at_chosen = scores[names.index(chosen_room)] if chosen_room in names else 0.0
    if soft_top == chosen_room and scores[si] >= SOFT_COHERENCE_FLOOR:
        return {'status': 'confirmed', 'soft_top': soft_top,
                'soft_score': round(float(scores[si]), 3)}
    if scores[si] >= SOFT_COHERENCE_FLOOR:
        return {'status': 'unconfirmed', 'soft_top': soft_top,
                'soft_score': round(float(scores[si]), 3),
                'soft_at_chosen': round(float(soft_at_chosen), 3)}
    return {'status': 'no_second_opinion', 'soft_top': soft_top,
            'soft_score': round(float(scores[si]), 3)}


# ── tier 3: word tf-idf (faithful TfidfVectorizer.transform + cosine) ────────
def _tfidf_word_tokens(text):
    # sklearn default word analyzer with token_pattern r'[a-z][a-z]{2,}',
    # lowercase. Stop words are removed AFTER tokenization (build-side filter
    # baked the vocabulary; here we just need tokens, OOV terms are ignored).
    return re.findall(r'[a-z][a-z]{2,}', text.lower())


def _tfidf_vector(tokens, vocab, idf, sublinear=True):
    """Build the L2-normalized tf-idf row for a prompt, exactly as sklearn does:
      tf  -> (1 + ln(tf)) if sublinear else tf      [only for tf>0]
      val -> tf * idf[term]
      row -> row / ||row||_2
    OOV terms (not in vocab) are dropped, matching transform().
    Returns a {str(col): weight} sparse dict (string keys, like the cache)."""
    counts = Counter(t for t in tokens if t in vocab)
    if not counts:
        return None
    vec = {}
    for term, tf in counts.items():
        tfw = (1.0 + math.log(tf)) if sublinear else float(tf)
        vec[str(vocab[term])] = tfw * idf[vocab[term]]
    norm = math.sqrt(sum(x * x for x in vec.values()))
    if norm == 0:
        return None
    return {col: val / norm for col, val in vec.items()}


def _sparse_dot(a, b):
    """Dot product of two {str(col): weight} sparse dicts."""
    if len(a) > len(b):
        a, b = b, a
    return sum(val * b[col] for col, val in a.items() if col in b)


def tfidf_scores(prompt, cache):
    """Cosine of the prompt tf-idf row against each cached (already L2-normed)
    document row. Both rows are unit-norm, so cosine == dot product."""
    w = cache['word_tfidf']
    vocab = w['vocabulary']        # {term: col(int)}
    idf = w['idf']                 # list aligned to col
    docs = w['doc_rows']           # list of {str(col): weight} sparse unit rows
    pv = _tfidf_vector(_tfidf_word_tokens(prompt), vocab, idf, sublinear=True)
    if pv is None:
        return [0.0] * len(docs)
    return [_sparse_dot(pv, row) for row in docs]


# ── tier 4: char_wb fallback (only for tiny libraries) ───────────────────────
def _char_wb_ngrams(text, nmin=3, nmax=5):
    """Reproduce sklearn analyzer='char_wb': pad each whitespace-split word with
    a single leading/trailing space, then take char n-grams within each padded
    word (n-grams never cross word boundaries)."""
    out = []
    for word in text.lower().split():
        padded = ' ' + word + ' '
        L = len(padded)
        for n in range(nmin, nmax + 1):
            if L < n:
                continue
            for i in range(L - n + 1):
                out.append(padded[i:i + n])
    return out


def char_scores(prompt, cache):
    c = cache.get('char_tfidf')
    if not c:
        return [0.0] * len(cache['names'])
    vocab = c['vocabulary']
    idf = c['idf']
    docs = c['doc_rows']
    # char_wb tf-idf uses the SAME sublinear setting as configured (default False
    # for char_vec in the original — it passes no sublinear_tf, so plain tf).
    counts = Counter(g for g in _char_wb_ngrams(prompt) if g in vocab)
    if not counts:
        return [0.0] * len(docs)
    vec = {}
    for g, tf in counts.items():
        vec[str(vocab[g])] = float(tf) * idf[vocab[g]]
    norm = math.sqrt(sum(x * x for x in vec.values()))
    if norm == 0:
        return [0.0] * len(docs)
    vec = {col: val / norm for col, val in vec.items()}
    return [_sparse_dot(vec, row) for row in docs]


# ── tier 1: embeddings (OPTIONAL, highest precision) ─────────────────────────
# Activated only when BOTH are true:
#   1. the cache carries per-skill embedding vectors (build arm computed them),
#   2. an embedding provider is supplied to embed the live prompt.
# The cosine itself is pure stdlib; only obtaining the prompt vector touches a
# provider (an API client or a local model). This keeps the DEFAULT install pure
# and free — embeddings are an opt-in upgrade that fills the synonym/paraphrase
# gap neither lexical tier can cross (e.g. "optimize sql query" -> query-optimizer
# even with no shared words). See docs/EMBEDDINGS.md.
def _dense_cosine(pvec, doc_vecs):
    pn = _l2(pvec)
    if pn == 0:
        return [0.0] * len(doc_vecs)
    pv = [x / pn for x in pvec]
    out = []
    for d in doc_vecs:
        # doc vectors are stored already L2-normalized by the build arm
        out.append(sum(pv[i] * d[i] for i in range(len(pv))))
    return out


def embed_scores(prompt, cache, provider):
    """provider: callable(text)->list[float], or None. Returns per-skill cosine
    scores (one float per skill in cache['names']), or None if embeddings
    aren't available/usable.

    Handles two cache formats:
      - chunked (embed_chunked=True): multiple vectors per skill, max-pool.
        The best-matching chunk determines a skill's score, so tail-end
        sections (output specs, verification steps) contribute even though
        ternlight's 128-token window can't see the whole skill at once.
      - flat (embed_chunked=False or absent): one vector per skill, direct cosine.
    """
    emb = cache.get('embed_vectors')
    if not emb or provider is None:
        return None
    try:
        pvec = provider(prompt)
    except Exception:
        return None
    if not pvec or len(pvec) != cache.get('embed_dim', len(pvec)):
        return None

    if cache.get('embed_chunked'):
        skill_map = cache.get('embed_skill_map', [])
        n_skills = len(cache['names'])
        cosines = _dense_cosine(pvec, emb)
        scores = [float('-inf')] * n_skills
        for ci, cos in enumerate(cosines):
            si = skill_map[ci]
            if cos > scores[si]:
                scores[si] = cos
        return scores

    return _dense_cosine(pvec, emb)


EMBED_CONFIDENCE_FLOOR = 0.25   # cosine floor; below this, defer to lexical tiers


# ── ranking + route (mirror semantic_lattice.route / _rank) ──────────────────
def _rank(scores, names, k, via):
    # Replicate numpy: np.argsort(scores)[::-1][:k].
    # argsort is stable-ascending (ties keep ascending index), then reversed,
    # so among equal scores the HIGHER index comes first. Achieve that by
    # sorting on (score, index) ascending and reversing.
    order_asc = sorted(range(len(scores)), key=lambda i: (scores[i], i))
    order = order_asc[::-1][:k]
    ranked = [(names[i], round(float(scores[i]), 3), via) for i in order]
    # Drop masked-out (-inf) survivors so two-stage routing never shows a vetoed
    # skill. If everything was masked the caller handles the empty case.
    return [r for r in ranked if r[1] != float('-inf') and r[1] > float('-inf')]


def route(prompt, cache, k=3, embed_provider=None, candidates=None):
    """Same tier order and thresholds as SemanticLattice.route(), with the
    optional embedding tier first (active only if cache has vectors AND a
    provider is given). Lexical tiers are unchanged and remain the default.

    candidates: optional set/list of room names to restrict scoring to (STAGE TWO
    of two-stage routing — the survivors of the deliverable gate). When given,
    non-candidate rooms are masked out before ranking, so a categorically-wrong
    skill can never win even if its words happen to match. None = score all."""
    names = cache['names']
    allow = None if candidates is None else set(candidates)

    def _masked(scores):
        if allow is None:
            return scores
        return [s if names[i] in allow else float('-inf') for i, s in enumerate(scores)]

    # tier 1 embed (optional, highest precision):
    es = embed_scores(prompt, cache, embed_provider)
    if es is not None:
        em = _masked(es)
        if max(em) >= EMBED_CONFIDENCE_FLOOR:
            return _rank(em, names, k, 'embed')
    # tier 2 coherence:
    cs = coherence_scores(prompt, cache)
    if cs is not None:
        cm = _masked(cs)
        if max(cm) >= COHERENCE_CONFIDENCE_FLOOR:
            return _rank(cm, names, k, 'coherence')
    # tier 3 word tf-idf:
    tf = tfidf_scores(prompt, cache)
    tfm = _masked(tf)
    if max(tfm) > 0.0:
        return _rank(tfm, names, k, 'tfidf-fallback')
    # tier 4 char fallback only for tiny libraries:
    if len(names) <= 10:
        return _rank(_masked(char_scores(prompt, cache)), names, k, 'char-fallback')
    return _rank(tfm, names, k, 'tfidf-fallback')


def load_cache(path):
    with open(path, 'r') as f:
        return json.load(f)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        sys.stderr.write('usage: pure_router.py <cache.json> "<prompt>"\n')
        sys.exit(2)
    cache = load_cache(sys.argv[1])
    for name, score, via in route(sys.argv[2], cache):
        print(f'  {score:.3f}  {name}  [{via}]')
