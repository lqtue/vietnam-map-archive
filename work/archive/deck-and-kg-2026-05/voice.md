# Voice, Tone & Terminology

The single reference for how VMA sounds. Read this before writing any user-facing copy.

## One-line positioning

> A volunteer-built archive of Saigon's historical maps — open data, georeferenced, free for anyone to use.

## Voice attributes (in priority order)

1. **Specific over generic.** Years, sheet counts, sources — never "many", "various", "rich".
2. **Concrete over abstract.** "Trace a building" beats "contribute to vectorization". "1882 city plan" beats "historical cartographic artifact".
3. **Warm but unsentimental.** No nostalgia syrup ("the city of our grandparents"). The maps do the emotional work.
4. **Playful at moments, not by default.** Playfulness lives in hero headlines, empty states, primary CTAs, the 404. It does **not** live in tool sidebars, form labels, settings, status badges, or admin pages.
5. **Confident, not promotional.** State what it is.

## Audience

Three audiences, balanced — section context decides which leans louder.

- **Volunteers** (OSM/Wikipedia-style newcomers). Optimize for: Contribute hub, tool pages, empty states.
- **Researchers / academics** (Saigoneer, PhD-context readers). Optimize for: About, Blog, source-of-truth language.
- **Vietnamese diaspora / local readers**. Optimize for: Homepage hero, About, place-evocative copy.

## POV

- **"We"** for mission. About, Blog, Footer, project-voice sections.
- **"You"** for action. Contribute hub, tool pages, instructional microcopy.
- Avoid "users". Say *contributor*, *volunteer*, *researcher*, or address as *you*.

## Tone register map

| Surface                                | Register               | Emoji?                       | POV         |
| -------------------------------------- | ---------------------- | ---------------------------- | ----------- |
| Homepage hero + section CTAs           | Playful editorial      | Yes — one per CTA            | We          |
| About / Blog / Footer                  | Editorial-warm         | Section icons only           | We          |
| Catalog / search / lists               | Editorial-functional   | None in chrome               | (none / you) |
| Contribute hub                         | Inviting-instructional | One per role card            | You         |
| Tool sidebars, panels, toolbars        | Functional-technical   | None                         | You         |
| Empty states (any page)                | Playful-warm           | One emoji per state          | You         |
| Errors / form validation               | Plain, helpful         | None                         | You         |
| Auth / legal / consent                 | Plain, formal          | None                         | (none)      |
| Admin pages                            | Terse, functional      | None                         | You         |

## Sentence rules

- Default to **short declaratives**. Fragments are fine when they land ("The Archive.", "Open data. Volunteer-built. Forkable.").
- One idea per sentence. Cut prepositional pile-ups.
- No exclamation points outside hero / empty states. Cap one per page.
- Lists default to **noun-led**, parallel grammar.
- Buttons: **verb + noun** ("Trace a building", "Run OCR", "Open in Allmaps") or **single imperative** ("Continue", "Sign in"). Never `Verb →` *and* an arrow emoji — pick one.

## Emoji policy

**Allowed surfaces:** hero label, empty state, role cards on `/contribute`, base-map buttons (🗺️ 🛰️), language switch (🇬🇧 🇻🇳).

**Disallowed:** tool buttons, sidebar headers, status badges, form labels, table columns, error messages, footer.

**One emoji per surface.** `✏️ Studio` is fine; `✏️ Studio 🎨` is not.

Always keep the `notranslate` class on emoji spans so the Google-Translate-cookie language switch doesn't munge them.

## Terminology lock

Use the left column. Avoid the right.

| Use this                          | Not this                                              |
| --------------------------------- | ----------------------------------------------------- |
| **historical map** (noun)         | scan, image, artifact                                 |
| **layer** (stacked on the viewer) | overlay, warped layer, historical overlay             |
| **georeference** (verb + noun)    | warp, register, align                                 |
| **trace** (verb — polygon work)   | digitize, vectorize *(reserve for the L1 outcome)*    |
| **OCR & Triage**                  | Digitalize *(retire as a surface label)*              |
| **Story Builder**                 | Studio (rename `/create` flow surface)                |
| **Annotate**                      | Studio (`/annotate` only)                             |
| **the archive**                   | "the platform", "the site", "the database"           |
| **contributor / volunteer**       | "user"                                                |
| **Saigon (1880–1930)**            | Ho Chi Minh City *unless the period is post-1975*    |

**Intentional exceptions** (don't rewrite these — they're load-bearing technical names):
- DB columns + enums: `overlay_*`, `digitize`, `seg_queued`, `ocr_done` etc. stay raw in code.
- OpenLayers + Allmaps API surface: `warp`, `warpedOverlay.ts` filename, OL `Overlay` class.
- Routes already in URLs: `/contribute/digitalize` (the surface label changes; the route does not).

## Stock phrases

Use freely, sparingly.

- "Open data. Volunteer-built. Forkable."
- "An archive of the city before the city we know."
- "Every traced building is permanently attributed."
- "No specialist software needed — just a browser."
- "We're not finished. That's the point."

## Don't

- Don't say **amazing**, **powerful**, **revolutionary**, **unlock**, **empower**, **seamless**, **intuitive**, **cutting-edge**.
- Don't apologize for being unfinished — name the phase ("Phase 1: Maps to Geometry").
- Don't write copy that only makes sense if you've already used the app.
- Don't translate emoji ARIA labels.

## Read-aloud test

If a sentence breaks when spoken aloud, rewrite it before shipping.
