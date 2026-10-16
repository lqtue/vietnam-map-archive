# Model dedup — one fact, one writer

Status: proposal, 2026-10-16. Nothing built. Line of work: **Debt**. Branch `model-dedup`, worktree
`vma-model-dedup`. Source: the read-only schema audit of 2026-10-16 (§C 1–3) and one read-only pass
over production rows the same day (numbers below).

**Question.** The audit found the same fact stored in several places: series three ways, year and
edition in five, three typed columns with a JSON twin. Which copies are safe to delete, and which
are not copies at all?

**Answer (measured).** Three different cases, so three different fixes:

| Case | What | Live rows, 2026-10-16 | Fix |
|---|---|---|---|
| **Copy, in step** | `maps.series_key` vs `series_id` vs `collection`; same pair on `series_cells`, `cell_printings` | 0 disagree of 1,562 / 1,151 / 1,670 (the 105 trigger works) | Stop reading the copy, then drop it |
| **Copy, in step** | `extra_metadata.sheet_number / sheet_half / edition / series` vs their columns | 1,462 / 725 / 523 / 693 rows hold the twin; 0 disagree | Stop writing the twin, then delete the keys |
| **Copy, drifting** | `maps.edition` vs `series_cells.edition` for the same sheet | 438 differ, all L7014: 431 are only zero padding (`"1"` vs `"001"`), 7 are real (`"2"` vs `"4-DMA"`) | Normalise the padding; a person settles the 7 |
| **Copy, drifting** | `maps.year` vs `series_cells.year` | 40 differ (mostly L7014 drafts; at least one public, Tonkin 25k sheet 14: 1925 vs 1911) | A person settles them |
| **Not a copy** | `year` (the scan's printing) vs `date_label` (display) vs `sheet_printings.*_year` (content / edition / printing) | `date_label` ≠ `year` on 7 rows; `sheet_printings` has **0 rows**; `printing_id` set on 0 maps and 0 items | Name them; decide whether `sheet_printings` gets filled or dropped |

**So what.** The in-step copies cost reading effort, not wrong answers: deleting them is tidy work,
not a fix. The real defect is the ~47 conflicting years and editions, plus a printing model (106) that
nothing uses. Those are facts a person must decide, which makes them review items, and that is bet 2.

## Steps

Migration numbers: 120–121 are Codex's (`1882-extraction`), 122 is `review-store`. This plan starts at **123**.

1. **JSON twins** (~2 h). Stop the writers that still put `sheet_number` / `edition` / `series` into
   `extra_metadata` (`scripts/l7014/l7014_ingest_list.py:58-60`, any other the grep finds). Move the
   readers in `src/lib/data/maps/service.ts` and `catalog/series/[key]/+page.server.ts` to the columns.
   Migration 123 deletes the four keys; nothing is lost because 0 rows disagree. Deploy order: app first.
2. **Edition padding** (~1 h). Migration 124 strips leading zeros on `series_cells.edition` and
   `cell_printings.edition` where the rest matches (`"003"` → `"3"`; `"3-DMA"` untouched — 086 keeps the
   agency). Writes a before/after count into its header.
3. **The ~47 conflicts** (~30 min for Tue). Checked on two of them: they are not errors but two scans
   of one cell from different printings (6550-1: PCL 1965, TTU 1976), and `series_cells` holds one year
   per cell. So most are step 5's problem, a cell has many printings; only the leftovers (6534-3 PCL
   says 2001, after L7014 ended) are mistakes. A list, one line per sheet: both values, the source of each.
   Tue picks. If `review-web` PR 1 has landed, this is a review task (`metadata-conflict`), so the
   seconds are measured; if not, a CSV.
4. **Retire `series_key`** (~1 day). Move the 55 files (`src/`, `scripts/`, `work/`) that read it to `series_id` / `series.key`.
   Then a migration drops `maps.series_key` and the sync trigger; the `series_cells` / `cell_printings`
   pairs follow. Deploy order: app first, migration a deploy later. Lowest value: the copy is in step.
5. **Printings** (decision, Tue). `sheet_printings` (106) is empty. Either fill it from the cell
   catalogue — the one table that says content, edition and printing year apart — or drop it until a
   page needs it.

**Proof each step works.** Before a step, `snapshot.mjs` (to write) saves the answers pages give from
the local test DB: series sheet counts, catalogue filters, one sheet's edition and year. After the
migration it runs again; the two files must be identical, except the lines the step means to change.

## Kill result

Stop after step 1 if any reader of the JSON keys cannot move to the column without changing a page's
output. Skip step 4 entirely if step 3 shows the conflicts, not the copies, were the problem.

## Not in scope

`region` × 4, `label_pins`, the three legend homes, free-text vocabularies, compat views (audit §C 4–10).
Each is its own item.
