# Companion piece — outline

**Drafted 2026-09-20.** An outline, not prose. The companion to
`draft.md` ("Blind by construction"), not a second version of it.

Working title, in order of preference:

1. **The cost of knowing: verification, custody and a Vietnamese map archive**
2. Blind twice: what a digital archive learns when it re-runs its own numbers
3. Held elsewhere: inherited control and the limits of self-verification

## Thesis

A digital archive's claims about its own correctness are produced by the same
apparatus that produces its errors. VMA published 276 of 437 sheets a median
455 m from where they belong, under a per-sheet check that returned
2.167e-12 on a displaced sheet. When the project regenerated those artifacts
to make the numbers citable, **the numbers did not reproduce either**. Neither
failure was noise; both were structural, and both were invisible from inside.

The cost of finding that out is not a line item in any digitization budget.
Where the sources, the control and the tooling are all held elsewhere — which
is the condition of Vietnamese historical cartography — that cost falls on the
party with the least leverage to reduce it.

## Why this is not the methods paper

`draft.md` is deliberately narrow: a verification taxonomy and one documented
failure. It cannot make the argument below, because the argument is *about*
the conditions under which that paper's own numbers were produced. Keep them
separate, and cite `draft.md` for every geometric claim.

Against `docs/theory.md` §"The Publication Strategy", this is a sixth paper,
not a rewrite of any of the five. It is closest in audience to #5 and closest
in evidence to #1.

---

## §1 · Two failures, one apparatus

**1a. The published fault.** Indian 1960 → WGS 84. 276 of 437 L7014 sheets off
their cell by more than 150 m; CRS displacement 395–528 m, median 455 m. The
graticule self-check returned 2.167e-12 on A Lưới because it read the sheet's
control points into the sheet's own datum and compared them with the graticule
the sheet itself prints — a wrong datum moves both operands together.

→ `draft.md` §1, §7.4 · `work/l7014/regen/REGEN.md` · `regen/datum-split.csv`

**1b. The write-up.** Regenerating those artifacts to move the claim ledger
from **B** to **A** moved almost every number: fault population 285 → **276**;
seams 750 → **717**; median 19 m → **9.2 m**; over 300 m 56 → **97**. And
§7.3's "every one of the 33 seams where a hand-georeferenced sheet meets the
mosaic falls between 447 and 504 m" became **36 seams spanning 1.8–446.2 m,
none in that band** — because a seam returns only the component *normal to the
shared edge*, so one fault vector reads as two numbers (438.0 m median across
E/W edges, 133.7 m across N/S, recombining to 457.9 m). The band was a
displacement magnitude. No seam can return it.

→ `claim-audit.md` R rows · `REGEN.md` §"Second run" · `regen/seams-*-hand.csv`

**1c. The fix, rejected by the check.** The correction itself was thrown out:
`graticule_error` read `lat, lon = TransformPoint(...)` positionally, an SRS
from an EPSG code returns `(lat, lon)` and one from a PROJ4 string returns
`(lon, lat)`, and **370 of 437 sheets were rejected as `offgrid`** — the datum
fix discarded by the very check meant to supersede it.

→ `scripts/l7014_mosaic.py:500` · commit `0aa04f0b`

**The beat this section lands.** Three failures, one apparatus, each invisible
to the layer above it. The third is the one that should worry a reader: a
correct fix was silently rejected, and the rejection looked like a clean run.

## §2 · Where the control comes from

L7014 is US Army Map Service. Its scans are held at the University of Texas
Perry-Castañeda Library. Indochine is the Service géographique de l'Indochine,
its sheet corners printed in grades from the **Paris** meridian. Indian 1960 is
a datum fitted by outside survey programmes for purposes that were not the
mapping of Vietnamese space for Vietnamese readers.

The argument is structural, not accusatory: this archive does not *place* its
sheets so much as **inherit a placement**, and inheriting control means
inheriting its assumptions — including the one that made the check blind. The
apparatus that produced the fault and the apparatus that failed to detect it
arrived together, from the same source, as a single package.

→ `draft.md` §3, §5, §6 · `docs/architecture.md`

**Do not overreach here.** This is one corpus. It is not a general theory of
colonial data, and the piece should say so in the section, not in a footnote.

## §3 · The field is calibrated somewhere else

ICDAR MapText's datasets are Rumsey (US/English), the French Land Registers,
and a Taiwanese set. The segmentation benchmarks are Paris (SODUCO), Swiss
Siegfried, European cadastres. **No Vietnamese and no French-colonial Indochina
corpus in any of them.** A general web search for a Vietnamese historical-map
OCR dataset returns this project's own site. Morlighem's OBIA calibration is
Dutch/Belgian.

So the tooling is imported and its thresholds were tuned on other people's
paper, other people's symbology, other people's script. Two-regime toponymy
with diacritics, on sheets 1791–1968, is not a corner case the field has
priced in — it is a corpus the field has not seen.

