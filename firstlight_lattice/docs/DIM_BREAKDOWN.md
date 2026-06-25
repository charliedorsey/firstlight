# firstlight_lattice — candidate dim breakdown (what each dimension actually measures)

This explains, in plain terms, what each of the 13 candidate dimensions measures — read
off **which rooms score high vs low on it**, which is the real functional meaning (more
honest than the raw SVD term lists, which can mislead). Generated from live data.

## How to read a dimension

Each dim is an **axis**: a line with two poles. A room's coordinate says where it sits on
that line. So a dim doesn't measure one thing — it measures a **contrast**:
- **semantic dims** contrast SUBJECTS: rooms about one topic-cluster at the + pole, the
  opposing topic-cluster at the − pole. (e.g. "build-an-artifact" rooms vs "be-present" rooms.)
- **structural dims** measure SURFACE SHAPE: how many sections / numbered steps / lines a
  room has. Positive = more scaffolding. (No contrast; it's a real quantity.)
- **move dims** contrast COGNITIVE MOVES: rooms that demand one move-family (e.g. VERIFY)
  at the + pole, rooms demanding the opposing family (e.g. TONE) at the −.

## The three operations applied to every dim (the F3/F12/F13 work)

1. **Orientation (valence):** SVD axes have an arbitrary sign, so each is flipped if needed
   so the **positive pole is the more-descriptive one**. Recorded per dim ("flipped"/"as-is").
2. **ELM re-key (native scale):** every dim is re-keyed to the stack's native magnitude —
   ELM = 2^(1/24), the same `compose._elm_key` the council already uses. A coordinate is
   the number of ELM steps a room sits **above/below the family median**, tanh-squashed to
   [−1,+1]. So +1 = strongly above the typical room, −1 = strongly below, 0 = typical. This
   replaces the earlier raw mixed scales (where structural z-scores hit +4.4 and drowned
   everything); now all arms sit on one comparable scale.
3. **Selection by combined variance:** the ≤6 axes are chosen to MAXIMIZE the variance the
   six **together** explain (their combined span), not six individually-big-but-redundant
   axes. Multiple strategies are tested (max_combined / orthogonality heuristic / greedy);
   they agree closely (CVE ≈ 0.85), and max_combined is the live pick.

## Per-dimension cards

### sem[0] · subject:room_builder v2>teacher v1
- **arm:** semantic  ·  **orientation:** as-is  ·  **ELM-keyed sd:** 0.68
- **measures:** a contrast in SUBJECT. High-pole rooms are about one topic cluster; low-pole the opposite.
  - **high (+):** room_builder v2, artifact_builder v
  - **low (−):** boundary v1, teacher v1

### sem[1] · subject:voice_polish v2_0>opportunity_gtm v5
- **arm:** semantic  ·  **orientation:** as-is  ·  **ELM-keyed sd:** 0.70
- **measures:** a contrast in SUBJECT. High-pole rooms are about one topic cluster; low-pole the opposite.
  - **high (+):** voice_polish v2_0, human voice_counci
  - **low (−):** question_asking v4, opportunity_gtm v5

### sem[2] · subject:room_builder v2>voice_polish v2_0
- **arm:** semantic  ·  **orientation:** flipped  ·  **ELM-keyed sd:** 0.49
- **measures:** a contrast in SUBJECT. High-pole rooms are about one topic cluster; low-pole the opposite.
  - **high (+):** room_builder v2, artifact_builder v
  - **low (−):** human voice_counci, voice_polish v2_0

### sem[3] · subject:generic_opportunit>life_os v1
- **arm:** semantic  ·  **orientation:** flipped  ·  **ELM-keyed sd:** 0.55
- **measures:** a contrast in SUBJECT. High-pole rooms are about one topic cluster; low-pole the opposite.
  - **high (+):** generic_opportunit, opportunity_gtm v5
  - **low (−):** strategic v1, life_os v1

### sem[4] · subject:hunting v1>life_os v1
- **arm:** semantic  ·  **orientation:** flipped  ·  **ELM-keyed sd:** 0.65
- **measures:** a contrast in SUBJECT. High-pole rooms are about one topic cluster; low-pole the opposite.
  - **high (+):** hunting v1, debug v1
  - **low (−):** question_asking v4, life_os v1

### sem[5] · subject:multipart_response>reflection v1
- **arm:** semantic  ·  **orientation:** flipped  ·  **ELM-keyed sd:** 0.67
- **measures:** a contrast in SUBJECT. High-pole rooms are about one topic cluster; low-pole the opposite.
  - **high (+):** multipart_response, charge_meter v1
  - **low (−):** boundary v1, reflection v1

### str[0] · shape:section_count
- **arm:** structural  ·  **orientation:** as-is  ·  **ELM-keyed sd:** 0.41
- **measures:** how much of the surface feature `section_count` a room carries. Positive = more.

### str[1] · shape:numbered_steps
- **arm:** structural  ·  **orientation:** as-is  ·  **ELM-keyed sd:** 0.41
- **measures:** how much of the surface feature `numbered_steps` a room carries. Positive = more.

### str[2] · shape:len_lines
- **arm:** structural  ·  **orientation:** as-is  ·  **ELM-keyed sd:** 0.74
- **measures:** how much of the surface feature `len_lines` a room carries. Positive = more.

### mov[0] · moves:reflection v1>human voice_counci
- **arm:** move  ·  **orientation:** as-is  ·  **ELM-keyed sd:** 0.79
- **measures:** a contrast in COGNITIVE MOVES (CONSTRAIN/TONE/EVIDENCE). High-pole rooms demand these moves.
  - **high (+):** reflection v1, triage v1
  - **low (−):** opportunity_gtm v5, human voice_counci

### mov[1] · moves:auditory v6_canoni>life_os v1
- **arm:** move  ·  **orientation:** as-is  ·  **ELM-keyed sd:** 0.52
- **measures:** a contrast in COGNITIVE MOVES (FORMAT/EVIDENCE/TONE). High-pole rooms demand these moves.
  - **high (+):** auditory v6_canoni, charge_meter v1
  - **low (−):** spirit_animal_coun, life_os v1

### mov[2] · moves:debug v1>spirit_animal_coun
- **arm:** move  ·  **orientation:** as-is  ·  **ELM-keyed sd:** 0.56
- **measures:** a contrast in COGNITIVE MOVES (VERIFY/TONE/FORMAT). High-pole rooms demand these moves.
  - **high (+):** debug v1, teacher v1
  - **low (−):** life_os v1, spirit_animal_coun

### mov[3] · moves:artifact_review>life_os v1
- **arm:** move  ·  **orientation:** as-is  ·  **ELM-keyed sd:** 0.58
- **measures:** a contrast in COGNITIVE MOVES (RESIST/CONSTRAIN/EVIDENCE). High-pole rooms demand these moves.
  - **high (+):** artifact_review, gtm_criticism v2
  - **low (−):** auditory v6_canoni, life_os v1

