#!/usr/bin/env python3
"""
semantic_lattice.py — the collapsed SEMANTIC ARM of firstlight_lattice.

Merges three modules that were one lineage (operator: "collapse hybrid_router,
seeded_semantic, residual_axes"):

  - coherence_words   → folded in verbatim (the pair-coherence subject sensor).
  - residual_axes     → folded in as `discover_axes` (scaffold-strip → SVD → named
                        SEMANTIC candidate dims; the STAGE 2a pipeline output).
  - hybrid_router     → folded in as `SemanticLattice` (the 3-tier route:
                        coherence → tf-idf fallback → embedding slot; 7/8).
  - seeded_semantic   → DROPPED. Its scaffold-strip→TF-IDF route is an earlier rung;
                        residual_axes is its evolved form (strip→SVD→dims, not just a
                        route), and its plain-TF-IDF matching is subsumed by tier 3
                        (`_tfidf_scores`) here. Nothing lost. (Provenance noted in
                        FIRSTLIGHT_DATAFLOW.md.)

Two faces, one module, one scaffold-strip lineage:
  ROUTE  — SemanticLattice.route(prompt)  → ranked rooms (the matcher)
  DIMS   — discover_axes(records)          → named semantic candidate dims (for the pool)

No regex over the live prompt for meaning: coherence/tf-idf are lexical surface, not
authored-pattern matching. grammar_seed (scaffold-strip) is build-time library work.
"""
from __future__ import annotations
import re, math, os, sys, glob
import numpy as np
from collections import Counter, defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
import grammar_seed as GS

# ============================================================================
# PART 1 — coherence sensor (folded from coherence_words.py, verbatim logic)
# ============================================================================

_STOP = set("""the a an and or but if then of to in on at for with by from as is are was were be
been being this that these those it its they them their there here what which who whom how when
where why you your yours we our i me my mine he she his her not no yes do does did done will would
can could should may might must shall have has had having get got make made use used using based
across into onto over under about above below between within without per via etc eg ie also more
most less least very much many few some any all each every both either neither such same other
than then so just only even still yet again once also like want need help please thing things way
ways one two three first second next last new old good bad big small""".split())


def _tokens(text):
    return [w for w in re.findall(r'[a-zA-Z][a-zA-Z\-]{2,}', text.lower())
            if w not in _STOP and len(w) > 2]


def descriptive_words(text, window=12, top_k=12):
    """A text's most strongly-descriptive words by pair coherence (proximity +
    co-occurrence within THIS text). Corpus-free; the coherent cluster is the subject."""
    toks = _tokens(text)
    if len(toks) < 5:
        return []
    freq = Counter(toks)
    vocab = [w for w, c in freq.items() if c >= 1]
    co = defaultdict(float)
    for i, w in enumerate(toks):
        for j in range(i + 1, min(i + window, len(toks))):
            v = toks[j]
            if v == w:
                continue
            d = j - i
            co[(w, v)] += 1.0 / d
            co[(v, w)] += 1.0 / d
    strength = {}
    for w in vocab:
        partners = [(co[(w, v)]) for v in vocab if v != w and (w, v) in co]
        if not partners:
            strength[w] = 0.0
            continue
        strength[w] = sum(partners) * math.log1p(freq[w])
    ranked = sorted(strength.items(), key=lambda x: -x[1])
    return [(w, round(s, 2)) for w, s in ranked[:top_k] if s > 0]


def descriptive_vector(text, vocab_index):
    dw = dict(descriptive_words(text, top_k=30))
    v = np.zeros(len(vocab_index))
    for w, s in dw.items():
        if w in vocab_index:
            v[vocab_index[w]] = s
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


# ============================================================================
# PART 2 — semantic candidate dims (folded from residual_axes.py)
#   scaffold-strip → SVD over residual → named orthogonal dims (STAGE 2a output)
# ============================================================================

MAX_DIMS = 6                 # council partition caps at 6 (never exceed)
TARGET_CUMULATIVE = 0.75
MARGINAL_FLOOR = 0.04


def _residual_texts(records, resolution='medium'):
    grammar = GS.build_grammar_multires(records, resolution)
    scaffold = set(grammar['scaffold'])
    residual_texts = []
    for name, text in records:
        feats = GS._features(text)
        toks = []
        for k, c in feats.items():
            if k in scaffold or k.startswith('§'):
                continue
            toks.extend([k] * int(c))
        residual_texts.append(' '.join(toks))
    return [n for n, _ in records], residual_texts, grammar


