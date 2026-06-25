#!/usr/bin/env python3
"""
turn_dashboard.py — a turn-start workspace readout.

Runs at the top of a turn. Takes the user's prompt (and optionally a little
recent context). Prints an advisory dashboard: where the request sits in the
canonical 6-dim manifold, what the spirit-animal council reads from it, which
rooms it might fit, what response posture to lean toward, and which known
failure modes this coordinate tends to trigger.

RIGHTS DISCIPLINE (the sensor/transform/read separation):
  - SENSORS observe raw prompt-surface facts. No inference, no scoring.
  - TRANSFORMS normalize sensor facts into the 6-dim manifold + 15 crossterms.
    Calculate, never judge.
  - READS interpret the crossterms into strength-tagged SUGGESTIONS.
    A read may suggest; it may not decide.
  - The reader (the model) is the sovereign CHOICE layer. This script briefs;
    it does not route.

Everything here is advisory. A wrong suggestion costs a glance. Nothing gates.

Downstream machinery (compute_crossterms, animal_opinion, conviction count,
the animal partition) is reused verbatim from corpus/voice/audio_room.py,
which is already verified and elm_validate-clean. Only the SENSOR layer is new:
audio_room sensed documents-to-be-heard; this senses user prompts.

ELM = 2 ** (1/24)

GOVERNANCE (aligned to stream_constitution_v1, the nine laws):
  - 1st (governance primary): every output is advisory; nothing here gates or
    decides. The tool suggests; the reader is sovereign.
  - 2nd (source before inference): SENSORS read raw prompt facts before any
    dim is computed; the layers are kept strictly separate.
  - 3rd (do not freeze life): suggestions are strength-tagged ranges, never
    hard routes; the reader can always override.
  - 7th (reflexive fold is real / dangerous): this tool IS a reflexive
    instrument — the model reading its own turn-situation. That is exactly the
    "powerful and dangerous" fold, which is why...
  - 8th (governance is the membrane for self-reference): ...the advisory-only
    contract is load-bearing, not decorative. A self-reading tool that could
    DECIDE would be self-reference without a membrane. This one cannot decide.
    The 'contract' field in analyze() states this in the data itself.
  - 9th (inheritance): single-file, stdlib-only (this READ module specifically),
    --selftest for verification — so it can be handed forward and re-checked.

HONEST SCOPE: the manifold COORDINATE and the WATCH flags are the reliable,
load-bearing signals. The 5-animal council vote is advisory texture — a
2026-05 finding showed negative low-stakes/low-depth crossterms can outvote
strong structure/artifact dims, so council DIRECTION does not robustly track
work-type. Room routing keys off the coordinate, not the council vote.
"""
import sys
import re
import argparse

# ── PRECOMPILED REGEX REGISTRY ─────────────────────────────────────────────
# Patterns used in the per-call hot path, compiled ONCE at import instead of on
# every analyze(). Lifted verbatim from their call sites — functionally identical.
import re as _re
_RX = {
    'code_fence':       _re.compile(r'\bdef \b|\bclass \b|import |#include'),
    'references_file':  _re.compile(r'\.\w{1,4}\b|/mnt/|uploaded|attached|\bbundle\b|\bzip\b'),
    'bare_pronoun':     _re.compile(r'\b(build|fix|ship|do|run|make|finish|send|write) (it|this|that|them|those)\b'),
    'scope_all':        _re.compile(r'\b(all|whole|every|comprehensive|entire|from scratch)\b'),
    'verify_verb':      _re.compile(r'\b(check|verify|confirm|compute|calculate|measure|benchmark|run|test|prove)\b'),
    'count_q':          _re.compile(r'\b(how many|what is the|how much|what size|what rate|count)\b'),
    'question_help':    _re.compile(r'what should i (ask|do|focus)|right question|which (way|move)|next step'),
    'room_build':       _re.compile(r'build a room|new room|room for|make a (room|protocol)'),
    'review_verb':      _re.compile(r'\b(review|critique|feedback on|thoughts on|read my|look over|assess|evaluate this)\b'),
    'review_code_excl': _re.compile(r'review the (code|pr|pull request)'),
    'book_obj':         _re.compile(r'\b(book|manuscript|chapter|novel|memoir)\b'),
    'intent_route': _re.compile('\\b(go.?to.?market|gtm|launch|pricing|positioning|sell|sales|customer|revenue|market|commercial|opportunity|deal|founder|business model|funnel|review|critique|feedback on|thoughts on|read my|look over|assess|strategy|strategic|goal|plan|decide|decision|should i|which (path|way|option)|trade.?off|next move|future|options|prioriti|roadmap|broken|not working|fails?|failing|error|bug|crash|why does|why is|unexpected|regression|say no|decline|push back|set a boundary|explain|teach me|help me understand|eli5|prioriti|overwhelmed|what do i do first)\\b'),
    'intent_route2': _re.compile(r"i'?m stuck|help me (see|frame|figure out my|sort out)|"
        r"what'?s my (next|real) (move|step)|clarify (this|my)|frame (this|my)|"
        r"make sense of (this|my)|where do i (start|go)|build a room|new room|"
        r"room for|make a (room|protocol)"),
    'goal_lang': _re.compile('\\b(strategy|strategic|goal|plan|decide|decision|should i|which (path|way|option)|trade.?off|next move|future|options|prioriti|roadmap|how do i (get|achieve|reach)|what.?s my (play|move|angle))\\b'),
    'process_lang': _re.compile('\\b(process|processing|sit with|sitting with|hold|holding|don.?t know what to (do with|feel)|grappling|grieving|grief|carry|carrying|feeling about|feelings about|devastated|heartbroken|overwhelmed|how i feel)\\b'),
    'gtm_lang': _re.compile('\\b(go.?to.?market|gtm|launch|pricing|positioning|sell|sales|customer|revenue|market|commercial|opportunity|deal|founder|business model|funnel)\\b'),
    'lifeos_lang': _re.compile("i'?m stuck|help me (see|frame|figure out my|sort out)|what'?s my (next|real) (move|step)|clarify (this|my)|frame (this|my)|make sense of (this|my)|where do i (start|go)"),
    'debug_signal': _re.compile("\\b(broken|not working|doesn'?t work|fails?|failing|error|bug|crash|why does|why is|unexpected|should work|used to work|regression|can'?t figure out why|stack ?trace|exception|returns? (the )?wrong|isn'?t (working|returning|showing))\\b"),
    'auditory':         _re.compile(r'voice|audio|listen|spoken|read aloud|podcast|tts|hear|narrat|pdf for'),
    'continuation':     _re.compile(r'^(keep going|keep at it|keep it up|continue|carry on|'
        r'go on|go ahead|proceed|carry on|more|next|onward|and\?|go|resume|'
        r'keep going\.?|continue\.?)[.! ]*$'),
    'boundary':         _re.compile(r'say no|saying no|tell (them|him|her) no|decline|'
        r'turn (them|it|him|her) down|push back|set a boundary|hold (a|my|the) '
        r'(line|limit|boundary)|deliver bad news|hard no|let (them|him|her) down|'
        r'how do i (say|tell)'),
    'teacher':          _re.compile(r'explain|teach me|help me understand|eli5|'
        r'how does .* work|walk me through|what is a |break down (the |this )?concept|'
        r'make .* (clear|understandable)'),
    'triage':           _re.compile(r'too much (going on|to do|at once)|overwhelmed with|'
        r'what (do|should) i do first|prioriti|so many (things|tasks)|'
        r'where do i (even )?start|everything at once|juggling'),
}
# ───────────────────────────────────────────────────────────────────────────

# CANONICAL CONSTANTS — reused verbatim from audio_room.py. Do not redefine.
# The partition is elm_validate-clean: 15 pairs, each covered exactly once.
# ─────────────────────────────────────────────────────────────────────────
TRITONE = 2 ** 0.5

# The six axes, in canonical order. Names are request-space analogs of the
# chess/document dims but occupy the SAME slots, so the partition and
# crossterm machinery are unchanged.
DIM_NAMES = ['stakes', 'register', 'form', 'openness', 'urgency', 'scope']
# Six ORTHOGONAL questions, each from a DISJOINT signal set so the dims don't
# correlate (a 2026-05 measurement found the old stakes/domain pair at r=-0.93
# because both read emotional markers; structure/artifact at +0.68; etc.).
#   stakes   = how much rides on getting it right   (consequence words)
#   register = human-emotional vs neutral-technical (affect words — sole home)
#   form     = wants a made artifact vs spoken answer (build/file words)
#   openness = exploratory vs well-formed ask        (explore vs imperative)
#   urgency  = time pressure                          (now vs no-rush)
#   scope    = how big the ask is                     (length + breadth words)

SPIRIT_ANIMALS = {
    'wolf_pup':                 [(0, 1), (0, 3), (0, 4)],
    'elk':                      [(1, 2), (1, 3), (1, 5)],
    'tayra':                    [(2, 3), (2, 4), (2, 5)],
    'technicolor_highland_cow': [(3, 4), (3, 5), (4, 5)],
    'clever_raccoon':           [(0, 2), (0, 5), (1, 4)],
}


# ─────────────────────────────────────────────────────────────────────────
# TRANSFORM LAYER — reused verbatim from audio_room.py.
# Calculates pairwise interactions. Does not judge.
# ─────────────────────────────────────────────────────────────────────────
def compute_crossterms(dims):
    ct = {}
    for i in range(6):
        for j in range(i + 1, 6):
            dist = j - i
            divisor = {1: 1000, 2: 1414, 3: 2000, 4: 2828, 5: 4000}[dist]
            a, b = dims[i], dims[j]
            if abs(a) < 0.01 or abs(b) < 0.01:
                ct[(i, j)] = 0.0
            elif (a > 0) == (b > 0):
                sign = 1.0 if a > 0 else -1.0
                ct[(i, j)] = sign * abs(a) * abs(b) * 1000.0 / divisor
            else:
                ct[(i, j)] = -abs(a) * abs(b) * 1000.0 / divisor / TRITONE
    return ct


# ─────────────────────────────────────────────────────────────────────────
# READ LAYER — reused verbatim from audio_room.py.
# Each animal reads its 3 assigned crossterm pairs and emits an opinion +
# confidence. A read SUGGESTS. It does not decide.
# ─────────────────────────────────────────────────────────────────────────
def animal_opinion(pairs, crossterms):
    res = [crossterms[p] for p in pairs]
    nz = [r for r in res if abs(r) > 0.01]
    if not nz:
        return {'opinion': 0.0, 'confidence': 0.0}
    signs = [1.0 if r > 0 else -1.0 for r in nz]
    alignment = sum(signs) / len(signs)
    magnitude = sum(abs(r) for r in res)
    return {'opinion': alignment * magnitude, 'confidence': abs(alignment)}


