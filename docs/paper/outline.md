# Paper outline — sections numbered, placeholders resolved

**Written 2026-09-19**, after the three full reads of Phase 1 (Luft & Schiewe, Janata & Cajthaml,
MapEdge). Purpose: three drafted paragraphs in `related-work.md` carry `§X` / `§Y` placeholders and
there was no numbering to resolve them against. This file is that numbering.

Structure follows Phase 3 of the plan, with **§7 split**, because §7 was carrying seven distinct
things under one number and the placeholders could not land.

> *Blind by construction: verifying a georeferenced map series when the check shares the error*
> — two colonial map series of Vietnam, 514 sheets

| § | content | drawn from |
|---|---|---|
| **1** | Introduction — for a series the control points are often already printed; verification and coverage are the real costs | new, ~600 words |
| **2** | Related work | `related-work.md` §2–§5 |
| **3** | Corpus — two series, 514 sheets, provenance, the dataset card's honest limits | `260912-postgrad-route.md` Part 1 |
| **4** | **C1 · Modelling the survey** — cell / sheet / printing; status derived not stored; no FK on purpose | migrations 083–087 |
| **5** | C2 method A — L7014, GeoPDF GCPs, neatline cutline, PMTiles mosaic | `allmaps-series-note.md` §1 |
| **6** | C2 method B — Indochine, printed corners in grades, the thick-line anchor, one rotation per sheet | ibid §2 |
| **7** | **C3 · Verification** — split below | ibid §2, `pipelines.md`, `worker/src/iiifKeys.ts` |
| **8** | Negative results | ibid §5, `260919-seg-audit.md` W8 |
| **9** | Discussion — what generalises; what the ecosystem is missing | ibid §3 |
| **10** | Data and code availability — Zenodo DOI, CC-BY-4.0 derived data, IIIF-referenced scans | `260912-postgrad-route.md` |

### §7, split

| § | content | the failure class it exists for |
|---|---|---|
| **7.1** | What a series already knows about itself — lattice, seams, rim constant, sheet numbering | framing |
| **7.2** | **The lattice: residual *and* collision** — 0.000 on both axes over 58 sheets; rim 84.2 px median, 58/58 within 15%; **`Ha Noi` on `Ninh Bình`'s cell** | two sheets claiming one cell |
| **7.3** | **The seam census** — 750 seams, median 19 m, 56 over 300 m, all 33 sheet↔hand-georeferenced at 447–504 m | a datum fault that splits the corpus |
| **7.4** | **The blind self-check** — `graticule_error` returns `2e-12` on a 470 m fault, because both sides move together | the frame itself being wrong |
| **7.5** | **The outside opinion** — `pick_crs`: two candidates ~470 m apart judged against a 15′ cell good to ~15 m; refuses rather than take the smaller miss | resolving 7.4 |
| **7.6** | The fix, validated without being applied — dry run over 437: median 430 m → 0 m, p95 9 m, max 115 m | — |
| **7.7** | One layer down — the IIIF `w,h` vs width-only size-segment mismatch; 0% at full res, 58.6% one level below the overview | serving, not georeferencing |

### Placeholders resolved

Update these in `related-work.md` when §2–§4's paragraphs are moved into the draft:

| placeholder | where it appears | resolves to |
|---|---|---|
| `§X` | §2 draft, para 2 — "reports a 470 m datum fault … on which a check of exactly this shape returns 2e-12" | **§7.4** |
| `§Y` | §2 draft, para 3 — "the failure that caught `Ha Noi`" | **§7.2** |
| `§Y` | §3 draft, para 1 — "The seam census we report in §Y" | **§7.3** |
| `§X` / `§Y` | §4, the `Ha Noi`-vs-five-checks table | **§7.2**, and the table itself belongs in 7.2 |

---

## The failure taxonomy — §7.1's table, and figure 12

This is the paper's thesis in one table, and it is the thing the three full reads actually bought.
Rows are checks; columns are error classes. **No row sees every column, and the rows that look most
authoritative see the fewest.**

Legend: **✓** catches it · **·** silent · **—** not applicable · **∅** cannot fail by construction.

