# Transfer test: how much of the Quận 4 chain survives on national sources alone

Bet 1c in `docs/NOW.md`; plan `docs/plans/series-admin-saigon-plan.md`. Drafted 2026-10-27; part 2 run the same day.
The decisions marked **open** wait on Tue.

**Question.** Saigon has local sources most districts lack. If we keep only the sources that exist for
any district of Nam Bộ, how many of the Quận 4 changes are still witnessed, and how often is a witness
wrong?

**Answer.** Part 2 (maps alone) is run: 2 of 17 changes recovered, both as one 1882–1930 window.
Part 1 (texts) is not run.

**So what.** It can stop the national work, but it cannot clear it. The national books were written in
Saigon, by authors who knew Saigon best, and whoever runs the check knows the answer. Both push the
result up. A low score kills; a high score only earns the next test, one source-poor district.

## Why not a blind rebuild

The first idea was a fresh agent rebuilding the chain from national sources, without seeing
`names.csv`. That does not make it blind: the model already knows Saigon's history, and its citations
would only cap that. Where national sources exist, the acts and gazetteers are themselves the list of
changes, so finding the changes comes down to whether the sources cover them. That can be checked
directly, row by row, and it can fail.

## The reference

`names.csv` rows with `q4=y`, frozen at the commit that adds this file: 19 changes. Two are left out
because the sources disagree on whether they happened: E10b (Tam Hội, 1888) and E23b (quận in 1948 or
1952). That leaves **17**. A conflict over a date or a count (E17c, E31, E32) keeps its row. **Open:**
this list.

## Sources allowed

Only kinds that exist for any district in Nam Bộ:

- **Acts with full text**: the 2020, 2024 and 2025 resolutions; 301/UB, 67-HĐBT, 147-HĐBT and
  258-HĐBT if their text is found.
- **National and regional lists**: S01, the 1892 canton-village list; the *Niên giám Hành chánh
  1963*; the French annuaires; the two Nam Bộ books still downloading (the dictionary of Nam Bộ
  place names, and the gazetteer of Nam Kỳ's provinces under French rule). **Open:** whether the two
  *Chế độ thực dân Pháp* volumes count as regional.
- **National map series**: the 1882 arrondissement plan (Cochinchina series), the 1930 Gia Định
  province plan, the 1971 Gia Định sheet and the 1984 L7014 sheet. They are 24–73 km wide, so they
  can show villages and quận, not phường.

Not allowed: vi.wiki (the reference is built from it, so agreement would be an echo), the NAC2
captions (a Saigon exhibition), Baudrit, Saigoneer, blogs, the *Gia Định – Sài Gòn – TP HCM* volumes,
and the city plans (1862–1968).

## The check

For each of the 17 rows and each allowed source, write one row in `witness.csv`: `event, source,
says` (y / differs / silent), `detail`, `page`. Then:

- **Coverage:** rows with at least one allowed witness, out of 17.
- **N of M on national sources:** rows where two families agree, counted by the plan's rule.
- **Error rate per source:** `differs` out of `y + differs`. This is the calibration number (an idea
  raised on 2026-10-27 and not yet agreed): it carries over to districts where that source stands
  alone.
- Each figure is broken down by period (1861–1945, 1945–75, 1976–2025) and given with a Wilson 95%
  interval. With n = 17 the interval is wide (8 of 17 is 26–69%), so read the period breakdown, not
  the second digit.

## Part 2: a change list from the maps alone

Where acts do not survive, maps may be all there is. So, from the four national sheets alone:

1. For each sheet, write what it prints over the Quận 4 area, with no reference to `names.csv`: unit
   names, their level (village, canton, quận), and the lines between them. One row per unit per
   sheet in `snapshots.csv`: `sheet, year, unit, level, printed_as, remark`.
2. Compare each sheet with the next. Every difference is a change in that window: a name gone, a new
   name, a line moved, a level changed.
3. Score against the 17: a reference change is **recovered** if a difference falls in a window that
   contains its date and names the same units. Report it as a window, not a date.

The windows are wide (1882 → 1930 is 48 years) and none of the four can show phường, so expect the
post-1976 rows to be missed. The number to get is how many pre-1976 rows the maps alone recover.

**Result, 2026-10-27 (one reader, Claude; crops from `sheet_crops.py`, readings in `snapshots.csv`).**
The maps alone show **one change**, in the 1882 → 1930 window. In 1882 the peninsula is three villages
(Khánh Hội, Vĩnh Hội, Tạm Hội) in canton Dương Minh, 20e arrondissement, outside the Saigon city
limit. By 1930 (the sheet's 1:50,000 inset) it lies inside the Ville de Saigon, the province limit
runs along the new Kênh Tẻ, and the land south of the canal belongs to villages of Gia Định
province. After 1930 neither the 1971 nor the 1984 sheet prints any unit over the area.

| Recovered | Rows |
|---|---|
| Yes, as the 1882–1930 window | E10 (20e arrondissement gone), E17 (peninsula inside the city) |
| Folded into the same window, not separable | E12b (the first part, 1895: a map cannot show two steps), E17c (the end state matches; the land's spell inside the city, E17b, is invisible) |
| No | E08 (no earlier sheet), E13, E17b, E25, E30, E31, E32, and all six after 1976 |

That is **2 of 17** (interval 3–34%), or 4 of 17 if the folded rows count; 2 to 4 of the 11
before 1976. Three causes: one gap of 48 years, a gap of 41 years (1930–1971) in which no national
sheet letters units inside the city, and scales too coarse for phường.

**So what.** Here the national sheets do not find changes; they check them. Their use is to
confirm a dated text claim inside a window (E10 and E17 above), so part 1, the text sources, decides
the transfer. Where only maps survive, expect a few windows a century, not a chain. The city plans
(left out here as tier 3) are what fill 1930–1971 in Saigon, and most districts lack them.

## Kill

Coverage under 9 of 17 → national scale stays parked (NOW.md *Parked*); publish the table with the
gap. 9 or more → run the same check on one source-poor district. **Open:** the threshold.

## Already known

- The phường changes after 1976 (E43, E44, E46–E48) depend on acts alone: no national sheet is fine
  enough to show them. Without text for 147-HĐBT and 258-HĐBT, E43 and E44 are silent, which is the
  plan's kill rule seen from a second side.
- S01 (printed p. 43) lists tổng Dương Minh in 1892 with three thôn and no Tam Hội or Vĩnh Hội. It
  supports E10b but does not enter the count, because E10b is left out above.