def council_pass(dims):
    """The five animals read the crossterms.

    DIRECTIONAL conviction (the v0->v1 fix): a read carries signal whether it
    leans positive OR negative. A strongly-negative council ("this is not a
    structured/engineering thing") is high-confidence information, not "no
    signal." v0 counted only positive agreement and so collapsed "strong: not
    this kind of work" into the same 0/5 bucket as "genuinely ambiguous." They
    are opposite meanings. We now report:
      - lean_for:   animals reading positive (engineer / build / commit)
      - lean_against: animals reading negative (this isn't that kind of work)
      - ambiguous:  animals near zero (genuinely no read)
    Conviction is the size of the DOMINANT directional bloc. Feral-priest is
    5/5 in one direction (the whole council sees one thing, either way)."""
    ct = compute_crossterms(dims)
    concerns = {
        'wolf_pup':                 'safety / trust / can I commit',
        'elk':                      'material / through-line / center of gravity',
        'tayra':                    'structure / coherence / arc',
        'technicolor_highland_cow': 'space / breath / room to move',
        'clever_raccoon':           'odd crossings / novel shape',
    }
    THRESH = 0.05  # opinion magnitude above which a read counts as directional
    readings = {}
    for animal, pairs in SPIRIT_ANIMALS.items():
        op = animal_opinion(pairs, ct)
        o = op['opinion']
        lean = 'for' if o > THRESH else ('against' if o < -THRESH else 'flat')
        readings[animal] = {
            'concern': concerns[animal],
            'opinion': round(o, 3),
            'confidence': round(op['confidence'], 3),
            'lean': lean,
        }
    lean_for = sum(1 for r in readings.values() if r['lean'] == 'for')
    lean_against = sum(1 for r in readings.values() if r['lean'] == 'against')
    flat = sum(1 for r in readings.values() if r['lean'] == 'flat')
    # dominant directional bloc and its sign
    if lean_for >= lean_against:
        conviction, direction = lean_for, 'for'
    else:
        conviction, direction = lean_against, 'against'
    return {'readings': readings,
            'conviction': conviction, 'direction': direction,
            'lean_for': lean_for, 'lean_against': lean_against, 'flat': flat,
            'feral_priest': conviction == 5,
            'crossterms': ct}


# ─────────────────────────────────────────────────────────────────────────
# SENSOR LAYER — NEW. The only domain-specific code.
# Observes raw, mechanically-verifiable prompt-surface facts. No inference,
# no scoring, no "what room." Just facts about the text.
# ─────────────────────────────────────────────────────────────────────────
import os as _os

_UPLOAD_DIRS = ['/mnt/user-data/uploads', './uploads']
_HEAVY_EXT = {'.pdf', '.zip', '.csv', '.xlsx', '.json', '.tsv', '.parquet',
              '.docx', '.pptx', '.ipynb', '.sqlite', '.db', '.tar', '.gz'}

def _scan_attachments(recency_window=180.0):
    """SENSOR: mechanically inventory uploaded attachments. No inference about
    contents — but it DOES separate this-turn files from ambient history.

    The brittleness this fixes (caught in the wild): a blind listdir counts every
    file ever dropped in the uploads dir, so an 8-word directive with 73 stale
    files from earlier reads as MAXIMUM. Honest fix: cluster by recency. Files
    whose mtime is within `recency_window` of the NEWEST file are 'fresh' (this
    turn); older ones are 'ambient' history. The budget signal uses the fresh
    set; the full set is still reported so the readout can flag the gap honestly.

    The most trustworthy path is still the caller passing _attachments explicitly
    (the harness knows what's on this turn); this scan is the fallback.
    """
    found = []
    for d in _UPLOAD_DIRS:
        try:
            for name in _os.listdir(d):
                fp = _os.path.join(d, name)
                if _os.path.isfile(fp):
                    ext = _os.path.splitext(name)[1].lower()
                    try:
                        mtime = _os.path.getmtime(fp)
                    except OSError:
                        mtime = 0.0
                    found.append({'name': name,
                                  'bytes': _os.path.getsize(fp),
                                  'ext': ext,
                                  'mtime': mtime,
                                  'heavy': ext in _HEAVY_EXT})
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            continue
    # cluster by recency: fresh = within recency_window of the newest file
    if found:
        newest = max(f['mtime'] for f in found)
        fresh = [f for f in found if newest - f['mtime'] <= recency_window]
    else:
        fresh = []
    ambient_extra = len(found) - len(fresh)
    return {
        # the SIGNAL: this-turn (fresh) files only
        'count': len(fresh),
        'total_bytes': sum(f['bytes'] for f in fresh),
        'heavy_count': sum(1 for f in fresh if f['heavy']),
        'files': fresh,
        # honesty: how many files were set aside as not-this-turn
        'ambient_count': len(found),
        'ambient_ignored': ambient_extra,
        'relevance_basis': 'recency' if found else 'none',
    }


def sense_prompt(prompt, context='', _attachments=None):
    """Raw, board-verifiable facts about the prompt. No inference, no scoring.
    Signals are partitioned into DISJOINT lexicons so each dimension draws on
    its own evidence and the dims stay orthogonal."""
    p = prompt
    low = ' ' + p.lower() + ' '
    words = p.split()

    def count(lex):
        return sum(low.count(t) for t in lex)

    facts = {}
    facts['word_count'] = len(words)
    facts['has_question_mark'] = '?' in p

    # STAKES: consequence-if-wrong / reversibility / weight of the decision.
    # Deepened (was underactive, std 0.14) and kept DISJOINT from scope: stakes
    # is about how much rides on it, NOT how big it is. A tiny irreversible
    # change is high-stakes/low-scope; a big throwaway draft is low-stakes/high.
    facts['consequence'] = count(['risk', 'risky', 'important', 'careful',
        'permanent', 'irreversible', 'matters', 'serious', 'critical',
        'consequence', 'stakes', 'mistake', 'safe', 'danger', 'dangerous',
        'expensive', 'sensitive', 'production', 'breaking', "can't undo",
        'high-stakes', 'crucial', 'security', 'legal', 'medical', 'money',
        'real money', 'launch', 'live', 'commit', 'decision', 'consequential',
        # life-domain stakes (borrowed from life_os kernel _DOMAINS): relational,
        # financial, health, existential distress that carries real consequence
        # even without the words above.
        'marriage', 'divorce', 'breakup', 'falling apart', 'debt', 'fired',
        'laid off', 'diagnosis', 'dying', 'custody', 'evicted', 'bankrupt'])
    # REGISTER: affect / relational — the SOLE home of emotional signal.
    facts['affect'] = count(['sad', 'happy', 'love', 'scared', 'afraid',
        'guilt', 'guilty', 'feel', 'feeling', 'grief', 'lonely', 'hurt',
        'angry', 'worried', 'anxious', 'proud', 'ashamed', ' my mom',
        ' my dad', ' i miss', 'cry', 'heart', 'emotional',
        # life-situation distress expressed WITHOUT feeling-words (borrowed from
        # life_os _EMOTIONAL + _STATE): real distress reads neutral to a pure
        # feeling-word lexicon. "marriage falling apart" IS emotional.
        'falling apart', 'drowning', 'lost', 'overwhelmed', 'stuck',
        'can\'t cope', 'breaking down', 'hopeless', 'exhausted', 'burned out',
        'alone', 'desperate'])
    facts['first_person_emotion'] = count([' i feel', " i'm sad",
        " i'm scared", " i'm worried", ' i just', ' eating at me'])
    # FORM: wants a made artifact — build verbs + artifact nouns + file refs.
    facts['build'] = count(['build', 'make ', 'create', 'write a', 'generate',
        'draft', 'ship', 'produce', 'implement', 'code', 'script', 'module',
        'file', 'deck', 'slide', 'document', 'pdf', 'spreadsheet', 'chart'])
    facts['has_code_fence'] = '```' in p or bool(_RX['code_fence'].search(p))
    facts['references_file'] = bool(_RX['references_file'].search(low))
    # OPENNESS: exploratory / unformed vs a formed ask. DISJOINT from urgency —
    # no time-words here (those live only in urgent/deurgent). Pure "is the ask
    # formed": hedged exploration vs a crisp directive/question.
    facts['explore'] = count(['wonder', 'explore', 'what if', 'curious',
        'feel like', 'idk', 'not sure', 'i guess', 'open-ended', 'brainstorm',
        'play with', 'poke at', 'see where', 'go wherever', 'where you feel',
        'no agenda', 'follow your', 'whatever feels'])
    facts['imperative'] = count(['fix ', 'compute', 'run ', 'show me',
        'give me', 'list ', 'find ', 'add ', 'make ', 'build', 'write'])
    # URGENCY: time pressure only — net of de-urgency. The SOLE home of time.
    facts['urgent'] = count(['now', 'today', 'asap', 'urgent', 'quick',
        'right away', 'immediately', 'deadline', 'tomorrow', 'tonight',
        'hurry', 'rushed', 'time-sensitive', 'eod', 'by end of'])
    facts['deurgent'] = count(['no rush', 'not urgent', 'take your time',
        "don't have to", 'no hurry', 'whenever you', 'no deadline',
        'low priority', 'background'])
    # SCOPE: size/extent of the ask — DISJOINT from stakes (size ≠ consequence).
    # Pure magnitude words: how much surface area, not how much rides on it.
    facts['breadth'] = count(['full', 'whole', 'entire', 'everything',
        ' all ', 'complete', 'end to end', 'from scratch', 'every ',
        'across all', 'comprehensive', 'exhaustive', 'in depth', 'long',
        'multi-part', 'several', 'many'])
    facts['multipart'] = (p.count('?') + low.count(' and also')
                          + low.count('. also') + p.count('\n\n'))

    # HEAVY-OUTPUT VERBS — imply a large response regardless of prompt length.
    # This is the fix for the prompt-length fallacy: "prove X" is 2 words but
    # MAXIMUM effort. Output-demand, not input-length, drives the budget.
    facts['heavy_verbs'] = count(['prove', 'analyze', 'design', 'refactor',
        'review', 'audit', 'compare', 'plan ', 'investigate', 'derive',
        'write a report', 'write an essay', 'write a', 'summarize', 'research',
        'walk through', 'work through', 'figure out', 'rethink', 'reflect',
        'build', 'create', 'implement', 'ship'])

    # ATTACHMENTS — the other blindness. A short prompt + a big file is a big
    # task. Scan the uploads dir (mechanical fact, not inference). Attachment
    # MASS and TYPE are first-class effort drivers.
    facts['attachments'] = _attachments if _attachments is not None else _scan_attachments()

    # CLARITY SENSORS — distinct from evidence-volume. A short imperative can be
    # the CLEAREST thing ("build it", "ship it"). Clarity ≠ how many words matched.
    first_words = ' '.join(low.split()[:3])
    _cmd_verbs = ['build', 'fix', 'ship', 'make', 'run', 'write', 'create',
                  'add', 'show', 'give', 'compute', 'check', 'refactor', 'go ',
                  'do ', 'prove', 'analyze', 'explain', 'tell', 'find']
    facts['imperative_lead'] = any(first_words.strip().startswith(v.strip())
                                   for v in _cmd_verbs)
    facts['hedges'] = count(['maybe', 'perhaps', 'kind of', 'sort of', 'i guess',
        'i wonder', 'not sure', 'or maybe', 'something like', 'idk', 'i think',
        'possibly', 'might', 'i dunno', 'or something'])
    # unresolved pronoun: a bare it/this/that/them as object with no noun nearby.
    # This is the context-dependence flag — NOT a penalty. "build it" is clear
    # IF prior context established the referent; firstlight can't see that.
    facts['bare_pronoun'] = bool(_RX['bare_pronoun'].search(low))
    facts['ask_count'] = max(1, facts['imperative'] + p.count('?'))
    facts['hedge_density'] = facts['hedges'] / max(1, facts['word_count'])

    # EVIDENCE TALLY — how many distinct signals fired per dimension. This is
    # what confidence is computed from (population_read philosophy: a reading
    # backed by many corroborating signals is conserved/trustworthy; one backed
    # by a single keyword is thin/brittle). Counts, not booleans, so 3 hits > 1.
    att = facts['attachments']
    facts['evidence'] = {
        'stakes':   facts['consequence'],
        'register': facts['affect'] + facts['first_person_emotion'],
        'form':     facts['build'] + (1 if facts['has_code_fence'] else 0)
                    + (1 if facts['references_file'] else 0)
                    + (1 if facts['imperative_lead'] and facts['build'] else 0),
        'openness': facts['explore'] + facts['imperative'],
        'urgency':  facts['urgent'] + facts['deurgent'],
        'scope':    facts['breadth'] + facts['multipart']
                    + (1 if facts['word_count'] > 40 else 0),
    }

    facts['raw'] = p
    return facts


