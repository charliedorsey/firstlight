# firstlight_lattice — dataflow

How a prompt becomes a readout. Two phases: a one-time **build** over your room library,
then a per-prompt **read**.

## Build (once per library)

```
your rooms (bundled 23, or --rooms YOUR_FOLDER)
  │
  ├─ semantic arm    each room → scaffold-stripped → TF-IDF → SVD → subject axes
  ├─ structural arm  each room → surface shape (section count, numbered steps, length)
  └─ move arm        each room → cognitive-move profile → SVD → move axes
        │
        ▼
  candidate dim pool (13 axes across the three arms)
        │  orient (positive = the distinctive pole)
        │  ELM-key (re-key every axis to a common [-1,+1] scale)
        ▼
  selector picks 6 axes (max combined variance + orthogonality, positive-skewed)
        │
        ▼
  cached: the 6 council dims, each room's coordinates, room properties (breadth/soul),
          and the fitted transforms needed to project a live prompt
```

Breadth (how many cognitive moves a room exercises) and soul (load-bearing density) are
computed per room across your library and cached as room properties.

## Read (per prompt)

```
incoming prompt
  │
  ├─ ROUTE       hybrid router (coherence words → TF-IDF fallback) → closest room(s)
  │                 → a confidence read: weak top score OR tiny gap = LOW confidence
  │
  ├─ PROJECT     run the prompt through the SAME fitted transforms the rooms used,
  │              orient + ELM-key against the room family → the prompt's coordinate
  │              on each of the 6 council dims
  │
  ├─ READ        council reads the prompt's 6-dim vector → conviction (how coherently
  │              the dims agree) + per-dim character ("reads as: what's wrong / diagnose")
  │
  └─ ANNOTATE    the routed room's breadth/soul (room properties, not prompt scores)
        │
        ▼
  one advisory readout (claim_status: advisory_not_truth)
    · the suggested room(s) + match score + confidence
    · the prompt's character on each council dim
    · council conviction
    · the room's breadth/soul
```

## What the tool does and doesn't claim

- It **suggests** a room and **reads** the prompt's character. It never forces or refuses —
  every output is advisory; the reader decides.
- Confidence is honest: an out-of-scope prompt (e.g. "what is 2+2") still gets its closest
  suggestion, flagged LOW confidence, rather than a false-confident match or a refusal.
- The route is the **locator** (which room). The dims/council are **character** (what kind
  of thinking the prompt wants). Breadth/soul are **room facts**. The faces are kept
  separate on purpose — the readout never collapses them into one false score.

## The dimensions

The 6 council dims are selected from the 13-axis pool at build time. What each one
measures (and its locked name) is in `DIM_NOMENCLATURE.md`; the functional breakdown
(which rooms sit at each pole) is in `DIM_BREAKDOWN.md`.