def _verdict(keep, ev, cap):
    if keep >= cap:
        return f"hit cap ({cap}); residual may support more"
    return f"{keep} real axes (evidence-floored, not forced to {cap})"


def discover_axes(records, resolution='medium', max_dims=MAX_DIMS):
    """STAGE 2a: scaffold-strip → SVD over residual → named SEMANTIC candidate dims.
    Returns named axes + per-record coords + explained-variance record (auditable)."""
    names, res_texts, grammar = _residual_texts(records, resolution)
    n = len(records)
    vec = TfidfVectorizer(lowercase=True, min_df=1, max_df=0.9,
                          token_pattern=r'[a-z][a-z0-9_]{2,}')
    X = vec.fit_transform(res_texts)
    terms = np.array(vec.get_feature_names_out())
    n_feat = X.shape[1]
    ceil = max(1, min(max_dims, n - 1, n_feat - 1))
    svd = TruncatedSVD(n_components=ceil, random_state=0)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        coords_full = svd.fit_transform(X)
    ev = np.nan_to_num(svd.explained_variance_ratio_, nan=0.0, posinf=0.0, neginf=0.0)
    keep, cum = 0, 0.0
    for i in range(ceil):
        if i >= max_dims:
            break
        if i > 0 and ev[i] < MARGINAL_FLOOR:
            break
        keep += 1
        cum += ev[i]
        if cum >= TARGET_CUMULATIVE:
            break
    keep = max(1, keep)
    axes = []
    for i in range(keep):
        comp = svd.components_[i]
        top = np.argsort(comp)[::-1][:6]
        axes.append({'index': i, 'name': '_'.join(str(t) for t in terms[top[:3]]),
                     'top_terms': [str(t) for t in terms[top]],
                     'explained_variance': round(float(ev[i]), 4)})
    coords = {names[r]: [round(float(coords_full[r][i]), 4) for i in range(keep)]
              for r in range(n)}
    return {'resolution': resolution, 'scaffold_size': grammar.get('scaffold_size', len(grammar['scaffold'])),
            'n_axes_kept': keep, 'n_axes_ceiling': ceil, 'cap': max_dims,
            'explained_variance_curve': [round(float(x), 4) for x in ev],
            'cumulative_at_kept': round(float(sum(ev[:keep])), 4),
            '_fitted': {'vec': vec, 'svd': svd, 'grammar': grammar,
                        'resolution': resolution, 'keep': keep},
            'dimensionality_verdict': _verdict(keep, ev, max_dims),
            'axes': axes, 'coords': coords}


# ============================================================================
# PART 3 — the router (folded from hybrid_router.py): 3-tier route
#   coherence (precise) → tf-idf (coverage) → embedding (slot, product env)
# ============================================================================

COHERENCE_CONFIDENCE_FLOOR = 0.12