def transform_to_dims(facts):
    """TRANSFORM: normalize disjoint sensor facts into the 6 orthogonal axes,
    each clamped to [-1, 1]. Each dim draws ONLY on its own signal set
    (orthogonality verified by the --selftest correlation check)."""
    clamp = lambda x: max(-1.0, min(1.0, x))
    stakes = clamp(facts['consequence'] * 0.5 - 0.2)
    register = clamp((facts['affect'] * 0.4 + facts['first_person_emotion'] * 0.6) - 0.15)
    form = clamp(facts['build'] * 0.35
                 + (0.5 if facts['has_code_fence'] else 0.0)
                 + (0.3 if facts['references_file'] else 0.0)
                 + (0.4 if facts['imperative_lead'] and facts['build'] else 0.0) - 0.25)
    openness = clamp(facts['explore'] * 0.4 - facts['imperative'] * 0.3
                     - (0.3 if facts['has_question_mark'] and facts['explore'] == 0 else 0.0))
    urgency = clamp(facts['urgent'] * 0.4 - facts['deurgent'] * 0.5)
    scope = clamp(facts['breadth'] * 0.3
                  + min(facts['word_count'], 100) / 100 * 0.5
                  + facts['multipart'] * 0.12 - 0.25)
    return [stakes, register, form, openness, urgency, scope]


# ─────────────────────────────────────────────────────────────────────────
# CONFIDENCE — adapts donor primitives confidence.elm + population_read.elm.
# Does NOT change the dim VALUES; it annotates how much to TRUST each one.
# Philosophy (confidence.elm): don't claim more accuracy than you have — fire
# named warnings when a read is fragile. Mechanism (population_read): a reading
# is confident when many corroborating signals stand behind it; thin when it
# rests on a single keyword. Lexicon matching is brittle; this makes the
# brittleness VISIBLE instead of hiding it behind clean numbers.
# ─────────────────────────────────────────────────────────────────────────
def clarity_read(facts):
    """How CLEAR the instruction is — orthogonal to evidence-volume. A short
    imperative ('build it') is high-clarity even with little evidence; a long
    rambling prompt can be low-clarity despite many keyword hits. Returns a
    clarity score [0,1] and whether clarity is context-conditional."""
    clarity = 0.4  # neutral prior
    if facts['imperative_lead']:
        clarity += 0.35          # opens with a command verb = crisp directive
    if facts['ask_count'] <= 1:
        clarity += 0.15          # single ask, not stacked
    clarity -= facts['hedge_density'] * 4.0   # hedging erodes clarity
    if facts['word_count'] <= 8 and facts['imperative_lead']:
        clarity += 0.15          # short + imperative = maximally crisp
    clarity = max(0.0, min(1.0, clarity))
    # context-conditional: a bare pronoun directive ("build it") is clear ONLY
    # if prior context established the referent — which firstlight can't see.
    context_conditional = facts['bare_pronoun']
    return {'clarity': round(clarity, 2),
            'context_conditional': context_conditional}


def dim_confidence(dim_name, value, facts, clarity=None):
    """Confidence in [0,1] for one dimension's reading. Now a function of THREE
    things, not just evidence-volume (the v5 confounder fix):
      - EVIDENCE: how many corroborating signals fired (population_read).
      - CLARITY: how unambiguous the instruction is — a clear short directive
        is trustworthy even on thin evidence.
      - MAGNITUDE: a near-zero value can't be trusted as 'confidently neutral'.
    High clarity RESCUES a low-evidence read; ambiguity caps it regardless."""
    if clarity is None:
        clarity = clarity_read(facts)['clarity']
    ev = facts['evidence'].get(dim_name, 0)
    mag = abs(value)
    ev_conf = 1.0 - 0.55 ** max(ev, 0) if ev > 0 else 0.0
    mag_conf = min(1.0, mag * 1.5)
    base = 0.5 * ev_conf + 0.3 * mag_conf + 0.2 * clarity
    # CLARITY RESCUE: a strong value on thin evidence used to be auto-penalized.
    # Now, if clarity is high, the read is trustworthy anyway (the "build it"
    # case). Only penalize thin evidence when clarity is ALSO low.
    if mag > 0.3 and ev <= 1:
        if clarity >= 0.7:
            base = max(base, 0.55 + 0.3 * clarity)   # clear directive: trust it
        else:
            base *= 0.5                               # thin AND unclear: distrust
    return round(min(1.0, base), 2)


def confidence_label(c):
    return ('high' if c >= 0.7 else 'medium' if c >= 0.4
            else 'low' if c >= 0.2 else 'very-low')


def confidence_warnings(dims, facts, confs):
    """Named fragility warnings (the confidence.elm warning-rule pattern).
    These fire when the READ ITSELF may be untrustworthy — separate from the
    failure_flags, which are about the TASK. These are about the instrument."""
    w = []
    # thin-evidence: a strong dim value resting on a single keyword
    for name, v in zip(DIM_NAMES, dims):
        ev = facts['evidence'].get(name, 0)
        if abs(v) > 0.3 and ev <= 1:
            w.append('THIN: "%s" reads %+.2f on %d signal — single-keyword, '
                     'may be brittle; verify against the actual prompt.'
                     % (name, v, ev))
    # lexicon-miss: long prompt, everything near zero -> blind, not neutral
    if facts['word_count'] > 25 and all(abs(v) < 0.2 for v in dims):
        w.append('LEXICON-MISS: long prompt but every dim near zero — the '
                 'read may be BLIND (no keywords matched), not genuinely '
                 'neutral. Trust your own read of the prompt over this.')
    # attachment-unread: scope/budget estimated from metadata only
    if facts['attachments']['count'] > 0:
        w.append('METADATA-ONLY: attachment signals come from file '
                 'size/type, not contents — scope/budget are an upper-bound '
                 'estimate until the files are actually read.')
    # ambient files set aside as not-this-turn (the recency fix)
    ignored = facts['attachments'].get('ambient_ignored', 0)
    if ignored > 0:
        w.append('THIS-TURN ONLY: %d older file(s) in the uploads dir were set '
                 'aside as ambient history (not this turn), by recency. If a '
                 'relevant file is older, pass it explicitly or name it.' % ignored)
    return w


# ─────────────────────────────────────────────────────────────────────────
# READ → SUGGESTION mapping. Strength-tagged. Advisory only.
# ─────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────
# CROSSTERM SEMANTICS — now that the 6 dims are orthogonal (max |r|=0.28),
# each of the 15 pairwise crossterms names a REAL interaction of two
# independent axes. These are what the animals read. A crossterm fires when
# BOTH its dims are active and same-signed (reinforcing) or opposite (tension).
# ─────────────────────────────────────────────────────────────────────────
# dim index: 0 stakes  1 register  2 form  3 openness  4 urgency  5 scope
CROSSTERM_MEANING = {
    (0, 1): 'stakes×register — high-stakes AND emotional: a weighty personal moment',
    (0, 2): 'stakes×form — consequential thing to BUILD: get the artifact right',
    (0, 3): 'stakes×openness — high-stakes but unformed: dangerous to rush a decision',
    (0, 4): 'stakes×urgency — consequential AND time-pressed: the hot seat',
    (0, 5): 'stakes×scope — big consequential ask: the cathedral-stakes zone',
    (1, 2): 'register×form — emotional thing wants an artifact (rare; usually a tension)',
    (1, 3): 'register×openness — feelings + open: someone processing, not asking',
    (1, 4): 'register×urgency — emotional AND urgent: possible distress/crisis signal',
    (1, 5): 'register×scope — emotional and large: a life-sized human topic',
    (2, 3): 'form×openness — TENSION: wants a thing built but ask is unformed (clarify first)',
    (2, 4): 'form×urgency — build it fast: ship-pressure',
    (2, 5): 'form×scope — big thing to build: the over-build / cathedral risk surface',
    (3, 4): 'openness×urgency — TENSION: exploratory but rushed (do not force closure)',
    (3, 5): 'openness×scope — large open territory: real hunting, needs room',
    (4, 5): 'urgency×scope — TENSION: big ask, little time (cut scope or push back)',
}