| check | scope | misregistration inside the frame | the frame/datum itself wrong | two sheets on one cell | sheet-index entry wrong | serving/tile fault |
|---|---|:--:|:--:|:--:|:--:|:--:|
| Corner residual vs sheet layout — *Luft & Schiewe 2021* | per-sheet | ✓ | · | · | · | — |
| Internal consistency: sides, diagonals, cm×dpi, paper bulge — *MapEdge 2025* | per-sheet | ✓ | · | · | ✓ | — |
| `graticule_error` — sheet's GCPs vs the graticule it prints | per-sheet | ✓ | **∅** | · | · | — |
| Adjacency as a least-squares constraint — *Janata & Cajthaml 2020* | inter-sheet | ✓ | · | · | · | — |
| …the same adjacency read back as a residual | inter-sheet | **∅** | **∅** | **∅** | **∅** | — |
| **Seam census** (adjacency left free) | inter-sheet | ✓ | **✓** | ✓ | · | — |
| **Lattice residual** | series | ✓ | · | · | ✓ | — |
| **Lattice collision** | series | · | · | **✓** | ✓ | — |
| **`pick_crs`** — neatline warped under both readings, judged against the cell | external | · | **✓** | · | · | — |
| **Tile-key audit** | serving | — | — | — | — | **✓** |

Three cells carry the argument, and each is sourced to a different paper's own design:

1. **`graticule_error` on "frame/datum wrong" is `∅`, not `·`.** It does not merely miss the fault;
   it *cannot* report it. The sheet's control points are read into the sheet's own datum and
   compared against the graticule that same sheet prints, so a datum error moves both sides
   together. Measured: `2e-12` on A Lưới against a real 470 m displacement. **Luft & Schiewe's
   corner metric has the same shape** — the layout bounding boxes are prior knowledge used both to
   georeference the output and as the truth it is scored against — and they say so without meaning
   to, justifying corners on the grounds that neatlines "can be assumed to be drawn at the
   'correct' place".
2. **Adjacency-as-constraint turns an entire row to `∅`.** Janata & Cajthaml impose edge identity as
   a condition equation, so afterwards "the adjacent edges fit exactly together" by construction.
   The information was spent. Our seam row is the *same measurement left unspent*, and it is the row
   that caught the 470 m fault.
3. **Every per-sheet row is `·` on "two sheets on one cell".** MapEdge's five checks are the most
   complete per-sheet battery published and `Ha Noi` survives all five — sides and diagonals agree,
   sheet cm×dpi matches measured pixels to 0.78%, the content is unmistakably Hanoi — while sitting
   75 km from the city it names. A per-sheet check cannot see a property that is not per-sheet.

**The claim the table licenses**, and it is narrower and better than the retired one:

> Verification instruments for georeferenced series are routinely blind to one error class by
> construction, and which class is predictable from the instrument's scope and from what it has
> already committed to. Naming the scope is therefore a precondition for reporting a residual.

Note what the table does **not** claim: not that the lattice is novel (Luft & Schiewe published it),
not that adjacency is novel (Janata & Cajthaml published it), and not that any of these papers made
a mistake. Every `∅` is the ordinary consequence of a sound design.

### What the table says about our own work, unflatteringly

Worth keeping visible, because it is the honest reading:

- Our `graticule_error` is the **worst** row in the table and it is ours, not a competitor's. It was
  shipped, trusted, and silent through 285 of 437 sheets.
- Our lattice residual row is no better than Luft & Schiewe's on the datum column.
- Only two rows catch the datum fault — the seam census and `pick_crs` — and **one of them needs
  outside data**. The cheap one, seams, needs no external reference at all, which is the practical
  finding: *"a seam is the cheapest measurement here because it needs no outside data, only two
  sheets that claim to share an edge."*
- Four sheets is not enough seams to notice a fault splitting the corpus 285/151. The instrument
  needs a series to work at all, which is the argument for §4's C1.

---

## Next on the draft

1. §7.1's table above is figure 12 and the thesis. It is the first figure to build.
2. Move §2–§5 of `related-work.md` into §2, substituting the resolved numbers above.
3. §1 is unwritten and is ~600 words. It is the last thing to write, not the first.
4. Still open before Phase 3: five of seven citation verifications, and the Tyagi & Dubey
   access decision (`related-work.md` §5).
