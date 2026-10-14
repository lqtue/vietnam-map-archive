# Page specs — every web page, what it must do, and where it drifts

Read-only audit of `main` @ 727bec39, 2026-10-14. One section per page or tool mode, each in the
same template: for / job · access · data · requirements · layout · interaction and states · i18n,
a11y, mobile · findings with `file:line`. "unverified" means read from code, not run.

| File | Covers |
|---|---|
| [public.md](public.md) | `/`, about, blog, changelog, contribute, directory, login, profile, screens; nav, footer, palette, `/vi`, redirects |
| [catalog.md](catalog.md) | The ten `/catalog/**` pages |
| [tools.md](tools.md) | Every `/explore` and `/scan` mode, `/trip/[id]`, the four `/admin` tabs; the keyboard map |

These are a snapshot, not a contract. When a page changes, fix its section or delete it; a stale
spec is worse than none.

## Fix first — real bugs

Ranked by harm. "Checked" means a second reader confirmed it in the code; the rest are one reader's.

| # | Bug | Where | Status |
|---|---|---|---|
| 1 | A new Studio project keeps its local id after the store swaps in the database id, so its saves match no row | `AnnotateMode.svelte:280-291`, `annotationProjectStore.ts:65` | checked |
| 2 | Scout bulk approve or reject counts a failed request as done ("Updated N/N") — `fetch` does not throw on 4xx/5xx | `ScoutPage.svelte:139-160` | checked |
| 3 | Bulk upload re-sends rows it already created, making duplicate drafts | `BulkUploadPage.svelte:131` | unverified |
| 4 | Legend drops staged edits when you switch sheet, and nothing warns on leaving the page | `LegendPage.svelte` | unverified |
| 5 | Sign-in ignores `?next=`, so every sign-in lands on `/` | `login/+page.svelte:17` | checked |
| 6 | A failed load reads as an empty result: "Every map is georeferenced", zeros on `/profile`, "Nothing matches" on `/catalog` | see public.md, catalog.md | checked (georef) |
| 7 | No `+error.svelte`: every 404 and 500 shows SvelteKit's bare default page | `src/routes/` | checked |

## Gaps that need a house rule, not a patch

1. **States.** No shared loading / empty / error pattern; no surface offers Retry. Rule: one
   `StatePanel` (loading, empty, error with Retry), and an error never renders as empty.
2. **Vietnamese.** `/vi` pages mix languages: hero props, `<title>`, tabs, palette and directory skip
   `$t`; nav, footer and palette links drop the `/vi` prefix; the only language switch is behind
   sign-in; legacy redirects probably 404 under `/vi`. Rule: every string through `$t`, every
   internal link through `withLocale`, a public switch in the nav.
3. **Keys.** Eight keydown handlers, four typing-guard variants, and clashes: `r` rotates in Prepare
   but rejects in Scout; `x` rejects in Text but selects in Scout; `Enter` means four things. Rule:
   one `use:keys` action on `isTypingTarget`, and one house map — `j k` move, `v` approve, `x` reject,
   `u` undo, `Esc` cancel — that new tools (the review page) follow.
4. **Review words and save models.** Six status vocabularies and four save models; only one guards
   unsaved work. Rule: approve / reject / pending everywhere a person decides; one draft-and-save
   model with an unsaved-work guard.
5. **Access.** The role is fetched three or four times per page load and pops in late; no `/scan`
   mode gates in its page load (the API still refuses writes). Rule: role from the layout's server
   load, gate in `+page.server.ts`.
6. **Addresses.** Five places link a sheet by uuid, against the slug rule (`CatalogTable.svelte:117`
   and others in catalog.md).
7. **Shells and size.** Three editorial shells, four table styles, five hand-copied tool sidebars;
   nine-plus components over 500 lines; six `{#each}` keyed by index. Docs drift: `design-system.md`
   still names `ChunkyTabs` and shows the retired `mounted` fade; `/screens` misstates
   `--text-base`.

## Order

1. Bugs 1–7 — one PR, about half a day.
2. House rules 1, 3 and 4 written into `design-system.md` and `src/lib/CLAUDE.md`, because the
   review page (`docs/plans/review-page-plan.md`) is the first page built on them.
3. Vietnamese (rule 2) — its own stream, about a day, before the review page opens to contributors.
4. The rest as each page is next touched.
