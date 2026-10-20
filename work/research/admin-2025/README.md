# Admin names, 2025

Where each of the 3,321 communes formed on 1 July 2025 got its name, rebuilt from the work behind
VnExpress, *Tên phường xã mới được đặt lại thế nào* (1 Aug 2025; Quang Tuệ, Thuỳ Linh, Duy Khánh).
Serves bet 1c (`docs/NOW.md`): the 2025 reform as data, the last step of every chain back to 1882.

**Question.** Can the 2025 tagging be rebuilt so a machine settles what it can prove, a person sees
only what it cannot, and every human decision is kept?

**Answer (first run, 2026-10-20).** Yes. 3,153 of 3,321 names (94.9 %) settle on syllable rules; 168
go to a person (23 one-letter differences, 101 compounds, 44 "new" names that edit distance finds
close to a source). In 2025 the same step sent 362 names to a person and kept none of their answers.
`new` comes out at 435, the article's number exactly; `whole` is 2,537 against 2,596, because 61
names that differ from their source only in marks or spacing (Sà/Xà Phìn, Ea Ly/Ealy) count here as
`variant`, the article's own rule for Nà Hang.

**So what.** The method the paper claims (machine proposes, flags its own doubt, a person decides,
the decision is logged) now runs on a national dataset, with a queue a person can clear in an
afternoon. The crosswalk check found one wrong hand-typed code (Tân Ninh, Tây Ninh was given
Phường 4 of Tân An, Long An) and 233 old communes that land in no new unit.

## Run

```sh
python3 work/research/admin-2025/names.py --check   # self-test: folding and rules
python3 work/research/admin-2025/names.py           # writes out/, prints the counts
```

Stdlib only. To rebuild `data/` from the Drive sheet "Tên ĐVHC thay đổi" (export as .xlsx):
`python3 work/research/admin-2025/extract.py export.xlsx`.

## Method

Names are folded per syllable: the tone is lifted off and kept apart, so *hoà* = *hòa*; a final
*y* after a consonant reads as *i* (*Quý* = *Quí*, *Sỹ* = *Sĩ*) but *uy* keeps its *y*; a trailing
Roman numeral becomes a digit. Each new name is read against its sources: every old commune in its
code list, that commune's district, and its province.

| Kind | Rule | Example | Settles |
|---|---|---|---|
| whole | same folded name | An Phú ← An Phú | itself |
| variant | same letters, marks or spacing differ | Avương ← A Vương | itself |
| affix | a direction word, number or A/B added or dropped | Hội An Tây ← Hội An | itself |
| part | a run of a longer source name | Phan Rang ← Phan Rang-Tháp Chàm | itself |
| near | one letter differs | Tân Ninh ← Tây Ninh? | person |
| compound | every syllable from a different source | Thành Bình Thọ ← Thành Sơn + Bình Sơn + Thọ Sơn | person |
| reused | the name of an old unit in the same province, not a source | | itself |
| new | none of the above | Chợ Lớn | itself, unless edit distance finds a source close |

Witness B is the edit distance Duy Khánh used in 2025, run on the folded names: the nearest source
and the share of the name that must change. It audits only what the rules cannot prove; on affixes
it is worse than the rules (it puts Vĩnh Bình nearer Bình Minh than Vĩnh Bình Bắc). A kept name is
credited to the highest unit that bore it (province, then district, then commune), as the article
counted: 29 province, 735 district, 2,122 commune here, against 30, 712 and 2,144.

## Decide

`out/queue.csv` is what a person must look at. Add one row per decision to `decisions.csv`
(`province,name,kind,origin,by,date,note`) and rerun; the row's status becomes `decided` and the
counts include it. Never edit `out/` by hand.

## Files

| Path | What |
|---|---|
| `data/old_units.csv` | the 10,035 pre-merger communes with GSO codes, districts, provinces |
| `data/new_units.csv` | the 3,321 new communes, the old codes they were built from (`old_codes`), and codes added by hand in 2025 (`hand_codes`, `hand_note`) |
| `decisions.csv` | human decisions, applied on every run |
| `out/names.csv` | one row per new commune: kind, origin, sources, witness B, status |
| `out/queue.csv` | the rows a person must decide |
| `out/crosswalk_flags.csv` | old communes in no new unit; hand codes from another province |

## Limits

- The crosswalk lists the communes a new unit was built from, not the share of each. 612 old
  communes sit in two or more new units, and 233 in none (66 of them in Hồ Chí Minh City, mostly
  numbered wards, where the 2025 sheet records only whole merges). Geometry would settle both.
- Witness B shares A's folding, so the two are not fully independent.
- *reused* only looks inside the unit's own old provinces, and *new* cannot yet say a name is
  historical: Xuân Hòa came from a village on the 1882 plan, which only the gazetteer knows.
