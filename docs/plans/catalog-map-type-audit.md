# Map-type audit — 6 October 2026

Metadata audit of 1517 non-archived maps and visual screening of all 36 unlinked original/one-off scans. 9 originals were flagged in the initial screening. The table below preserves that pre-migration snapshot; migration 116 subsequently applied the taxonomy described here.

The metadata totals include drafts: plan: 50; topographic: 1460; cadastral: 1; regional: 4; route: 2. This is a snapshot, not a permanent collection count.

## Applied taxonomy — migration 116

Applied to production on 6 October 2026. One primary genre: `general_reference`,
`city_plan`, `topographic`, `cadastral`, `hydrographic`, `route`, `thematic` (null for
unknown). Previous values are preserved in `map_type_legacy`; older clients sending
`plan`/`regional` are normalized by a trigger. Geography remains separate.

Optional controlled `map_subjects` are independent of the genre. `depicted_state`
is observed/proposed/mixed/unknown; all remain unknown except the source-backed
Coffyn proposal. `map_images.content_role` is main_map/index_map/legend/text/unknown.
The two L909 verso scans are index_map; other primary images are main_map and
unclassified secondary images remain unknown.

The three source-backed river/port charts below became hydrographic. Cochinchine
Administrative became thematic with an administrative-boundaries subject. Six
ambiguous city/environs/port originals retain city_plan and needs_review status.
All other migrated assertions are provisional, including inherited survey types;
none is claimed as human reviewed. Evidence notes and source URLs are retained.
Reviewed requires a reviewer, timestamp and note; changing genre, subjects or
state invalidates a prior reviewed verdict.

Read-back: 1,518 maps including one archived record; 1,517 non-archived types:
topographic 1,460, city_plan 47, general_reference 3, hydrographic 3, route 2,
cadastral 1, thematic 1. Nine records have subjects; one depicts a proposal.
Scan roles: 789 main_map, 2 index_map, 46 unknown. IDs, slugs, names, publication
states, years, source URLs and series identities matched the before snapshot.
The unrelated migration 115 remains pending; 116 was applied independently.

## Original-map review

### Suggested review order for all 36 originals

1. **One strong reclassification candidate:** the 1882 *Plan topographique du 20e Arrondissement et ses environs* is currently `plan`. Review its survey conventions and legend, then use `topographic` if confirmed.
2. **Three likely hydrographic charts:** *Plan de la rivière de Huê* (1819), *Plan de la rivière de Saïgon* (1791), and *Plan du port de Saigon* (1863). Review navigation alignments, soundings and tidal notes. Retain `plan` until a hydrographic category is supported by the schema.
3. **Five ambiguous originals:** *Saigon Port Plan* (1864), *Saigon–Cholon* (1923), *Saigon–Cholon et Environs* (1912), *Environs de Saïgon* (1900), and *Plan des environs de Saïgon* (1895). Inspect the native legend, relief/contour symbols, soundings and dominant content before choosing between city plan, topographic survey and hydrographic chart.
4. **Keep the remaining 27 classifications provisionally.** Review their original titles, dates and source records as a second pass; the preview screening does not establish their full accuracy. In particular, retain Coffyn as `plan` while making its proposed-design status clear, and keep administrative/economic themes separate from map type.

For each reviewed map, record the decision, reviewer/date, source URL and a short note identifying the scan feature or catalog statement supporting it. A map can depict a city while being topographic or hydrographic; geographic coverage should not decide its type.

“Defensible*” means the current category fits the preview/title. It does not mean the entire native scan and every institution assertion have been verified. Suggested alternatives are review recommendations, not new facts committed to the catalog.

