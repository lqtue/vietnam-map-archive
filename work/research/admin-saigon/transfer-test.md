# Transfer test: how much of the Quận 4 chain survives on national sources alone

Bet 1c in `docs/NOW.md`; plan `docs/plans/series-admin-saigon-plan.md`. Draft of 2026-10-27, not run.
The decisions marked **open** wait on Tue.

**Question.** Saigon has local sources most districts lack. If we keep only the sources that exist for
any district of Nam Bộ, how many of the Quận 4 changes are still witnessed, and how often is a witness
wrong?

**Answer.** Not run.

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

## Kill

Coverage under 9 of 17 → national scale stays parked (NOW.md *Parked*); publish the table with the
gap. 9 or more → run the same check on one source-poor district. **Open:** the threshold.

## Already known

- The phường changes after 1976 (E43, E44, E46–E48) depend on acts alone: no national sheet is fine
  enough to show them. Without text for 147-HĐBT and 258-HĐBT, E43 and E44 are silent, which is the
  plan's kill rule seen from a second side.
- S01 (printed p. 43) lists tổng Dương Minh in 1892 with three thôn and no Tam Hội or Vĩnh Hội. It
  supports E10b but does not enter the count, because E10b is left out above.