def active_crossterms(dims, council, top_n=4):
    """Return the strongest crossterms with their plain-language meaning, so the
    council read is legible: not just 'tayra +0.3' but WHAT tayra is seeing."""
    ct = council['crossterms']
    ranked = sorted(ct.items(), key=lambda kv: -abs(kv[1]))
    out = []
    for (i, j), v in ranked[:top_n]:
        if abs(v) < 0.02:
            continue
        out.append({'pair': (DIM_NAMES[i], DIM_NAMES[j]),
                    'value': round(v, 3),
                    'meaning': CROSSTERM_MEANING[(i, j)]})
    return out


def compute_budget(dims, facts, council):
    """COMPUTE-BUDGET — how much effort the RESPONSE warrants. Advisory.

    Redesigned (v4) to fix two blindnesses:
      - PROMPT-LENGTH FALLACY: 'prove X' is 2 words but MAXIMUM effort. Effort
        is driven by OUTPUT DEMAND (heavy verbs, scope, attachments), not input
        length. word_count is demoted to a faint tiebreaker.
      - ATTACHMENT BLINDNESS: a 3-word prompt + an 80-page PDF is a big task.
        Attachment mass/type is now a first-class driver.
    Explicit user instruction ('use maximum compute' / 'keep it short') is
    sovereign and overrides this heuristic — the dashboard only suggests."""
    stakes, register, form, openness, urgency, scope = dims
    att = facts['attachments']

    # output-demand score — what the RESPONSE must contain
    score = 0.0
    drivers = []
    if facts['heavy_verbs']:
        score += min(facts['heavy_verbs'], 3) * 0.8
        drivers.append('%d heavy verb(s)' % facts['heavy_verbs'])
    if max(0, scope) > 0:
        score += scope * 1.0
        if scope > 0.2: drivers.append('scope %.1f' % scope)
    if max(0, form) > 0:
        score += form * 0.7
        if form > 0.2: drivers.append('build/form')
    if max(0, stakes) > 0:
        score += stakes * 0.6
    if max(0, openness) > 0:
        score += openness * 0.5
        if openness > 0.2: drivers.append('open-ended')
    # ATTACHMENTS — mass + heaviness. A heavy file (pdf/zip/dataset) alone
    # floors the budget at MODERATE; large mass pushes higher.
    if att['count'] > 0:
        mb = att['total_bytes'] / 1e6
        score += min(mb, 5) * 0.4              # mass contribution, capped
        score += att['heavy_count'] * 0.6      # analysis-type files
        drivers.append('%d attachment(s), %.1fMB%s'
                       % (att['count'], mb,
                          ', %d heavy' % att['heavy_count'] if att['heavy_count'] else ''))
    # faint tiebreaker only — NOT a driver
    score += min(facts['word_count'], 60) / 60 * 0.2

    # STACKING BONUS — multiple independent effort drivers compounding is what
    # separates a real big build ("whole system from scratch with all features
    # and tests") from a single heavy verb ("summarize this"). Count distinct
    # active driver families; reward breadth of demand, not just one signal.
    active_families = sum([
        facts['heavy_verbs'] > 0,
        scope > 0.2,
        form > 0.2,
        att['count'] > 0,
        bool(_RX['scope_all'].search(
                       facts['raw'].lower())),
    ])
    if active_families >= 3:
        score += 0.8
        drivers.append('%d stacked demands' % active_families)
    elif active_families == 2:
        score += 0.3

    # bounded factual: short, a question, NO attachment, NO heavy verb, low everything
    bounded_factual = (facts['has_question_mark'] and att['count'] == 0
                       and facts['heavy_verbs'] == 0 and scope < 0.0
                       and form < 0.0 and stakes < 0.2
                       and facts['word_count'] < 18)

    if bounded_factual:
        level, guide = 'MINIMAL', ('one-liner / a few sentences. Do NOT '
            'over-explain. A bounded factual ask wants a bounded answer.')
    elif score < 0.9:
        level, guide = 'LIGHT', ('a short focused answer; a paragraph or a few. '
            'One demand, no breadth — keep it tight.')
    elif score < 1.7:
        level, guide = 'MODERATE', ('real work: think it through, stay scoped. '
            'Tools/reading if the task needs it.')
    elif score < 2.6:
        level, guide = 'HEAVY', ('substantial: multi-step, read attachments '
            'fully, run tools, build/verify. Worth the compute.')
    else:
        level, guide = 'MAXIMUM', ('go all in — deep work, full tool use, read '
            'everything attached, no shortcuts. Do not under-resource this.')

    return {'level': level, 'score': round(score, 2),
            'guidance': guide, 'drivers': drivers,
            'note': 'advisory — an explicit instruction (e.g. "use maximum '
                    'compute" or "keep it short") overrides this.'}


def turn_decision(dims, facts, council):
    """The three turn-shape decisions, borrowed from the existing tools so the
    dashboard absorbs them instead of reinventing:
      - RUN vs WRITE   (from scratchpad_selector.py: shell out to verify, or
                        just answer? default WRITE, flip to RUN when
                        verification/quantitative/artifact signals pile up)
      - ARTIFACT vs INLINE (from thinking.py: produce a file deliverable, or
                        answer in chat?)
    Advisory. Strength-tagged where it helps."""
    stakes, register, form, openness, urgency, scope = dims
    low = facts['raw'].lower()

    # RUN vs WRITE — scratchpad_selector's weighted-signal model, default WRITE
    run_score = 0
    run_sigs = []
    if _RX['verify_verb'].search(low):
        run_score += 2; run_sigs.append('verification-verb')
    if _RX['count_q'].search(low):
        run_score += 2; run_sigs.append('quantitative-ask')
    if facts['has_code_fence'] or facts['references_file']:
        run_score += 2; run_sigs.append('code/file-present')
    if form > 0.2 and stakes > 0.2:
        run_score += 1; run_sigs.append('consequential-build')
    decision_run = 'RUN (shell out)' if run_score >= 3 else 'WRITE (answer directly)'

    # ARTIFACT vs INLINE — thinking.py's anti-premature-conversion default:
    # only produce a file when the ask actually wants a standalone artifact.
    if form > 0.25:
        decision_out = 'ARTIFACT (produce a file)'
    elif register > 0.2:
        decision_out = 'INLINE (relational — chat, not a file)'
    elif facts['has_question_mark'] and form < 0.0:
        decision_out = 'INLINE (answer in chat)'
    else:
        decision_out = 'INLINE (default; produce a file only if asked)'

    return {'run_vs_write': decision_run, 'run_score': run_score,
            'run_signals': run_sigs, 'artifact_vs_inline': decision_out}