| Map | Year | Current | Recommendation | Verdict | Evidence / next check |
| --- | --- | --- | --- | --- | --- |
| [Map of Imperial City of Hue](/catalog/map-of-imperial-city-of-hue) | 1909 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://lib.nomfoundation.org/collection/1/volume/168/) |
| [Plan Cadastral de la ville de Saigon, Cochinchine Française](/catalog/plan-cadastral-de-la-ville-de-saigon-cochinchine-francaise) | 1882 | cadastral | cadastral | Defensible* | Keep cadastral: explicit cadastral title and parcel-oriented detailed city coverage. [Source](https://gallica.bnf.fr/ark:/12148/btv1b52508901z) |
| [Saigon - Cholon](/catalog/saigon-cholon) | 1923 | plan | plan or topographic | Review | Wide urban and surrounding-territory coverage. Inspect legend and relief representation; the word Plan alone does not settle the method. [Source](https://gallica.bnf.fr/ark:/12148/btv1b53065091z) |
| [Saigon Plan](/catalog/saigon-plan) | 1898 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b530297676) |
| [Cochinchine Francaise](/catalog/cochinchine-francaise) | 1888 | regional | regional | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/bpt6k5783366m) |
| [Đô thành Sài Gòn](/catalog/do-thanh-sai-gon) | 1959 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://collections.lib.uwm.edu/digital/collection/agdm/id/36018) |
| [Saigon Port Plan](/catalog/saigon-port-plan) | 1864 | plan | plan or hydrographic | Review | Port-focused sheet; preview is insufficient to distinguish navigation/depth information from an urban port layout. Inspect native soundings and legend before changing. [Source](https://gallica.bnf.fr/ark:/12148/btv1b84391461) |
| [Plan topographique du 20e Arrondissement et ses environs](/catalog/plan-topographique-du-20e-arrondissement-et-ses-environs) | 1882 | plan | topographic | Review | The title explicitly identifies a topographic survey of an arrondissement; the preview shows village boundaries and extensive surrounding territory. Recommend topographic rather than a generic city plan. [Source](https://gallica.bnf.fr/ark:/12148/btv1b53169711z) |
| [Hanoï Plan dessiné par Pham-Dinh-Bach](/catalog/hanoi-plan-dessine-par-pham-dinh-bach) | 1873 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b531213085) |
| [Province de Thua-thien](/catalog/province-de-thua-thien) | 1909 | regional | regional | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://humazur.univ-cotedazur.fr/s/humazur/item/4054#?c=&m=&s=&cv=) |
| [Plan de la ville de Saigon](/catalog/plan-de-la-ville-de-saigon-1799) | 1799 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b525055501) |
| [Plan de la ville de Hanoï](/catalog/plan-de-la-ville-de-hanoi-1942) | 1942 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b531893703) |
| [Hue et ses environs](/catalog/hue-et-ses-environs) | 1930 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b530647505) |
| [Plan de Saïgon](/catalog/plan-de-saigon) | 1942 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b53197000p) |
| [Plan de la rivière de Huê](/catalog/plan-de-la-riviere-de-hue) | 1819 | plan | hydrographic (taxonomy gap) | Review | Humazur describes the river from the citadel to its mouth and the alignments for crossing the Thuận-An bar. Keep plan until the taxonomy supports hydrographic charts. [Source](https://humazur.univ-cotedazur.fr/s/humazur/item/24330#?cv=&c=&m=&s=&xywh=0%2C-980%2C7560%2C7560) |
| [Town Plan of Hue](/catalog/town-plan-of-hue) | 1945 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://blogs.loc.gov/maps/2018/03/u-s-military-maps-of-hue-vietnam/) |
| [Plan annamite d'Hanoï](/catalog/plan-annamite-d-hanoi) | 1880 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b53109929v) |
| [Cochinchine Administrative](/catalog/cochinchine-administrative) | 1920 | regional | regional | Defensible* | Regional is defensible as extent; administrative boundaries are its thematic purpose, a separate future facet. [Source](https://gallica.bnf.fr/ark:/12148/bpt6k11001779) |
| [Plan de la rivière de Saïgon](/catalog/plan-de-la-riviere-de-saigon) | 1791 | plan | hydrographic (taxonomy gap) | Review | River/estuary chart. The matching 1791 edition in David Rumsey identifies Dépôt de la Marine and Hydrographie Française. Keep plan until hydrographic is supported. [Source](https://gallica.bnf.fr/ark:/12148/btv1b53225307c) |
| [Administrados al. S. Coronel Don Carlos Palanca Gutierrez Dibujado](/catalog/administrados-al-s-coronel-don-carlos-palanca-gutierrez-dibujado) | 1863 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://humazur.univ-cotedazur.fr/s/humazur/ark:/17103/s7m#?cv=&c=&m=&s=&xywh=-4563%2C0%2C15626%2C11194) |
| [Plan de Cholon](/catalog/plan-de-cholon) | 1942 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b53189369q) |
| [Carte Itineraire de Huế à Tourane](/catalog/carte-itineraire-de-hue-a-tourane) | 1889 | route | route | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/bpt6k58577516) |
| [Plan de Hanoï et de ses Environs](/catalog/plan-de-hanoi-et-de-ses-environs) | 1891 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b8440219z) |
| [Saigon - Cholon et Environs](/catalog/saigon-cholon-et-environs) | 1912 | plan | plan or topographic | Review | Saigon–Cholon and environs: extensive settlements and waterways beyond the city. Check native legend before choosing topographic. [Source](https://gallica.bnf.fr/ark:/12148/btv1b53075544f) |
| [Plan topographique de la province de Giadinh](/catalog/plan-topographique-de-la-province-de-giadinh) | 1930 | topographic | topographic | Defensible* | Keep topographic: explicitly titled provincial topographic survey. [Source](https://gallica.bnf.fr/ark:/12148/btv1b53213326r) |
| [Plan de la ville de Hanoï](/catalog/plan-de-la-ville-de-hanoi-1929) | 1929 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b53066612q) |
| [Plan de Gia Định et des environs, dressé par Trần Văn Học](/catalog/plan-de-gia-dinh-et-des-environs-dresse-par-tran-van-hoc) | 1815 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://vi.wikipedia.org/wiki/Tập_tin:Ban_Do_Gia_Dinh_1815_Tran_Van_Hoc_v2.png) |
| [Plan de la citadelle de Hué](/catalog/plan-de-la-citadelle-de-hue) | 1885 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b530231259) |
| [Hanoi economique](/catalog/hanoi-economique) | 1951 | plan | plan | Defensible* | Plan is defensible as form; economic information is a theme, not a replacement for its city-plan geometry. [Source](https://gallica.bnf.fr/ark:/12148/btv1b532122083) |
| [Plan de la Ville de Saigon](/catalog/plan-de-la-ville-de-saigon-1878) | 1878 | plan | plan | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b84924617) |
| [Environs de Saïgon](/catalog/environs-de-saigon) | 1900 | plan | plan or topographic | Review | Environs survey rather than a street-only plan. Inspect relief and survey conventions at native resolution. [Source](https://gallica.bnf.fr/ark:/12148/btv1b531670876) |
| [Plan du port de Saigon](/catalog/plan-du-port-de-saigon) | 1863 | plan | hydrographic (taxonomy gap) | Review | The scan and existing source note describe port-channel soundings, tidal notes and a naval hydrographic survey. A port chart is more specific than city plan. [Source](https://humazur.univ-cotedazur.fr/s/humazur/ark:/17103/8bvk#?c=&m=&s=&cv=&xywh=-4092%2C0%2C17034%2C12203) |
| [Plan des environs de Saïgon](/catalog/plan-des-environs-de-saigon) | 1895 | plan | plan or topographic | Review | Extensive environs and waterway coverage; large scale and Plan in the title do not establish city-plan purpose. Native legend review needed. [Source](https://gallica.bnf.fr/ark:/12148/btv1b530291797) |
| [Carte du Sud-Vietnam](/catalog/carte-du-sud-vietnam) | 1958 | regional | regional | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://vietnamproject.archives.msu.edu/objects/159-547-848/) |
| [Bâtiments civils: Le plan du Colonel du Génie Paul Coffyn pour une ville de 500 000 habitants à Saigon](/catalog/batiments-civils-le-plan-du-colonel-du-genie-paul-coffyn-pour-une-ville-de-500-0) | 1862 | plan | plan | Defensible* | Plan is appropriate, but this is a proposed urban design. It must not be treated as evidence that all drawn streets and canals were built. [Source](https://www.geographicus.com/P/AntiqueMap/saigon-coffyn-1862) |
| [Carte routière des environs de Saïgon](/catalog/carte-routiere-des-environs-de-saigon) | 1922 | route | route | Defensible* | Preview and title are consistent with the current broad category; not a full native-resolution or source-record verification. [Source](https://gallica.bnf.fr/ark:/12148/btv1b53064703f) |

## Series screening

The 1481 series-linked records contain topographic survey sheets and L909 city maps. Metadata consistency was checked; every individual series scan was not visually reclassified. Nha Trang and Qui Nhon versos inherit plan from their city sheets but are reference/index content, not additional city maps. Existing scan-side metadata preserves this distinction.

## Sources checked beyond the preview

- [Humazur river-of-Huê record](https://humazur.univ-cotedazur.fr/s/humazur/item/24330): river mouth and navigation alignments, including the 1819 survey / 1931 copy distinction.
- [David Rumsey’s matching 1791 Saigon river chart](https://www.davidrumsey.com/luna/servlet/detail/RUMSEY~8~1~372156~90138965): Dépôt de la Marine and Hydrographie Française. This is a matching edition reference, not a claim that it is the archive’s same physical copy.
- [Coffyn map record](https://www.geographicus.com/P/AntiqueMap/saigon-coffyn-1862): proposed masterplan.

Gallica pages were not readable through the web tool during this pass. Their catalog links are preserved for follow-up; title/preview-based recommendations are explicitly identified above.
