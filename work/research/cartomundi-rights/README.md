# CartoMundi rights index — 2026-09-30

`sheets.csv` lists every distinct Nakala DOI found in VMA's local CartoMundi
source files for the Tonkin 1:25,000 and Indochine 1:100,000 surveys. The script
queried each DOI's public `GET https://api.nakala.fr/datas/<doi>` record and read
its `http://nakala.fr/terms#license` field. **All 870 of 870 records returned
`CC-BY-4.0`**, with `published` status and at least one file. The 870 consist of
157 linked items from CartoMundi series 243, 221 from series 325, and 492 from
series 561. These are identified scans, including some VMA has not mirrored;
they are not a count of unique printed sheets or of VMA's published maps.

`series.csv` is the existing CartoMundi scout inventory from VMA's database:
25 Indochina or adjacent series, of which four are labelled only Laos or
Cambodia. Of the remaining 21, three have linked DOI records in the local
source files. The other 18 have **no item-level rights result here**. Zero
linked records means the local inventory lacks them; it does not mean the
series has no digital images. The series names are a discovery filter, not a
spatial proof that every sheet covers Vietnam. Series 175 and 243 are two
catalogue descriptions of the same Tonkin survey; the linked items in this
index were taken from 243.

`feuilles/<series-id>.json` holds the reduced CartoMundi sheet list for each of
the 21 Vietnam-related series: **5,367 distinct catalogue records** in total.
It preserves each record's key, number, title, year, and published extent. A
series' declared sheet count and number of returned records differ where the
catalogue carries editions or halves; some series return fewer records than
their declared count. This is the complete set returned by the public endpoint
for these 21 series on 2026-09-30, not a claim that every historical sheet has
a surviving catalogue record.
These files come from CartoMundi's public `/serie/<id>/feuilles` endpoint;
they contain catalogue metadata only, not scan files.

The posted license describes the Nakala item. It does **not** establish that
its depositor controlled every right in the scan or the original map. Every
item checked here names Romain Suarez as depositor. CartoMundi's own [2020
report](https://www.collexpersee.eu/wp-content/uploads/2020/10/CartoMundi_Rapport_enquete_usages.pdf)
said some files were held only for specified use and identified IGN
redistribution restrictions at that time. Those statements predate these
Nakala deposits. Written confirmation from IGN/CartoMundi would settle whether
the item licenses authorize VMA's mirroring and derivative tiles. The
[CC BY 4.0 terms](https://creativecommons.org/licenses/by/4.0/deed.en)
require attribution, a license link, and an indication of changes.

Check new item records with:

```sh
node scripts/cartomundi_rights_index.mjs --check
```

Fetch or resume the complete sheet index with:

```sh
node scripts/fetch_cartomundi_sheets.mjs
```

The script caches successful responses in `nakala-metadata.json` and resumes
after interruptions. `--refresh` rechecks every DOI. To rebuild `series.csv`
from VMA's scout queue and publish the static website snapshot at
`src/lib/data/maps/cartomundiIndex.json`:

```sh
node --env-file=.env scripts/cartomundi_rights_index.mjs --series-from-db --require-sheets
```