→ `docs/field-comparison.md` §5 · `docs/theory.md` §"The open gap"
→ `docs/image-processing-record.md` §4 (nine rejected approaches — evidence of
   what recalibration actually cost)

## §4 · What checking cost, itemised

The claim ledger grades every number A / B / C / D / R — reproduced, recorded
but not re-run, checked against literature, logical under stated inputs, or
revise. Moving the L7014 rows from **B** to **A** took: a full regeneration
over 510 GeoPDFs, a controlled A/B differing by **one flag**
(`--no-datum-shift`), a 778-seam census, and a new script to get the 24
hand-georeferenced sheets into a manifest at all. It produced 4.3 GB of
artifacts that are still gitignored and still undeposited.

The same discipline applied to the image-processing side retracted numbers
this project had been citing: a "SODUCO F1 = 0.59 baseline" that never existed
(the paper reports Panoptic Quality throughout, best 51.1% PQ), a MapSAM2
"+12.8% for prompt quality" still unverified after two passes, and an author
list that was wrong in a file about to be used for outreach.

**The finding to state plainly:** a project that grades its own claims
discovers that a meaningful fraction of them fail. That is the base rate, not a
scandal. Almost nobody publishes it, which is why nobody knows the base rate.

→ `claim-audit.md` · `REGEN.md` · `docs/field-comparison.md` §7
→ `docs/image-processing-record.md` §5 ("what is not established")

## §5 · Who pays for verification

Grant lines fund scanning, georeferencing and platform. They do not fund
re-running. The asymmetry is specific: the institutions holding the sources
have no obligation to verify a placement made downstream, and the downstream
project has no leverage over the sources — but it is the downstream project
whose readers see a street in the wrong place.

Keep this grounded in what the project actually spends and refuses to spend.
`docs/strategy.md` §"Economic Model" and §"Engineering vs. Research" are the
source; do not inflate them into a general claim about heritage funding.

→ `docs/strategy.md` §"Economic Model", §"Sustainability tiers"

## §6 · Practices, stated as claims

Not homilies. Each one earned by a specific failure above:

1. **Publish a claim ledger with the paper.** Label every number by how it was
   established. (§4)
2. **Every number carries a regenerable command.** `REGEN.md` is the model:
   inputs, environment, exact invocations, and a claim-by-claim table against
   the draft. (§1b)
3. **A fault claim needs a controlled A/B on one flag.** Same code, same
   sheets, one difference. (§1a)
4. **Name each check's committed inputs.** A check that shares an assumption
   with the transformation cannot test that assumption. (`draft.md` §7)
5. **Say which relations are free.** A hand-georeferenced sheet sits on the
   lattice *by construction*, so a hand-to-mosaic seam is not an independent
   join — it measures departure from the cell. Only the 715 `pdf / pdf` and 25
   `jpg / jpg` seams are free. (§1b)
6. **Report error as a percentage of map diagonal as well as in metres**, since
   that is the field's unit and metres are not comparable across scales.
   (`field-comparison.md` §7)

## §7 · Limits

- One archive, two series, 514 recorded sheets. Not a prevalence claim about
  digitization anywhere else.
- The custody argument is about *this* corpus's inherited control. It does not
  establish that inherited control is generally blinding.
- **Our own position.** VMA is an independent project doubling as the research
  instrument for a PhD — not a Vietnamese institutional archive, and dependent
  on the same foreign-held scans and imported tooling the section describes.
  Say so in the section. A piece arguing that placement authority sits
  elsewhere is weaker, not stronger, for pretending its author stands outside
  the pattern.

---

## What this piece must not claim

Carried from `claim-audit.md`'s discipline:

- Not that the observed magnitude or frequency generalises.
- Not field priority for lattice, seam, or independent-checkpoint methods —
  those are established (Luft & Schiewe 2021; Janata & Cajthaml 2020; Bozzano
  et al. 2024; Kuna et al. 2024).
- Not that every self-check is blind — only that one is, under named shared
  inputs.
- No number that is not in `draft.md`'s figure ledger with a source.

## Dependencies, in order

1. **§7.3 of `draft.md` must be rewritten first.** This piece quotes it, and it
   is currently wrong. (`.claude/handoff.md` → Next, item 1.)
2. **Decide whether to rebuild production.** `draft.md` §7.6 currently leans on
   the live archive still being displaced. A piece arguing for the cost of
   verification, published while the archive still serves sheets it knows are
   455 m out, has a problem its reader will find first. Resolve before
   drafting §5.
3. **Deposit `work/l7014/`.** Required by `claim-audit.md` regardless; this
   piece makes the deposit part of its argument, so it cannot ship without it.
4. Submit the methods paper. This one cites it.

## Venue

Closest fits, to be checked against current scope rather than assumed:
*Digital Scholarship in the Humanities*, DHQ, or *Journal of Vietnamese
Studies* for the custody framing. The verification practices (§6) could also
stand alone as a short note in e-Perimetron alongside the methods paper.