def suggest_rooms(dims, facts, council):
    """Map the coordinate to strength-tagged room suggestions across the full
    23-room catalog (read from rooms/, not from memory). Advisory only.

    Key correction (v4): emotional/personal turns route to strategic_council
    (truthful read of a live reality) or just inline presence — NOT to
    human_voice_council, which is the voice-CODEC engineering room, not a
    feelings room. That was a real mis-route in earlier versions.

    Routing policy (v8) for the collection-merge rooms:
      - GTM/commercial: ONE cluster route, not 8 (firstlight can't pick the
        specific GTM room from one sentence — that's business context).
      - artifact_review (+book_review sub-branch), life_os: distinct -> routed.
      - architecture_eng_builder: FOLDED into room_builder as a co-suggestion.
      - hyper-specific project rooms: NOT routed — too narrow; a generic turn
        never cleanly triggers them. Kept in the bundle, out of the router.
    """
    stakes, register, form, openness, urgency, scope = dims
    low = facts['raw'].lower()
    s = []

    # detect whether any CONTENT/INTENT route applies — if so, this isn't a
    # "just answer" turn even when form/scope are low (a GTM or review or
    # life-clarify ask is substantive even when tersely phrased).
    intent_route = bool(_RX['intent_route'].search(low) or _RX['intent_route2'].search(low))

    # just answer — bounded factual, no attachment, NO intent route, nothing to deliberate.
    # bounded_prompt = the PROMPT itself is trivial/bounded, independent of attachments.
    bounded_prompt = (form < 0.0 and scope < 0.0 and register < 0.2
                      and openness < 0.2 and not intent_route)
    bounded = bounded_prompt and facts['attachments']['count'] == 0
    if bounded:
        s.append(('(just answer directly — no room)', 5,
                  'clear bounded question; nothing to deliberate'))

    # hunting — genuinely open, unformed exploration
    if openness > 0.2 and not bounded:
        s.append(('hunting_room', min(5, int(3 + openness * 2)),
                  'exploratory / unformed — chase the scent, do not force structure'))

    # question_asking — wants help finding the RIGHT question / next move
    if (openness > 0.1 and stakes > 0.1) or _RX['question_help'].search(low):
        s.append(('question_asking_room', 3,
                  'help find the truest question / see the live branches'))

    # REFLECTION vs STRATEGY — split (v9). These are opposite postures and were
    # wrongly conflated into one strategic_council rule. Reflection = processing
    # / presence (do NOT rush to action). Strategy = goals, branches, tactics.
    goal_lang = bool(_RX['goal_lang'].search(low))
    process_lang = bool(_RX['process_lang'].search(low))
    # GTM and life-os are MORE specific than generic strategy — let them own
    # their turns. Strategy is the fallback for goal/decision language that is
    # neither commercial nor a fast life-clarify.
    gtm_lang = bool(_RX['gtm_lang'].search(low))
    lifeos_lang = bool(_RX['lifeos_lang'].search(low))
    # triage-overwhelm ("overwhelmed with TASKS / so many things to do") is
    # task-ordering, not emotional processing — reflection yields to triage there.
    triage_overwhelm = bool(_RX['triage'].search(low))
    reflection = ((register > 0.2 and not goal_lang)
                  or (register > 0.1 and process_lang)
                  or process_lang) and not triage_overwhelm
    strategy = (goal_lang or (stakes > 0.3 and form < 0.2)) and not gtm_lang and not lifeos_lang

    if reflection:
        s.append(('reflection_room_v1', min(5, int(3 + register * 2)),
                  'processing / presence — stay with what is here, do not rush to action'))
    if strategy:
        s.append(('strategic_room_v1', min(5, int(3 + max(stakes, 0) * 2)),
                  'goals / live future branches / tactics — a decision-useful read'))
    # BOTH high: emotional AND a real decision (the truck-decision shape).
    # Reflection FIRST — you cannot strategize well from unprocessed state.
    if reflection and strategy:
        # ensure reflection outranks strategy by bumping it
        for i, (room, st, why) in enumerate(s):
            if room == 'reflection_room_v1':
                s[i] = (room, 5, why + ' (do this BEFORE strategy — presence first)')

    # debug — something exists and is WRONG; find why. Investigation, not
    # construction. Distinct from engineering_scrum (build/refactor) and
    # question_asking (find the question — debug already has it: "why broken").
    debug_signal = _RX['debug_signal'].search(low)
    if debug_signal:
        s.append(('debug_room_v1', min(5, int(3 + max(0, form))),
                  'something is broken — reproduce, find where reality diverges '
                  'from belief, fix the cause not the symptom'))

    # engineering_scrum — improve/refactor a code or room artifact (technical)
    if form > 0.2 and register < 0.2 and (facts['has_code_fence']
            or facts['references_file'] or 'refactor' in low or 'room' in low):
        s.append(('engineering_scrum_room', min(5, int(2 + form * 4)),
                  'improve/build a technical artifact, capability-preserving'))

    # artifact_builder — build a deliverable (deck, doc, pdf), more presentation
    if form > 0.2 and not facts['has_code_fence']:
        s.append(('artifact_builder_room', min(5, int(2 + form * 3)),
                  'build the right deliverable artifact for its reality level'))

    # room_builder — meta: build a new room/protocol. architecture_eng_builder
    # is FOLDED here as a co-suggestion for larger system/family builds (it
    # overlaps room_builder too much to justify a competing rule).
    if _RX['room_build'].search(low):
        s.append(('room_builder_room', 4, 'building a new room/protocol/system — '
                  'meta work; spans single room through governed system/family'))

    # GTM / commercial cluster — ONE route, not 8. firstlight can recognize
    # commercial intent but cannot tell one GTM sub-domain from another from
    # opportunity-eval from one sentence (that's business context, not surface).
    # So: suggest the cluster, naming generic_opportunity as the general entry,
    # and let the reader pick the specific room. Routing to 8 = false precision.
    if _RX['gtm_lang'].search(low):
        s.append(('generic_opportunity_room_v7  [GTM cluster]',
                  min(5, int(3 + max(0, stakes) * 2)),
                  'commercial/GTM intent — entry to the GTM cluster '
                  '(opportunity_gtm, gtm_worldview_launch, gtm_criticism, '
                  'joint_strategic_council_gtm); pick the fit. Domain instances '
                  '(domain-specific GTMs, if any, live in rooms/specialized, not routed.)'))

    # artifact_review — review/critique a made thing. Books/manuscripts are
    # reviewed here too: artifact_review absorbed the book promise/audience lens,
    # so a book is reviewed as an artifact whose promise is its reading experience.
    if _RX['review_verb'].search(low) and not _RX['review_code_excl'].search(low):
        is_book = bool(_RX['book_obj'].search(low))
        s.append(('artifact_review_room_generic', 4 if is_book else 3,
                  'structured review — judged against its own promise/audience'
                  + (' (book: promise = the reading experience)' if is_book else '')))

    # life_os — clarify a live situation fast, frame a project, state into
    # movement. Distinct from strategic_council: shorter, lower emotional weight,
    # "help me see / I'm stuck / frame this / what's my next move on X".
    if _RX['lifeos_lang'].search(low) and register < 0.4:
        s.append(('life_os_room_v1', min(5, int(3 + max(0, stakes))),
                  'clarify a live situation fast — fact vs story, the real branch, '
                  'smallest faithful next move'))

    # multipart_compression — long accumulated thread, many sub-asks. Fires on
    # genuine multi-part PROMPT structure, OR multiple attachments paired with a
    # prompt that has real heft (not a trivial bounded question that merely
    # happens to share a dir with unrelated files).
    multi_attach = (facts['attachments']['count'] >= 2
                    and (facts['multipart'] >= 1 or facts['word_count'] >= 8
                         or facts['attachments']['heavy_count'] >= 1)
                    and not bounded_prompt)
    if facts['multipart'] >= 3 or multi_attach:
        s.append(('multipart_response_compression_room', 3,
                  'many parts / accumulated context — reconstruct then compress'))

    # auditory — when the deliverable is meant to be HEARD. The canonical
    # auditory_room synthesizes the presentation pipeline + voice-polish
    # discipline + the audio_room listening engine. cow_renderer.py (in tools/)
    # renders the feral-priest arrival signal for listening PDFs.
    if _RX['auditory'].search(low):
        s.append(('auditory_room_v6_canonical', min(5, int(3 + max(0, form))),
                  'output meant for the ear — listening-optimized without '
                  'corrupting meaning; uses tools/cow_renderer.py for the '
                  'feral-priest signal. (voice_polish for ear-landing polish.)'))

    # boundary — deliver a no / hold a limit (clear + kind + undefended)
    if _RX['boundary'].search(low):
        s.append(('boundary_room_v1', 4,
                  'delivering a no / holding a limit — clear, kind, undefended; '
                  'hold the limit and the warmth at once'))

    # teacher — make X clear to THIS learner at THIS level
    if _RX['teacher'].search(low):
        s.append(('teacher_room_v1', min(5, int(3 + max(0, openness))),
                  'calibrated explanation — meet the learner, one real step, '
                  'truth over false simplicity'))

    # triage — too much at once; what actually first (multi-item ordering)
    if _RX['triage'].search(low):
        s.append(('triage_room_v1', 4,
                  'ordering under scarcity — sort by consequence not loudness, '
                  'name the cuts, one true next action'))

    if not s:
        s.append(('(no strong room signal — read the dims and choose)', 2,
                  'coordinate is mid-range; sovereign call'))
    s.sort(key=lambda x: -x[1])
    return s


# rooms that are real (not the two informational pseudo-entries)
_PSEUDO = ('(just answer', '(no strong room signal')


def route_decision(dims, facts, suggestions):
    """GATE LAYER (v11). Separates SUGGESTION from DECISION.

    suggest_rooms ranks rooms (a suggestion). This decides what actually happens:
    is a room QUEUED to run (pending model approval), or is this a just-answer
    turn? The two were conflated before — "(just answer)" competed as a peer in
    the ranked list, which conflicts with the idea of a queued, approved room run:
    if a room is approved and run, the turn was never "just answer".

    Returns a decision dict. It does NOT execute anything. needs_approval=True is
    the membrane: the routed room is QUEUED, and the model (sovereign) must
    approve running it. Advisory becomes actionable only on approval — consistent
    with the constitution's 7th/8th law (self-reference needs a governance gate).
    """
    stakes, register, form, openness, urgency, scope = dims
    low = facts['raw'].lower()

    # CONTINUATION DEFERENCE (v12): a bare "keep going" nudge carries almost no
    # new content. Reading it fresh would mis-size it (tiny prompt -> MINIMAL),
    # wrong if the prior turn was a MAXIMUM deep build. firstlight can't see prior
    # turns, so the honest move is to SUGGEST inheriting the prior turn's
    # behavioral settings rather than fabricating a fresh read.
    if _RX['continuation'].match(low.strip()) and facts['word_count'] <= 4 \
            and facts['attachments']['count'] == 0:
        return {
            'queued_room': None,
            'queued_strength': 0,
            'needs_approval': False,
            'default_action': 'defer_to_prior_turn',
            'alternatives': [],
            'rationale': ('bare continuation nudge — inherit the prior turn\'s '
                          'compute budget, queued room, and posture rather than '
                          're-reading from an almost-empty prompt'),
            'note': ('firstlight cannot see prior turns; it suggests deferring to '
                     'last turn\'s behavioral settings. If the prior turn was a '
                     'deep build, keep going at that depth — do not reset to MINIMAL.'),
        }

    real = [(r, st, w) for (r, st, w) in suggestions
            if not r.startswith(_PSEUDO)]

    # ARTIFACT-PRODUCTION default: a create-an-artifact turn queues the artifact
    # builder by default, UNLESS a more specific builder/room already leads.
    # "case dependent": a more specific match (room_builder for "build a room")
    # outranks the generic artifact route.
    wants_artifact = (form > 0.2 and not facts['has_code_fence']
                      and _RX['room_build'].search(low) is None)
    top = real[0] if real else None
    if wants_artifact and (top is None or top[1] < 4):
        if not any(r.startswith('artifact_builder') for r, _, _ in real):
            real.insert(0, ('artifact_builder_room', 4,
                            'create-artifact turn — queue artifact production by default'))
            top = real[0]

    # QUEUE BAR: a room is queued (pending approval) when the strongest real
    # suggestion is convincing enough (strength >= 3). Below that, just answer.
    QUEUE_BAR = 3
    if top and top[1] >= QUEUE_BAR:
        return {
            'queued_room': top[0],
            'queued_strength': top[1],
            'needs_approval': True,            # the membrane — never auto-runs
            'default_action': 'run_room',
            'alternatives': [r for r, _, _ in real[1:4]],
            'rationale': top[2],
            'note': ('QUEUED pending model approval. If approved and run, this '
                     'turn is a room run, not "just answer".'),
        }
    # No room cleared the bar -> this is genuinely a just-answer turn.
    return {
        'queued_room': None,
        'queued_strength': 0,
        'needs_approval': False,
        'default_action': 'just_answer',
        'alternatives': [r for r, _, _ in real[:3]],
        'rationale': ('no room cleared the queue bar; answer directly. '
                      '(weaker suggestions remain available if the read is wrong)'),
        'note': 'just-answer is the DECISION here, not a peer suggestion.',
    }


def posture_hint(dims, facts):
    """Response-posture suggestions, advisory."""
    stakes, register, form, openness, urgency, scope = dims
    hints = []
    if form > 0.2:
        hints.append('lean toward producing a FILE/artifact')
    elif facts['has_question_mark'] and form < 0:
        hints.append('lean toward an INLINE answer (no file)')
    if scope > 0.4:
        hints.append('large scope — a fuller response is warranted')
    elif scope < 0.0:
        hints.append('small scope — keep it short')
    if register > 0.2:
        hints.append('human/emotional register — warmth over machinery')
    if urgency < -0.3:
        hints.append('explicitly de-urgent — rest/no-rush is allowed')
    if openness > 0.2:
        hints.append('open/exploratory — follow the nose, do not force closure')
    return hints or ['no strong posture signal']