class SemanticLattice:
    """The semantic arm's matcher. Tier 1 coherence (descriptive_words), tier 2
    TF-IDF full-surface fallback, tier 3 embedding slot (active only with vectors).
    This subsumes the old seeded_semantic plain-TF-IDF route as tier 2."""

    def __init__(self, rooms, embed_vectors=None):
        self.names = list(rooms)
        self.texts = [rooms[n] for n in self.names]
        # coherence side (preferred)
        self.room_words = {n: dict(descriptive_words(t, top_k=40)) for n, t in rooms.items()}
        cvocab = sorted({w for d in self.room_words.values() for w in d})
        self.cidx = {w: i for i, w in enumerate(cvocab)}
        C = np.zeros((len(self.names), len(cvocab)))
        for r, n in enumerate(self.names):
            for w, s in self.room_words[n].items():
                C[r, self.cidx[w]] = s
        cn = np.linalg.norm(C, axis=1, keepdims=True); cn[cn == 0] = 1
        self.C = C / cn
        # tf-idf side (fallback)
        self.vec = TfidfVectorizer(stop_words='english', sublinear_tf=True,
                                   token_pattern=r'[a-z][a-z]{2,}', min_df=1, max_df=0.9)
        self.X = self.vec.fit_transform(self.texts)
        # char n-gram fallback for tiny/BYO libraries where singular/plural or
        # debug/debugging-style morphology would otherwise score all zeros. It is only
        # used when the word-level fallback has no signal, so the bundled-library
        # settled route remains unchanged.
        self.char_vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5),
                                        lowercase=True, min_df=1)
        self.char_X = self.char_vec.fit_transform(self.texts)
        # embedding slot (drop-in; active only if vectors provided)
        self.embed = embed_vectors

    def _coherence_scores(self, prompt):
        v = np.zeros(len(self.cidx))
        for w, s in descriptive_words(prompt, top_k=40):
            if w in self.cidx:
                v[self.cidx[w]] = s
        n = np.linalg.norm(v)
        if n == 0:
            return None
        return self.C @ (v / n)

    def _tfidf_scores(self, prompt):
        return cosine_similarity(self.vec.transform([prompt]), self.X)[0]

    def _char_scores(self, prompt):
        return cosine_similarity(self.char_vec.transform([prompt]), self.char_X)[0]

    def _embed_scores(self, prompt):
        if self.embed is None:
            return None
        def vec(text):
            ws = [w for w in _tokens(text) if w in self.embed]
            if not ws:
                return None
            return np.mean([self.embed[w] for w in ws], axis=0)
        pv = vec(prompt)
        if pv is None:
            return None
        pv = pv / (np.linalg.norm(pv) or 1)
        out = np.zeros(len(self.names))
        for i, t in enumerate(self.texts):
            rv = vec(t)
            if rv is not None:
                rv = rv / (np.linalg.norm(rv) or 1)
                out[i] = float(pv @ rv)
        return out

    def route(self, prompt, k=3):
        em = self._embed_scores(prompt)
        if em is not None and em.max() > 0.1:
            return self._rank(em, k, 'embed')
        cs = self._coherence_scores(prompt)
        if cs is not None and cs.max() >= COHERENCE_CONFIDENCE_FLOOR:
            return self._rank(cs, k, 'coherence')
        tf = self._tfidf_scores(prompt)
        if float(tf.max()) > 0.0:
            return self._rank(tf, k, 'tfidf-fallback')
        # Tiny BYO libraries are especially vulnerable to morphology misses
        # (debug vs debugging, KeyError vs KeyErrors). Use char n-grams only there;
        # on the bundled/large library, all-zero word TF-IDF should stay low/no-signal
        # rather than becoming a spurious char-level match.
        if len(self.names) <= 10:
            return self._rank(self._char_scores(prompt), k, 'char-fallback')
        return self._rank(tf, k, 'tfidf-fallback')

    def _rank(self, scores, k, via):
        order = np.argsort(scores)[::-1][:k]
        return [(self.names[i], round(float(scores[i]), 3), via) for i in order]


# ============================================================================
# PART 4 — STRUCTURAL FUSION (folds combined_router's manifold concept)
#   combined_router intended semantic+structural fusion but only wired semantic.
#   prompt_manifold.py left a topic_signal STUB whose docstring says the semantic
#   backend "drops in without touching the structural manifold" — semantic_lattice
#   IS that backend. So the fusion seam was designed; this wires it.
#
#   prompt_manifold gives a STRUCTURAL read (shape axes: section_count, numbered_
#   steps, len_lines — the features that VARY across the library, CV-tested). It
#   separates rooms by SHAPE, not subject. semantic_lattice separates by SUBJECT.
#   Together = the combined_router fusion that was advertised but never wired.
#
#   THE BLEND IS AN OPERATOR FORK (WIRING_PLAN Step 1, FORK 1/2): does structural
#   RE-RANK semantic candidates (preference), or do both vote equally? Left
#   advisory here — fuse() returns BOTH reads + a near-tie structural tiebreak,
#   never a hard-blended single score. The runtime decides how much to trust it.
# ============================================================================
try:
    import prompt_manifold as PM
    _HAVE_STRUCTURAL = True
except Exception:
    _HAVE_STRUCTURAL = False


SUPPORTED_LIBRARY_EXTS = ('.md', '.txt', '.yml', '.yaml', '.json')


def _record_name(path, root):
    """Stable record id for a library file. Uses relative path so recursive BYO
    libraries can contain duplicate basenames without collisions."""
    rel = os.path.relpath(path, root)
    stem = os.path.splitext(rel)[0]
    return stem.replace(os.sep, '__')


