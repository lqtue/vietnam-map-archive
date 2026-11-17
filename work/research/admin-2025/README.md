# Admin names, 2025

Where each of the 3,321 communes formed on 1 July 2025 got its name, rebuilt from the work behind
VnExpress, *Tên phường xã mới được đặt lại thế nào* (1 Aug 2025; Quang Tuệ, Thuỳ Linh, Duy Khánh).
Serves bet 1c (`docs/NOW.md`): the 2025 reform as data, the last step of every chain back to 1882.

**Question.** Can the 2025 tagging be rebuilt so a machine settles what it can prove, a person sees
only what it cannot, and every human decision is kept?

**Answer (2026-10-20).** Yes. 3,140 of 3,321 names (94.5 %) settle on syllable rules; 181 go to
a person (21 one-letter differences, 103 compounds, 17 sources kept inside a longer name, 40 "new"
names that edit distance finds close to a source). In 2025 the same step sent 362 names to a person
and kept none of their answers. Family comes out at 2,600 whole, 311 partial and 410 new, against
the article's 2,596, 290 and 435; most of the gap in `new` is names the rules read as compounds or
one-letter differences and send to a person. Judged against every disagreement with the published
tags (below), the rules settle 2 names wrongly without a check; the published tags have 35 wrong.

**So what.** The method the paper claims (machine proposes, flags its own doubt, a person decides,
the decision is logged) now runs on a national dataset, with a queue a person can clear in an
afternoon. The crosswalk check found one wrong hand-typed code (Tân Ninh, Tây Ninh was given
Phường 4 of Tân An, Long An), a one-row slip among the Kiên Giang islands (Kiên Hải, Tiên Hải and
Sơn Hải each held the next unit's codes; fixed in `CODE_FIXES`), and 229 old communes that land in
no new unit.

**Two more checks that could have failed (2026-10-20).**

- *Against the published tags.* `published.py` reads the article's saved Flourish page and joins its
  3,321 units to ours: 3,319 join (the other two carry "Mới hoàn toàn" as their name, an error in the
  published data). The first run agreed on family for 3,185 (96.0 %) and on origin for 3,205. The
  disagreements cut both ways. The published tags call Bến Cát, Bỉm Sơn, Mộc Hoá and Giao Thủy new,
  though each is an old district's name. Our rules settled 22 names as `new` without a check that
  the article had as partial, in four shapes the rules missed: a shorter run of a source (Hiệp Bình),
  a direction word dropped to one syllable (Láng ← Láng Hạ), a source kept inside a longer name
  (Cam Ly - Đà Lạt), and a source's syllables reordered (Thư Vũ ← Vũ Thư) or taken from the
  province (Tuyên Bình). With those rules added, family agrees on 3,206 (96.6 %) and origin on 3,217
  (96.9 %); the queue grows from 168 to 181. Two such misses remain on the auto side (Đông Tiên
  Hưng, Thành Vinh: a syllable from no source).
- *Judged.* `judged.csv` rules on all 170 units where the two differed in family or origin (Claude,
  2026-10-20; 149 high confidence, 20 low, 1 unsure; Tue to confirm). Before the judgment, ours got
  family wrong for 78 of 3,319 units: 57 were `variant`, mapped to partial while the article keeps a
  name spelled differently as whole; 17 were one-letter cases already in the queue; 4 were real.
  Origin was wrong 19 times, every time a compound credited to a district that only shares a
  syllable a commune already supplies. Three fixes followed: `variant` counts as whole, each
  syllable of a compound rests on the lowest unit that bore it, and the island codes are corrected.
  Now ours errs on family 19 times (0.6 %; 17 in the queue, 2 settled wrongly: Đông Tiên Hưng and
  Thành Vinh, each with a syllable from no source) and on origin 4 times (2 in the queue). The
  published tags err on family 35 times (1.1 %): 22 compounds, kept names and old district names
  tagged new, and a one-row slip in two blocks (Cà Mau; the old Nam Định communes, Đồng Thịnh to
  Minh Thái) that gives each unit its neighbour's sources and tag. They err on origin 50 times,
  mostly on which level bore a kept name. The 20 low-confidence rows are one mark apart in a
  Vietnamese name (Lưỡng/Lượng Minh, Thạnh/Thanh An): judged the same place, but only the resolution
  text can say whether a side mistyped or the name changed. Where the two sides agree they are taken
  as right, so both rates are floors.
- *Witness C, geometry, Hồ Chí Minh City.* `overlay.py` lays OSM's communes from 1 Jan 2025 over
  OSM's from 13 Oct 2026. All 441 old and 168 new communes match a GSO code or a new name. The code
  list agrees with the geometry for 349 old communes. The 66 the list left out each land in exactly
  one new commune, and 65 of them are numbered wards: the 2025 sheet joined numbered wards by name
  across the whole merged city, so Phường 1 of Vũng Tàu sits in 11 new units' lists but lies wholly
  in the new Vũng Tàu. That collision explains 18 of the 25 cases where the list names a unit the
  geometry does not reach; 7 named cases remain, plus one 6 % sliver, for a person. 40 old communes
  are truly cut, each piece at least 5 %. Of 105 names kept from an old commune, 98 lie inside the
  unit that bears the name and 3 partly (the source was split nearly in half). Of the 4 that lie
  elsewhere, 3 are `reused` names, which the rules already said came from another unit; the fourth,
  Tân Vĩnh Lộc, credits its Tân to Tân Tạo, which the geometry puts in Bình Tân and Tân Tạo only.

## Run

```sh
python3 work/research/admin-2025/names.py --check   # self-test: folding and rules
python3 work/research/admin-2025/names.py           # writes out/, prints the counts
python3 work/research/admin-2025/published.py ~/Downloads/embed            # agreement with the article
python3 work/research/admin-2025/overlay.py before.geojson after.geojson   # witness C, HCMC
```

`names.py` and `published.py` are stdlib only; `published.py` reads the article's Flourish story
saved as a page and writes nothing. `overlay.py` needs shapely and two OSM extracts cut with
`ogr2ogr` (commands in its docstring) from Geofabrik's `vietnam-250101.osm.pbf` and a current
extract; the boundaries stay outside the repo. To rebuild `data/` from the Drive sheet "Tên ĐVHC
thay đổi" (export as .xlsx): `python3 work/research/admin-2025/extract.py export.xlsx`.

## Method

Names are folded per syllable: the tone is lifted off and kept apart, so *hoà* = *hòa*; a final
*y* after a consonant reads as *i* (*Quý* = *Quí*, *Sỹ* = *Sĩ*) but *uy* keeps its *y*; a trailing
Roman numeral becomes a digit. Each new name is read against its sources: every old commune in its
code list, that commune's district, and its province.

| Kind | Rule | Example | Settles |
|---|---|---|---|
| whole | same folded name | An Phú ← An Phú | itself |
| variant | same letters, marks or spacing differ; counted as kept whole | Avương ← A Vương | itself |
| affix | a direction word, number or A/B added or dropped | Hội An Tây ← Hội An, Láng ← Láng Hạ | itself |
| part | a run of a longer source name | Phan Rang ← Phan Rang-Tháp Chàm, Hiệp Bình ← Hiệp Bình Chánh | itself |
| near | one letter differs | Tân Ninh ← Tây Ninh? | person |
| kept | a source kept whole inside a longer name | Chân Mây - Lăng Cô ← Lăng Cô; Chu Văn An ← Văn An? | person |
| compound | every syllable from a source, in any order; the province only if nothing lower covers it | Thành Bình Thọ ← Thành Sơn + Bình Sơn + Thọ Sơn; Thư Vũ ← Vũ Thư | person |
| reused | the name of an old unit in the same province, not a source | | itself |
| new | none of the above | Chợ Lớn | itself, unless edit distance finds a source close |

Witness B is the edit distance Duy Khánh used in 2025, run on the folded names: the nearest source
and the share of the name that must change. It audits only what the rules cannot prove; on affixes
it is worse than the rules (it puts Vĩnh Bình nearer Bình Minh than Vĩnh Bình Bắc). A kept name is
credited to the highest unit that bore it (province, then district, then commune), as the article
counted, and a compound to the lowest unit that bore each syllable: 36 province, 724 district,
2,151 commune here, against 30, 712 and 2,144.

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
| `judged.csv` | verdicts on every unit where ours and the published tags differ (`published.py` scores both) |
| `out/names.csv` | one row per new commune: kind, origin, sources, witness B, status |
| `out/queue.csv` | the rows a person must decide |
| `out/crosswalk_flags.csv` | old communes in no new unit; hand codes from another province |
| `out/hcmc_overlay.csv` | witness C: share of each old HCMC-area commune in each new commune (≥ 1 %) |
| `out/hcmc_checks.csv` | one row per old commune: the code list against the geometry |
| `out/hcmc_names.csv` | names kept from an old commune: does that commune lie in the unit? |

## Limits

- The crosswalk lists the communes a new unit was built from, not the share of each. 612 old
  communes sit in two or more new units, and 229 in none (66 of them in Hồ Chí Minh City, mostly
  numbered wards, where the 2025 sheet records only whole merges). Geometry settles both; it is
  run for Hồ Chí Minh City only, where it shows most of the gap is numbered wards joined by name.
- Witness C trusts OSM: its 1 Jan 2025 boundaries are what mappers had drawn by then, and a share
  under 5 % is read as the two surveys' edges disagreeing.
- Witness B shares A's folding, so the two are not fully independent.
- *reused* only looks inside the unit's own old provinces, and *new* cannot yet say a name is
  historical: Xuân Hòa came from a village on the 1882 plan, which only the gazetteer knows.