def failure_flags(dims, facts, council):
    """Known failure modes this COORDINATE tends to trigger. From the corpus
    pattern index. Advisory warnings, not blocks."""
    stakes, register, form, openness, urgency, scope = dims
    flags = []
    # cathedral risk: high form + high scope + low urgency = time to over-build
    if form > 0.3 and scope > 0.2 and urgency < 0.2:
        flags.append('CATHEDRAL RISK: form+scope high, no urgency — the '
                     'over-build zone. Confirm scope before building.')
    # forced-room risk: only when the council is genuinely FLAT (no read),
    # not when it strongly leans against (that's a real signal, not absence)
    if council['flat'] >= 3:
        flags.append('DO NOT FORCE A ROOM: %d/5 animals read flat — genuinely '
                     'open. Hunting or direct answer is correct, not a '
                     'manufactured fit.' % council['flat'])
    # large scope + high openness = thrash risk
    if scope > 0.4 and openness > 0.2:
        flags.append('THRASH RISK: large and unformed — easy to spiral. '
                     'Name the shape before diving.')
    # emotional register + technical reflex
    if register > 0.2:
        flags.append('REGISTER WATCH: human/emotional coordinate — resist '
                     'the swivel-to-productivity reflex; presence over output.')
    # distress signal: emotional + urgent
    if register > 0.3 and urgency > 0.3:
        flags.append('CARE SIGNAL: emotional AND urgent — slow down, this may '
                     'be distress; lead with presence, not solutions.')
    # jump-ahead risk on multipart
    if facts['multipart'] >= 3:
        flags.append('MULTIPART: %d sub-asks detected — answer what was asked, '
                     'do not self-answer clarifying questions.' % facts['multipart'])
    return flags


# ─────────────────────────────────────────────────────────────────────────
# DASHBOARD RENDER
# ─────────────────────────────────────────────────────────────────────────
def bar(v):
    """-1..1 to a 20-cell bar centered at 0."""
    n = int(round((v + 1) / 2 * 20))
    n = max(0, min(20, n))
    return '█' * n + '░' * (20 - n)


def analyze(prompt, context='', _attachments=None):
    """SINGLE SOURCE OF TRUTH. Runs the full pipeline and returns a dict.
    Both render() (human text) and the --json path consume this, so the
    human view and the machine view can never diverge. This is the seam that
    makes the dashboard composable: another tool (or a room entry-check) can
    import analyze() and read the dict without parsing formatted text."""
    facts = sense_prompt(prompt, context, _attachments)
    dims = transform_to_dims(facts)
    council = council_pass(dims)
    decision = turn_decision(dims, facts, council)
    rooms = suggest_rooms(dims, facts, council)
    decision_gate = route_decision(dims, facts, rooms)
    posture = posture_hint(dims, facts)
    flags = failure_flags(dims, facts, council)
    crossterms = active_crossterms(dims, council)
    budget = compute_budget(dims, facts, council)
    cr = clarity_read(facts)
    confs = {name: dim_confidence(name, v, facts, cr['clarity'])
             for name, v in zip(DIM_NAMES, dims)}
    conf_warnings = confidence_warnings(dims, facts, confs)
    # overall read confidence = mean confidence of the dims that are actually
    # carrying signal (|v|>0.15); if none, the read is very-low confidence.
    active = [confs[n] for n, v in zip(DIM_NAMES, dims) if abs(v) > 0.15]
    overall_conf = round(sum(active) / len(active), 2) if active else 0.1
    return {
        'prompt': prompt,
        'coordinate': dict(zip(DIM_NAMES, [round(d, 3) for d in dims])),
        'dim_confidence': confs,
        'overall_confidence': overall_conf,
        'clarity': cr['clarity'],
        'context_conditional': cr['context_conditional'],
        'confidence_warnings': conf_warnings,
        'dims': dims,
        'attachments': {k: facts['attachments'][k] for k in ('count','total_bytes','heavy_count')},
        'compute_budget': budget,
        'turn_shape': {
            'output': decision['artifact_vs_inline'],
            'method': decision['run_vs_write'],
            'run_signals': decision['run_signals'],
        },
        'council': {
            'conviction': council['conviction'],
            'direction': council['direction'],
            'lean_for': council['lean_for'],
            'lean_against': council['lean_against'],
            'flat': council['flat'],
            'feral_priest': council['feral_priest'],
            'readings': {a: {'opinion': r['opinion'], 'lean': r['lean'],
                             'concern': r['concern']}
                         for a, r in council['readings'].items()},
        },
        'active_crossterms': crossterms,
        'room_suggestions': [{'room': r, 'strength': s, 'why': w}
                             for r, s, w in rooms],
        'route_decision': decision_gate,
        'posture': posture,
        'flags': flags,
        'contract': 'advisory — sovereign choice stays with the reader; '
                    'this tool suggests, it does not decide',
    }