def load_rooms_canonical(rooms_folder):
    """THE canonical loader — one corpus for both arms.

    Bundled rooms are .yml/.yaml, but BYO prompt libraries often arrive as markdown or
    text files (for example attic/exampleprompts). Support .md/.txt/.json as prompt
    records too, recurse through subfolders, exclude ROOM_CONTRACT.md and macOS/hidden
    files, and keep stable sorted order. Both semantic and structural/move arms build
    over THIS exact record set, so axes/norms are derived over one corpus.

    SKILLS-AWARE MODE: an Agent Skill is a directory `skill-name/SKILL.md` with optional
    `scripts/`, `references/`, `assets/` subdirs that the agent loads ONLY on demand. The
    skill's identity is its SKILL.md; the reference/asset files are NOT separate prompts.
    So if a `SKILL.md` is present anywhere under the library, switch to skills mode: take
    exactly one record per skill directory (its SKILL.md), and ignore everything under
    scripts/ references/ assets/. This prevents a skill's REFERENCE.md from competing with
    the skill itself as a routing target. A library with no SKILL.md uses the generic
    rule below (every supported file is a prompt), preserving BYO-prompt behavior.
    """
    rooms_folder = os.path.abspath(rooms_folder)
    all_paths = sorted(glob.glob(os.path.join(rooms_folder, '**', '*'), recursive=True))

    def _usable(path):
        if not os.path.isfile(path):
            return False
        b = os.path.basename(path)
        if b.startswith('.') or b.startswith('._') or b == 'ROOM_CONTRACT.md':
            return False
        if '__MACOSX' in path.split(os.sep):
            return False
        return path.lower().endswith(SUPPORTED_LIBRARY_EXTS)

    skill_files = [p for p in all_paths
                   if os.path.basename(p).lower() == 'skill.md' and _usable(p)]

    out = []
    if skill_files:
        # Skills mode: one record per SKILL.md; reference/asset/script files ignored.
        for path in skill_files:
            out.append((_record_name(path, rooms_folder),
                        open(path, encoding='utf-8', errors='replace').read()))
    else:
        # Generic BYO-prompt mode: every supported file is its own prompt record.
        for path in all_paths:
            if _usable(path):
                out.append((_record_name(path, rooms_folder),
                            open(path, encoding='utf-8', errors='replace').read()))
    if not out:
        raise ValueError(f"no supported prompt files found in {rooms_folder} "
                         f"(expected {', '.join(SUPPORTED_LIBRARY_EXTS)}; "
                         f"for skills, a {os.sep}SKILL.md per skill directory)")
    return out


class StructuralFace:
    """The structural manifold (from combined_router via prompt_manifold): shape
    axes derived per-library by the CV-variance test. Advisory character, not a
    primary matcher (shape collides across subjects — that's why semantic leads).

    Built from EXPLICIT records (the canonical loader) so it shares the semantic
    arm's corpus — no broad re-scan, no ROOM_CONTRACT contamination (Finding 6)."""

    def __init__(self, records_or_folder):
        if not _HAVE_STRUCTURAL:
            self.axes = None; return
        # accept either a records list (canonical) or a folder (back-comat → canonical-load it)
        if isinstance(records_or_folder, str):
            records = load_rooms_canonical(records_or_folder)
        else:
            records = list(records_or_folder)
        lib = PM.build_library_from_records(records)
        self.axes = lib['axes']; self.norm = lib['norm']
        self.room_coords = {r['name']: r['coord'] for r in lib['rooms']}

    def prompt_coord(self, prompt):
        if not self.axes:
            return None
        return PM.score(prompt, self.axes, self.norm)

    def axis_names(self):
        return [a['field'] for a in self.axes] if self.axes else []


MIN_ROUTE_SCORE = 0.04   # below this top semantic score, the prompt matches no room


