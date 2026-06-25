# firstlight_lattice — dimension names & meanings

Reference: the 13 candidate dimensions, their names, what defines each (the terms or
moves that load on it), and which pole is positive. The 6 used by the council are selected
from these at build time.

The understanding+naming pass for the candidate dimensions, grounded in actual SVD
loadings (the terms/moves that DEFINE each axis), confirmed against which rooms sit at
each pole. Names are LOCKED here; orientation (which pole is +) and re-keying come next.


## SEMANTIC ARM (contrasts in scaffold-stripped subject space)

| id | LOCKED NAME | + pole (defining terms) | − pole (defining terms) |
|----|-------------|--------------------------|--------------------------|
| sem[0] | **generative slime-mold ↔ linearization** | branch, proof, question, paired (branch out) | wrapped, acknowledgment, delivered-on-request (synthesize/close) |
| sem[1] | **aesthetic refinement ↔ pragmatic direction** | polish, voice, listening (craft of expression) | commercial, opportunity, launch (market decision) |
| sem[2] | **refine ↔ review** | polish, engine, eval (iterate on existing) | built, paired, builder, new (build/construct new) |
| sem[3] | **internal audience ↔ external audience** | feeling, person, situation, limit (for a person) | commercial, buyer, gtm, motion (for a market) |
| sem[4] | **what's wrong ↔ what's right** (diagnose ↔ analyze) | question, branch, launch, polish (generate forward) | cause, hunting, fix, hunt (locate the fault) |
| sem[5] | **artifact output ↔ presence** | feeling, limit, person (relational presence) | corpus, multipart, manifold, instrument (output objects) |

Notes:
- **sem[2] = refine ↔ review**:
  + pole iterates/evaluates an existing thing, − pole constructs something new. Refine-an-
  existing vs build/review-a-new. LOCKED as "refine ↔ review."
- **sem[4]** locked as "what's wrong ↔ what's right"; "diagnose ↔ analyze" kept as the
  functional gloss (− pole = diagnose the defect; + pole = open analysis).
- **sem[5]**: the + pole's "engine/polish/proof" terms alongside feeling/person did give
  pause, but the − pole is unambiguously output-objects (corpus/multipart/manifold/
  instrument), so the artifact↔presence contrast holds. LOCKED.

## STRUCTURAL ARM (surface shape, literal counts z-scored across the library)

| id | LOCKED NAME | code |
|----|-------------|------|
| str[0] | **many sections ↔ few sections** | `section_count` (number of ## headers) |
| str[1] | **step-procedural ↔ freeform** | `numbered_steps` (count of ordered step markers) |
| str[2] | **long instructions ↔ short instructions** | `len_lines` (total spec line count) |

## MOVE ARM (contrasts in the 10 cognitive moves; loadings from move-profile SVD)

| id | LOCKED NAME | + pole moves | − pole moves |
|----|-------------|--------------|--------------|
| mov[0] | **high specification & rigor ↔ loose/unfocused** | CONSTRAIN .70, EVIDENCE .43, VERIFY .38, TONE .26 | (none strong — pure rigor-density) |
| mov[1] | **constraint-bound ↔ evidence-dependent** | CONSTRAIN .62 | EVIDENCE −.54, TONE −.46, VERIFY −.27 |
| mov[2] | **strict output format ↔ freeform/abstention** | FORMAT .81, VERIFY .41 | EVIDENCE −.29, TONE −.26 |
| mov[3] | **form & voice driven ↔ evidence & verification driven** | TONE .59, FORMAT .42 | VERIFY −.56, EXEMPLAR −.29, EVIDENCE −.20 |

Notes:
- **mov[0]**: one-directional rigor-density axis (everything loads +, nothing −). "High
  specification & rigor vs loose/unfocused." LOCKED.
- **mov[3]**: resolved AWAY from the earlier "adversarial vs accepting" read — the loadings
  carry NO RESIST move, so it is not a combativeness axis. It is "form & voice driven
  (TONE+FORMAT) ↔ evidence & verification driven (VERIFY+EVIDENCE+EXEMPLAR)." LOCKED on the
  loadings. (The adversarial *feel* came from which rooms sit high, not this axis.)

## STATUS: ALL 13 LOCKED

Semantic: slime-mold↔linearization · aesthetic-refinement↔pragmatic-direction ·
refine↔review · internal↔external-audience · what's-wrong↔what's-right ·
artifact-output↔presence.
Structural: many↔few-sections · step-procedural↔freeform · long↔short-instructions.
Move: high-rigor↔loose · constraint-bound↔evidence-dependent · strict-format↔freeform ·
form&voice↔evidence&verification.



---

## ORIENTATION (valence) + RE-KEY — DONE

### Orientation rule (principled, deterministic)
Operator intent: **positive = more descriptive of the variance.** Implemented as the
**extreme-pole rule**: orient each SVD axis so its largest-|coord| pole is positive —
that pole is where the variance-carrying *distinctive* rooms sit; the opposite pole is
the near-zero "default/absent" cluster. Structural axes are already signed by a real
quantity (more sections/steps/lines = +) and are not re-oriented.

Recorded + pole per dim (the distinctive side; verified against the rooms there):

| id | name | + pole (distinctive) | rooms at + pole |
|----|------|----------------------|------------------|
| sem[0] | slime-mold ↔ linearization | slime-mold (branch out) | room_builder, artifact_builder |
| sem[1] | aesthetic ↔ pragmatic | aesthetic refinement | voice_polish, human_voice_council |
| sem[2] | refine ↔ review | review (build/assess new) | room_builder, artifact_builder |
| sem[3] | internal ↔ external audience | external audience (market) | gtm, opportunity |
| sem[4] | what's wrong ↔ what's right | what's wrong (diagnose) | hunting, debug |
| sem[5] | artifact output ↔ presence | artifact output (objects) | multipart_response, charge_meter |
| str[0] | many ↔ few sections | many sections | gtm_criticism, opportunity_gtm |
| str[1] | step-procedural ↔ freeform | step-procedural | opportunity_gtm, question_asking |
| str[2] | long ↔ short instructions | long instructions | human_voice_council, opportunity_gtm |
| mov[0] | high rigor ↔ loose | high rigor | reflection, triage |
| mov[1] | constraint-bound ↔ evidence-dependent | constraint-bound | auditory, charge_meter |
| mov[2] | strict format ↔ freeform | strict format (+verify) | debug, teacher |
| mov[3] | form&voice ↔ evidence&verification | form & voice driven | artifact_review, gtm_criticism |

Note on mov[3]: the + (form&voice) pole holds artifact_review and gtm_criticism — the
critique rooms. So the earlier "adversarial" intuition does cluster here, even though the
RESIST move doesn't load. Flagged for possible future revisit; name stands as locked.

### Re-key (ELM-native)
Every oriented axis re-keyed to council-native [-1,+1] via the stack's convention
(ELM = 2^(1/24), compose._elm_key logic): a room's coord = ELM steps above/below the
family median, tanh-squashed over one octave. Result: all three arms now sit on
comparable sd (semantic 0.49-0.70, structural 0.41-0.74, move 0.52-0.79) — no arm
dominates the council crossterms by raw scale. Verified: all coords in [-1,+1]; the
selected 6-dim vector flows into council.compute_crossterms (15 crossterms) cleanly.