def render(prompt, context=''):
    """Human-readable formatter. Consumes analyze() — does not recompute."""
    a = analyze(prompt, context)
    dims = a['dims']
    council = a['council']
    decision = a['turn_shape']
    rooms = [(d['room'], d['strength'], d['why']) for d in a['room_suggestions']]
    posture = a['posture']
    flags = a['flags']

    out = []
    out.append('')
    out.append('  ┌─ TURN DASHBOARD ' + '─' * 43)
    snippet = prompt.strip().replace('\n', ' ')
    if len(snippet) > 64:
        snippet = snippet[:61] + '...'
    out.append('  │  prompt: ' + snippet)
    out.append('  │  ' + '─' * 56)
    att = a['attachments']
    if att['count']:
        out.append('  │  ATTACHMENTS: %d file(s), %.1f MB%s'
                   % (att['count'], att['total_bytes']/1e6,
                      ', %d analysis-type' % att['heavy_count'] if att['heavy_count'] else ''))
        out.append('  │  ' + '─' * 56)
    b = a['compute_budget']
    out.append('  │  COMPUTE BUDGET: %s  (effort %.2f)' % (b['level'], b['score']))
    if b['drivers']:
        out.append('  │    drivers: ' + ', '.join(b['drivers']))
    out.append('  │    ↳ ' + b['guidance'])
    out.append('  │    (' + b['note'] + ')')
    out.append('  │  ' + '─' * 56)
    out.append('  │  TURN SHAPE   (the three decisions)')
    out.append('  │    output : ' + decision['output'])
    out.append('  │    method : ' + decision['method']
               + ('  [%s]' % ', '.join(decision['run_signals']) if decision['run_signals'] else ''))
    out.append('  │  ' + '─' * 56)
    out.append('  │  MANIFOLD COORDINATE   (value · confidence)')
    confs = a['dim_confidence']
    for name, v in zip(DIM_NAMES, dims):
        c = confs[name]
        out.append('  │    %-9s %s  %+.2f  conf %.2f %s'
                   % (name, bar(v), v, c, confidence_label(c)))
    out.append('  │    overall read confidence: %.2f (%s)   clarity: %.2f'
               % (a['overall_confidence'], confidence_label(a['overall_confidence']),
                  a['clarity']))
    if a['context_conditional']:
        out.append('  │    ⓘ clear directive, but refers to prior context '
                   '("it"/"this") —')
        out.append('  │      confidence ASSUMES that prior context is clear.')
    out.append('  │  ' + '─' * 56)
    dirword = {'for': 'LEAN-IN', 'against': 'NOT-THIS-KIND'}[council['direction']]
    out.append('  │  COUNCIL READ   (%d/5 %s%s)'
               % (council['conviction'], dirword,
                  '  ★ FERAL PRIEST' if council['feral_priest'] else ''))
    out.append('  │    for:%d  against:%d  flat:%d'
               % (council['lean_for'], council['lean_against'], council['flat']))
    leanmark = {'for': '↑', 'against': '↓', 'flat': '·'}
    for animal, r in council['readings'].items():
        out.append('  │    %s %-26s op=%+.2f'
                   % (leanmark[r['lean']], animal, r['opinion']))
    if a['active_crossterms']:
        out.append('  │  ' + '─' * 56)
        out.append('  │  WHAT THE COUNCIL IS READING  (top interactions)')
        for c in a['active_crossterms']:
            out.append('  │    %+.2f  %s' % (c['value'], c['meaning']))
    out.append('  │  ' + '─' * 56)
    out.append('  │  ROOM SUGGESTIONS  (advisory — you choose)')
    oc = a['overall_confidence']
    octag = confidence_label(oc)
    for room, strength, why in rooms:
        out.append('  │    %d/5  %s   (read conf: %s)' % (strength, room, octag))
        out.append('  │         ↳ %s' % why)
    g = a['route_decision']
    out.append('  │  ' + '─' * 56)
    out.append('  │  ROUTE DECISION  (gate — model approves)')
    if g['queued_room']:
        out.append('  │    ▸ QUEUED: %s  [%d/5]' % (g['queued_room'], g['queued_strength']))
        out.append('  │      needs model approval to run — not auto-run')
        out.append('  │      if approved & run → this is a room run, not "just answer"')
    elif g['default_action'] == 'defer_to_prior_turn':
        out.append('  │    ▸ DEFER TO PRIOR TURN  (continuation nudge)')
        out.append('  │      inherit last turn\'s budget, room, and posture')
        out.append('  │      do NOT reset to MINIMAL just because the prompt is short')
    else:
        out.append('  │    ▸ JUST ANSWER  (no room cleared the queue bar)')
        out.append('  │      %s' % g['rationale'])
    out.append('  │  ' + '─' * 56)
    out.append('  │  POSTURE')
    for h in posture:
        out.append('  │    · ' + h)
    if flags:
        out.append('  │  ' + '─' * 56)
        out.append('  │  ⚠ WATCH')
        for f in flags:
            words = f.split()
            line = '    '
            for w in words:
                if len(line) + len(w) > 54:
                    out.append('  │  ' + line)
                    line = '      ' + w + ' '
                else:
                    line += w + ' '
            out.append('  │  ' + line.rstrip())
    if a['confidence_warnings']:
        out.append('  │  ' + '─' * 56)
        out.append('  │  ⚠ CONFIDENCE WATCH  (the read itself may be fragile)')
        for f in a['confidence_warnings']:
            words = f.split()
            line = '    '
            for wd in words:
                if len(line) + len(wd) > 54:
                    out.append('  │  ' + line); line = '      ' + wd + ' '
                else:
                    line += wd + ' '
            out.append('  │  ' + line.rstrip())
    out.append('  │  ' + '─' * 56)
    out.append('  │  SIBLINGS  (run these directly — this tool does not call them)')
    out.append('  │    · reader_state.py     — read your own state on the convo')
    out.append('  │    · session_tracker.py  — runtime/workspace self-check')
    out.append('  │    · dispatcher.py        — canonical router (this supersedes it)')
    out.append('  └' + '─' * 60)
    out.append('  (advisory readout — sovereign choice stays with the reader)')
    out.append('')
    return '\n'.join(out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='turn-start workspace dashboard')
    ap.add_argument('prompt', nargs='?', help='prompt text (or pipe via stdin)')
    ap.add_argument('--context', default='', help='optional recent context')
    ap.add_argument('--json', action='store_true',
                    help='emit machine-readable JSON (for tool/room chaining)')
    ap.add_argument('--selftest', action='store_true',
                    help='run the built-in discrimination self-test and exit')
    args = ap.parse_args()

    if args.selftest:
        # SELFTEST has three invariants now:
        #  (1) ORTHOGONALITY — the six dims must be independent (max |r| < 0.5).
        #      This is the load-bearing 2026-05 fix; if dims re-correlate, the
        #      crossterms are reading redundancy and the council is noise.
        #  (2) ROUTING — contrasting prompts route to the right room.
        #  (3) BUDGET — a bounded factual gets MINIMAL; a big build gets HEAVY+.
        #  plus the partition cover check.
        ok = True
        # (1) orthogonality
        probes = [
            'Build a Python module with tests for the spectral theory.',
            'What is the capital of Montana?',
            'I am sad about my truck and my mom who died.',
            'I wonder if we could explore something new, idk, maybe.',
            'Should I rewrite this module or patch it? Which is the better risk?',
            'Fix the bug in this code right now, it is urgent.',
            'Help me think through whether to send this hard email.',
            'Write a long comprehensive plan for my whole startup.',
            'Tell me a joke.', 'Explain how photosynthesis works.',
            'Make me a slide deck for the board meeting tomorrow.',
            'Ship the entire bundle from scratch and name it.',
            'This is a high-stakes irreversible production change, be careful.',
            'No rush, whenever you get to it, low priority background thing.',
            'prove the theorem and write the full derivation', 'Build it.',
        ]
        try:
            import numpy as _np
            M = _np.array([transform_to_dims(sense_prompt(p)) for p in probes])
            C = _np.corrcoef(M.T)
            maxoff = max(abs(C[i][j]) for i in range(6) for j in range(6) if i != j)
            orth_ok = maxoff < 0.45
            ok = ok and orth_ok
            print('  orthogonality: max |r| = %.2f  %s'
                  % (maxoff, 'OK (<0.45 on small sample; ~0.25 at scale)'
                     if orth_ok else '<-- DIMS CORRELATED'))
            # RICHNESS FLOOR: every dim must actually fire across varied prompts.
            # Guards the OTHER side of the tradeoff — decorrelating by starving a
            # dim (driving its variance to ~0) would pass orthogonality but kill
            # the reading. Both bounds together prevent gaming one against the other.
            stds = [M[:, i].std() for i in range(6)]
            min_std = min(stds)
            rich_ok = min_std >= 0.15
            ok = ok and rich_ok
            print('  richness: min dim std = %.2f  %s'
                  % (min_std, 'OK (>=0.15)' if rich_ok else '<-- A DIM IS STARVED'))
        except ImportError:
            print('  orthogonality/richness: (numpy unavailable, skipped)')
        # (2) routing — full catalog, with the strategic_council correction
        cases = {
            'engineering': ('Refactor this module.py and add tests.',
                            'engineering_scrum_room'),
            'personal':    ('I am really sad about my truck, my mom died when '
                            'I was 17 and I am just sitting with it.',
                            'reflection_room_v1'),
            'factual':     ('What is the capital of Montana?', 'just answer'),
            'open':        ('I wonder if we could explore something new, idk.',
                            'hunting_room'),
        }
        for name, (p, expect) in cases.items():
            a = analyze(p, _attachments={'count': 0, 'total_bytes': 0, 'heavy_count': 0, 'files': []})
            top = a['room_suggestions'][0]['room'] if a['room_suggestions'] else ''
            hit = expect in top
            ok = ok and hit
            print('  route %-11s top=%-32s %s'
                  % (name, top[:32], 'OK' if hit else '<-- want ' + expect))
        # (3) budget — bounded factual MINIMAL; big build HEAVY+; AND the
        # prompt-length fallacy: a SHORT heavy-verb prompt must NOT be minimal.
        _NA={'count': 0, 'total_bytes': 0, 'heavy_count': 0, 'files': []}
        bud_factual = analyze('What is the capital of Montana?', _attachments=_NA)['compute_budget']['level']
        bud_build = analyze('Build the whole comprehensive system from scratch '
                            'with all features and tests.', _attachments=_NA)['compute_budget']['level']
        bud_short_heavy = analyze('Prove the Riemann hypothesis.', _attachments=_NA)['compute_budget']['level']
        # Honest fallacy bar: a short heavy-verb prompt must escalate ABOVE a
        # bare factual lookup (not MINIMAL). Surface features cannot distinguish
        # "prove this lemma" from "prove RH" — that needs the model's judgment,
        # which is exactly why the budget is ADVISORY. LIGHT+ is the honest pass.
        fallacy_ok = bud_short_heavy != 'MINIMAL'
        bud_ok = (bud_factual == 'MINIMAL'
                  and bud_build in ('HEAVY', 'MAXIMUM') and fallacy_ok)
        ok = ok and bud_ok
        print('  budget: factual=%s build=%s short-heavy=%s  %s'
              % (bud_factual, bud_build, bud_short_heavy,
                 'OK' if bud_ok else '<-- BUDGET WRONG'))
        # (3b) attachment-awareness: same short prompt, clean vs heavy PDF,
        # must escalate the budget (the attachment-blindness fix).
        _NA = {'count': 0, 'total_bytes': 0, 'heavy_count': 0, 'files': []}
        _PDF = {'count': 1, 'total_bytes': 8_000_000, 'heavy_count': 1,
                'files': [{'name': 'big.pdf', 'bytes': 8_000_000,
                           'ext': '.pdf', 'heavy': True}]}
        clean = analyze('Summarize this.', _attachments=_NA)['compute_budget']['level']
        withpdf = analyze('Summarize this.', _attachments=_PDF)['compute_budget']['level']
        order = ['MINIMAL', 'LIGHT', 'MODERATE', 'HEAVY', 'MAXIMUM']
        att_ok = order.index(withpdf) > order.index(clean)
        ok = ok and att_ok
        print('  attachment: "summarize this" clean=%s +8MB-pdf=%s  %s'
              % (clean, withpdf, 'OK (escalates)' if att_ok else '<-- NOT ESCALATING'))
        # (4) confidence: thin AND UNCLEAR must read low; well-corroborated must
        # read higher. Post-v6 a thin-but-CLEAR read ("build it") is rescued by
        # clarity, so the low anchor must be genuinely unclear, not just short.
        thin = analyze('hmm maybe that thing perhaps, not sure, i dunno',
                       _attachments=_NA)
        thick = analyze('Build a comprehensive system from scratch with all '
                        'features, tests, and full documentation.', _attachments=_NA)
        tc = thin['overall_confidence']
        kc = thick['overall_confidence']
        conf_ok = kc > tc + 0.2 and kc >= 0.5
        ok = ok and conf_ok
        print('  confidence: thin/unclear=%.2f thick=%.2f  %s'
              % (tc, kc, 'OK (thick>>thin)' if conf_ok else '<-- NOT DISCRIMINATING'))
        # (5) clarity rescue: a clear short directive ("build it") must read
        # HIGHER form-confidence than a rambling hedged prompt with the same
        # build keyword — clarity, not word-count, drives trust in the ask.
        clear = analyze('Build it.', _attachments=_NA)
        rambl = analyze('um maybe we could kind of look at building something, '
                        'idk, i wonder if perhaps we might want to make a thing '
                        'or something like that possibly', _attachments=_NA)
        clarity_ok = (clear['clarity'] > 0.7 and rambl['clarity'] < 0.3
                      and clear['dim_confidence']['form'] >= 0.7
                      and clear['context_conditional'] is True)
        ok = ok and clarity_ok
        print('  clarity: "build it" clarity=%.2f form_conf=%.2f ctx=%s | '
              'rambling clarity=%.2f  %s'
              % (clear['clarity'], clear['dim_confidence']['form'],
                 clear['context_conditional'], rambl['clarity'],
                 'OK' if clarity_ok else '<-- CLARITY NOT RESCUING'))
        # (6) v8 collection-merge routing: new routes fire, no-route stays out,
        # GTM is ONE cluster (not many GTM rooms), folds don't compete.
        def top(p):
            a = analyze(p, _attachments=_NA)
            return a['room_suggestions'][0]['room'] if a['room_suggestions'] else ''
        def rooms_for(p):
            a = analyze(p, _attachments=_NA)
            return [r['room'] for r in a['room_suggestions']]
        r_ok = True
        checks = [
            ('gtm',    'How should I take my service to market and price it?',
             lambda t: 'GTM cluster' in t or 'opportunity' in t),
            ('review', 'Can you review this artifact and give critique?',
             lambda t: 'artifact_review' in t),
            ('book',   'Review my manuscript and the book argument.',
             lambda t: 'artifact_review' in t),
            ('lifeos', 'I am stuck, help me frame this and find my next move',
             lambda t: 'life_os' in t),
        ]
        for name, p, pred in checks:
            t = top(p)
            hit = pred(t)
            r_ok = r_ok and hit
            print('  v8route %-8s top=%-34s %s'
                  % (name, t[:34], 'OK' if hit else '<-- want ' + name))
        # NEGATIVE: a hyper-specific project room must NOT route
        cc = rooms_for('translate these strategic values into the engine')
        no_cc = not any('chess' in r for r in cc)
        r_ok = r_ok and no_cc
        print('  v8route no-cowchess: %s' % ('OK' if no_cc else '<-- LEAKED A ROUTE'))
        # NEGATIVE: GTM must be ONE cluster suggestion, not multiple GTM rooms
        gtm_rooms = [r for r in rooms_for('go to market launch pricing strategy')
                     if 'gtm' in r.lower() or 'opportunity' in r.lower()]
        one_cluster = len(gtm_rooms) <= 1
        r_ok = r_ok and one_cluster
        print('  v8route gtm-single-cluster (%d): %s'
              % (len(gtm_rooms), 'OK' if one_cluster else '<-- FALSE PRECISION'))
        ok = ok and r_ok
        # (6b) auditory route -> canonical room; room_router retired (no route)
        a_ok = True
        aud = top('turn this into a listening-optimized pdf to hear read aloud')
        if 'auditory_room' not in aud:
            a_ok = False; print('  v9route auditory top=%s <-- want auditory_room' % aud[:30])
        else:
            print('  v9route auditory top=%-28s OK' % aud[:28])
        rr = rooms_for('route this request to the right room')
        no_router = not any('room_router' in r for r in rr)
        a_ok = a_ok and no_router
        print('  v9route room_router retired: %s' % ('OK' if no_router else '<-- LEAKED'))
        ok = ok and a_ok
        # (6c) debug route: "why is this broken" -> debug, not engineering_scrum
        d_ok = True
        dbg = rooms_for('this function is broken and returns the wrong value, '
                        'why does it fail?')
        di = next((i for i, r in enumerate(dbg) if 'debug' in r), 99)
        ei = next((i for i, r in enumerate(dbg) if 'engineering_scrum' in r), 99)
        dbg_ok = di < 99 and di <= ei
        d_ok = d_ok and dbg_ok
        print('  v10route debug@%d scrum@%d  %s'
              % (di, ei, 'OK (debug leads)' if dbg_ok else '<-- want debug to lead'))
        build = rooms_for('build a new python module with tests and a CLI')
        no_dbg = not any('debug' in r for r in build)
        d_ok = d_ok and no_dbg
        print('  v10route build-not-debug: %s' % ('OK' if no_dbg else '<-- debug leaked'))
        ok = ok and d_ok
        # (6d) route_decision gate (v11): suggestion vs decision separation
        g_ok = True
        def gate(p):
            return analyze(p, _attachments=_NA)['route_decision']
        gf = gate('What is the capital of Montana?')
        if gf['queued_room'] is not None or gf['default_action'] != 'just_answer':
            g_ok = False; print('  v11gate factual <-- should be just_answer, got', gf['default_action'])
        else:
            print('  v11gate factual -> just_answer (no queue)        OK')
        gd = gate('this function is broken, why does it fail?')
        if gd['queued_room'] is None or not gd['needs_approval']:
            g_ok = False; print('  v11gate debug <-- should queue+approve, got', gd['queued_room'])
        else:
            print('  v11gate debug -> QUEUED %s (needs approval)  OK' % gd['queued_room'][:18])
        ga = gate('create a slide deck about our q3 results')
        if ga['queued_room'] is None:
            g_ok = False; print('  v11gate artifact <-- should queue a builder, got None')
        else:
            print('  v11gate create-artifact -> QUEUED %s  OK' % ga['queued_room'][:20])
        # the conflict resolution: a queued+approved turn is NOT just_answer
        if gd['queued_room'] and gd['default_action'] == 'just_answer':
            g_ok = False; print('  v11gate CONFLICT: queued room but action=just_answer')
        # trivial prompt + unrelated attachments must NOT spuriously queue multipart
        _heavy = {'count': 10, 'total_bytes': 35000000, 'heavy_count': 6, 'files': []}
        ma = analyze('what is the capital of Montana?', _attachments=_heavy)
        spurious = any('multipart' in r['room'] for r in ma['room_suggestions'])
        if spurious:
            g_ok = False; print('  v11gate multipart-guard <-- trivial prompt queued multipart')
        else:
            print('  v11gate trivial+files -> no spurious multipart       OK')
        # but a genuine multi-part prompt + attachments SHOULD still fire multipart
        mp = analyze('summarize these and also reconcile and also flag risks',
                     _attachments=_heavy)
        if not any('multipart' in r['room'] for r in mp['room_suggestions']):
            g_ok = False; print('  v11gate multipart-real <-- real multipart did not fire')
        else:
            print('  v11gate real-multipart still fires                  OK')
        ok = ok and g_ok
        # (6e) continuation deference (v12) + attachment recency (v12)
        c_ok = True
        for nudge in ['keep going', 'continue', 'more', 'go on']:
            gc = analyze(nudge, _attachments=_NA)['route_decision']
            if gc['default_action'] != 'defer_to_prior_turn':
                c_ok = False; print('  v12cont %r <-- should defer, got %s' % (nudge, gc['default_action']))
        # a substantive "keep going AND do X" must NOT defer (has real content)
        gs = analyze('keep going and build the full module with tests',
                     _attachments=_NA)['route_decision']
        if gs['default_action'] == 'defer_to_prior_turn':
            c_ok = False; print('  v12cont substantive <-- should NOT defer')
        print('  v12 continuation deference            %s' % ('OK' if c_ok else '<-- FAIL'))
        # attachment recency: ambient_ignored surfaces; fresh count drives signal
        fake = {'count': 2, 'total_bytes': 24, 'heavy_count': 0, 'files': [],
                'ambient_ignored': 70, 'ambient_count': 72, 'relevance_basis': 'recency'}
        aw = analyze('why not just try it', _attachments=fake)
        has_ambient_warn = any('THIS-TURN ONLY' in w for w in aw['confidence_warnings'])
        if not has_ambient_warn:
            c_ok = False; print('  v12attach <-- ambient-ignored warning missing')
        else:
            print('  v12 attachment recency warning         OK')
        ok = ok and c_ok
        # (6f) sprint-3 rooms: boundary, teacher, triage + triage/reflection split
        s3_ok = True
        s3 = [
            ('boundary', 'how do i tell them no without burning the relationship',
             'boundary_room'),
            ('teacher',  'explain how does TCP work to me', 'teacher_room'),
            ('triage',   'overwhelmed with so many tasks, what do i do first',
             'triage_room'),
        ]
        for name, p, want in s3:
            t = top(p)
            if want not in t:
                s3_ok = False; print('  s3route %-9s top=%s <-- want %s' % (name, t[:28], want))
            else:
                print('  s3route %-9s top=%-26s OK' % (name, t[:26]))
        # task-overwhelm -> triage, emotional-overwhelm -> reflection (no steal)
        if 'triage' not in top('overwhelmed with tasks what first'):
            s3_ok = False; print('  s3 triage-overwhelm <-- want triage')
        if 'reflection' not in top('I feel so overwhelmed and sad about everything'):
            s3_ok = False; print('  s3 emotional-overwhelm <-- want reflection')
        print('  s3 triage/reflection overwhelm split   %s' % ('OK' if s3_ok else '<-- FAIL'))
        ok = ok and s3_ok
        # (6g) life-situation distress (borrowed life_os lexicons): distress
        # expressed WITHOUT feeling-words must still route emotionally, not just-answer.
        ls_ok = True
        for p in ['my marriage is falling apart and I do not know what to do',
                  'I am drowning in debt and overwhelmed']:
            t = top(p)
            if 'reflection' not in t and 'strategic' not in t:
                ls_ok = False; print('  lifesit %r -> %s <-- want reflection/strategic' % (p[:30], t[:24]))
        print('  life-situation distress routes (not just-answer)  %s'
              % ('OK' if ls_ok else '<-- FAIL'))
        ok = ok and ls_ok
        s_ok = True
        refl_top = top('I am just sitting with how sad I feel about all this')
        strat_top = top('What should my strategy be and which path do I pick to '
                        'hit my goal?')
        if 'reflection' not in refl_top:
            s_ok = False; print('  split reflection top=%s <-- want reflection' % refl_top[:30])
        else:
            print('  split reflection top=%-28s OK' % refl_top[:28])
        if 'strategic_room' not in strat_top:
            s_ok = False; print('  split strategy   top=%s <-- want strategic_room' % strat_top[:30])
        else:
            print('  split strategy   top=%-28s OK' % strat_top[:28])
        # both-high: emotional AND a real decision -> reflection must come BEFORE strategy
        both = rooms_for('I feel devastated about this and I have to decide '
                         'whether to take the job, which path do I choose')
        ri = next((i for i, r in enumerate(both) if 'reflection' in r), 99)
        si = next((i for i, r in enumerate(both) if 'strategic_room' in r), 99)
        order_ok = ri < si and ri < 99 and si < 99
        s_ok = s_ok and order_ok
        print('  split both-high: reflection@%d strategy@%d  %s'
              % (ri, si, 'OK (presence first)' if order_ok else '<-- WRONG ORDER'))
        ok = ok and s_ok
        # partition
        cov = [pr for v in SPIRIT_ANIMALS.values() for pr in v]
        allp = [(i, j) for i in range(6) for j in range(i + 1, 6)]
        part_ok = sorted(cov) == allp
        print('  partition valid:', part_ok)
        ok = ok and part_ok
        # (coherence) every routed room name must resolve to exactly one routable
        # file. Bare stems (engineering_scrum_room) and versioned names
        # (reflection_room_v1) both allowed, but each must resolve uniquely — this
        # catches a route pointing at a renamed/retired/missing room. Skips
        # gracefully when the rooms dir isn't found (standalone runs).
        import os as _os2, re as _re2
        here = _os2.path.dirname(_os2.path.abspath(__file__))
        rdir = None
        for cand in ('../rooms/routable', 'rooms/routable',
                     _os2.path.join(here, '../rooms/routable')):
            if _os2.path.isdir(cand):
                rdir = cand; break
        if rdir:
            files = set(f[:-4] for f in _os2.listdir(rdir) if f.endswith('.yml'))
            src_self = open(_os2.path.abspath(__file__)).read()
            routed = set(m.group(1) for m in
                         _re2.finditer(r"s\.append\(\('([a-z_0-9]+)", src_self)
                         if not m.group(1).startswith('('))
            coh_ok = True
            for r in sorted(routed):
                matches = [f for f in files if f == r or f.startswith(r + '_v')
                           or f == r]
                if len(matches) != 1:
                    # allow exact-or-unique-prefix; flag only true 0 or >1
                    pref = [f for f in files if f == r or f.startswith(r)]
                    if len(pref) != 1:
                        coh_ok = False
                        print('  coherence ROUTE %s -> %d files %s' % (r, len(pref), pref))
            print('  coherence: all %d routes resolve uniquely  %s'
                  % (len(routed), 'OK' if coh_ok else '<-- DRIFT'))
            ok = ok and coh_ok
        else:
            print('  coherence: rooms dir not found (standalone) — skipped')
        print('SELFTEST:', 'PASS' if ok else 'FAIL')
        sys.exit(0 if ok else 1)

    prompt = args.prompt if args.prompt else sys.stdin.read()
    if args.json:
        import json as _json
        a = analyze(prompt, args.context)
        a.pop('dims', None)  # drop the raw list; coordinate dict is canonical
        print(_json.dumps(a, indent=2))
    else:
        print(render(prompt, args.context))