def fuse(prompt, semantic_router, structural_face, k=3, epsilon=0.05,
         min_route_score=MIN_ROUTE_SCORE):
    """Semantic/structural FUSION (the combined_router intent, finally wired).
    Semantic LEADS (it carries the discriminating subject signal). Structural is
    advisory: it annotates each candidate's shape-coordinate and can break a
    near-tie within `epsilon` of the top semantic score. NEVER a hard-blended
    single score — both reads are returned so disagreement stays visible.

    NO-ROOM POLICY (F7): if the top semantic score is below min_route_score (or all
    scores are ~zero — e.g. "what is 2+2"), this is a NO-ROOM case. Return no_room
    and DO NOT rerank — a structural shape tiebreak over all-zero candidates is not a
    valid route, just noise. The gate runs before any rerank.

    The blend POLICY (how much structural may move things) is the operator fork;
    this returns the material to decide it, with a conservative near-tie default."""
    sem = semantic_router.route(prompt, k=max(k, 5))
    pc = structural_face.prompt_coord(prompt) if structural_face else None
    out = {'semantic_order': sem, 'structural_prompt_coord': pc,
           'structural_axes': structural_face.axis_names() if structural_face else [],
           'fused_order': sem[:k], 'rerank_applied': False, 'rerank_note': None,
           'no_room': False}
    # NO-ROOM gate — before anything else
    top = sem[0][1] if sem else 0.0
    if not sem or top < min_route_score:
        out['no_room'] = True
        out['fused_order'] = []
        out['rerank_note'] = (f'no-room: top semantic score {top:.3f} < floor '
                              f'{min_route_score} — prompt matches no room (do not rerank)')
        return out
    if not pc or len(sem) < 2:
        return out
    band = [c for c in sem if c[1] >= top - epsilon]
    if len(band) > 1:
        # near-tie: prefer the candidate whose structural shape is closest to the prompt's
        def shape_dist(name):
            rc = structural_face.room_coords.get(name)
            if not rc:
                return 9e9
            return sum((pc.get(f, 0) - rc.get(f, 0)) ** 2 for f in pc)
        reordered = sorted(band, key=lambda c: shape_dist(c[0]))
        tail = [c for c in sem if c not in band]
        fused = reordered + tail
        if [c[0] for c in fused[:k]] != [c[0] for c in sem[:k]]:
            out['fused_order'] = fused[:k]; out['rerank_applied'] = True
            out['rerank_note'] = f'structural shape broke a {len(band)}-way semantic near-tie'
        else:
            out['fused_order'] = fused[:k]
    return out
    if len(band) > 1:
        # near-tie: prefer the candidate whose structural shape is closest to the prompt's
        def shape_dist(name):
            rc = structural_face.room_coords.get(name)
            if not rc:
                return 9e9
            return sum((pc.get(f, 0) - rc.get(f, 0)) ** 2 for f in pc)
        reordered = sorted(band, key=lambda c: shape_dist(c[0]))
        tail = [c for c in sem if c not in band]
        fused = reordered + tail
        if [c[0] for c in fused[:k]] != [c[0] for c in sem[:k]]:
            out['fused_order'] = fused[:k]; out['rerank_applied'] = True
            out['rerank_note'] = f'structural shape broke a {len(band)}-way semantic near-tie'
        else:
            out['fused_order'] = fused[:k]
    return out


# Back-compat alias so existing callers (route_prompt) keep working.
HybridRouter = SemanticLattice


def selftest():
    rooms_dir = os.path.join(os.path.dirname(__file__), '..', 'rooms')
    rooms = {os.path.splitext(os.path.basename(p))[0]: open(p, encoding='utf-8', errors='replace').read()
             for p in glob.glob(os.path.join(rooms_dir, '*'))
             if p.lower().endswith(('.yml', '.yaml')) and os.path.basename(p) != 'ROOM_CONTRACT.md'}
    R = SemanticLattice(rooms)
    tests = [
        ('help me debug this KeyError exception in my python code', ['debug', 'engineering', 'scrum', 'architect', 'tools']),
        ('review my manuscript and give hard editorial criticism', ['review', 'criticism', 'book', 'manuscript', 'editor', 'textbook', 'readability']),
        ('position and launch my product to market, find the wedge', ['gtm', 'opportunity', 'launch', 'sales', 'strategic', 'competitive']),
        ('I need to ask better questions before I decide', ['question']),
        ('help me sit with a hard feeling and reflect', ['reflection', 'voice', 'human', 'emotional', 'companion', 'boundary']),
        ('write me a song about loss', ['song', 'voice', 'companion', 'writer', 'creative', 'multipart']),
        ('teach me this concept like a patient coach', ['teach', 'coach', 'question', 'life_os', 'auditory', 'instruct']),
        ('summarize this long conversation into structured notes', ['summar', 'note', 'compression', 'multipart', 'omni']),
    ]
    ok = 0; via_count = {}
    print(f"rooms {len(rooms)}  (semantic_lattice: coherence + tf-idf fallback)")
    for p, keys in tests:
        top = R.route(p, k=3)
        via = top[0][2]; via_count[via] = via_count.get(via, 0) + 1
        hit = any(any(k in nm.lower() for k in keys) for nm, *_ in top)
        ok += hit
        print(f"  [{'OK' if hit else 'XX'}] '{p[:40]:40s}' -> {top[0][0]} ({top[0][1]}, {via})")
    print(f"ROUTING: {ok}/{len(tests)}   routed via: {via_count}")
    # also exercise the DIMS face
    recs = list(rooms.items())
    dims = discover_axes(recs)
    print(f"DIMS: {dims['n_axes_kept']} semantic candidate axes ({dims['dimensionality_verdict']})")
    return ok


if __name__ == '__main__':
    selftest()
