# Saigon admin changes, paired with the maps that can check them

Bet 1c in `docs/NOW.md`; plan `docs/plans/series-admin-saigon-plan.md`. Started 2026-10-26.

**Question.** Which of Saigon's dated admin changes can a VMA sheet check, by showing the unit
before and after?

**Answer so far.** 46 of 60 changes have a sheet on both sides (`map_match.csv`). None is checked
yet: `shows_change` is blank on every row.

**So what.** A map that shows a change is a source outside the text family, so it can raise a step
in the plan's N of M. Most of the text here comes from one wiki page, which counts once.

## Files

- `names.csv`: one row per change: date, level, link type, from, to, act, area code, whether it is
  in the Quận 4 chain (`q4`), what the wiki footnote cites, and what a map should show.
- `map_match.csv`: from `map_match.py`. For each change, up to two public sheets before it and two
  after it that cover at least half its area and are fine enough for its level. Fill in
  `shows_change` (y / n / unclear), `checked_by` and `remark` by hand.

- `nac2_check.csv`: each change checked against the captions of the national archive's 50 maps
  (TTLTQG II, `nac2.gov.vn/csdl/bando/1.html` … `50.html`, read 2026-10-26): 20 agree, 5 partly,
  1 differs (E07), 1 conflict (E10b). Seven changes found only there were added to `names.csv`
  (E04b, E04c, E08b, E16b, E17b, E17c, E20b). The captions summarise acts the archive holds, so they
  are the act's family: they settle what an act says, not whether it happened.
- `sources.csv`: 116 sources, most found by four searches on 2026-10-27 (Vietnamese archives and decrees,
  French official publications, map holdings, yearbooks and street-name books). `verified` is the
  search's own word; `my_check` is set where I re-read the source, including one claim rejected
  (D02).
- `transfer-test.md`: how many Quận 4 changes national sources alone still witness. Part 2
  (the four national sheets alone, `sheet_crops.py` → `snapshots.csv`): 2 of 17. Part 1 (texts) not run.
- `map-leads.csv`: sheets VMA does not hold publicly, found 2026-10-26, each listed with the changes
  it could check. Mostly 1955–1993, the years with fewest sheets. `status` says whether I opened the
  record or saw it only in search results.

## Sources

- vi.wiki *Lịch sử hành chính Thành phố Hồ Chí Minh*, revision 75635536 (2026-10-12): every row
  unless its `note` says otherwise. Read for facts only (dates, acts, units), not copied text.
- vi.wiki *Lịch sử Sài Gòn – Thành phố Hồ Chí Minh*, revision 75550622 (2026-09-14): adds nothing
  the admin page lacks at map scale.
- E10b, E12b, E17: from `work/image-processing/experiments/admin-lines/khanh-hoi-chain.md`.
- *Niên giám Hành chánh 1963* (Học viện Quốc gia Hành chánh), public domain on
  [Commons](https://commons.wikimedia.org/wiki/File:Ni%C3%AAn_gi%C3%A1m_H%C3%A0nh_ch%C3%A1nh_1963_(Viet-Nam_Government_Organization_Manual_1963).pdf):
  E31, printed p. 456. It still lists the 41 phường of 1959 in 1963, with no mention of 1434-BNV.
- André Baudrit, *Guide historique des rues de Saïgon* (S.I.L.I., 1943), PDF on
  [entreprises-coloniales.fr](https://www.entreprises-coloniales.fr/inde-indochine/Baudrit-Rues_Saigon.pdf):
  E10b, E12, E12b, E17. In copyright (Baudrit died 1969), so facts and page numbers only. It cites
  the council registers, so it is a separate family from the NAC2 captions unless a check shows they
  share the arrêtés.
- For street names after 1943 (plan phase 3): Nguyễn Q. Thắng and Nguyễn Đình Tư, *Đường phố Thành phố
  Hồ Chí Minh* (2001), named with Baudrit in Erik Harms,
  [Street names as method](https://blog.ukna.asia/2018/11/09/street-names-as-method/) (2018).
  entreprises-coloniales.fr also holds Saigon's mayors and councillors, and the electoral lists of the
  chambers of commerce and agriculture, for "who stood at a place" (plan line 2).

## Check first

1. **E10b, the 1888 merger (note row 5b).** Does the 1895 *Plan des environs de Saigon* still print
   Tam Hội or Vĩnh Hội? If so, the map sides with the 1895 and 1907 texts.
2. **E08 and E10, Hạt 20 (1880–1888).** Does the 1895 sheet still print the 20e arrondissement,
   or put Khánh Hội in the Chợ Lớn arrondissement?
3. **E11, E12, E16, E19, the city's area.** The wiki prints 4.06, 7.91, 13.17 and 16.38 km². Trace
   the city limit on the georeferenced sheets near each year and measure it. This is a check that
   could fail.
4. **E31 and E32, the phường of Quận Tư (1959 and 1962).** Does the 1959 *Đô thành Sài Gòn* or the
   1968 1:12,500 city map print phường names?

## Wiki against the working note

- E10: the wiki prints Hạt 20's end as 12/01/1988, a typo for 1888.
- E31: the wiki gives the act as 504-BNV/NC/8; the note has 504-BNV/HC/NĐ. The wiki also lists
  Quận Tư's four phường of 1959, which answers the note's open item 5.
- E42: the wiki gives 67-HĐBT no Quận 4 content; the note lists it in the Quận 4 chain.
- E43: on the wiki, 147-HĐBT's "P16, P18" are Quận 3 wards; for Quận 4 it merges only P11 into
  P8. The note's P16/P18 conflict may come from reading the Quận 3 line.
- 67-HĐBT, 147-HĐBT and 258-HĐBT are cited to full texts on thuvienphapluat.vn. A script cannot
  fetch them (blocked by Cloudflare), so open them in a browser.

## Limits

- Area codes are hand-drawn boxes, and sheet width stands in for scale (`MAX_KM`). A sheet that is
  listed may still not print the unit.
- Public sheets only. Drafts are missing, such as the Cochinchina 1881–89 atlas.
- No VMA sheet is later than 1984, so phường changes after that are checked against OSM snapshots
  instead.
