/**
 * thumbUrl.ts — the same IIIF image at a chosen width.
 *
 * Both URL shapes we hold (`/full/,400/` from the annotation, `/full/800,/`
 * from the `maps.thumbnail` column) end in the same three segments, so swapping
 * the size is a string edit. Anything that is not a IIIF Image API URL comes
 * back unchanged, which is what makes it safe to call on every row.
 *
 * It exists because the stored column is 800px wide and almost nothing renders
 * it at that size: the /catalog table draws it in a 96px cell and the archive
 * rail in a 40px one. Five 800s were 715 kB of front page for five thumbnails
 * (`FeaturedSheet`), and a 39-row list is worse.
 *
 * **200 is right, and it is not certain.** `worker/src/index.ts` is a two-stage
 * lookup: an R2 key first (only what `vips dzsave` wrote, plus whatever
 * derivatives were generated at mirror time — it renders nothing), then, on a
 * miss, a proxy to the original IIIF server read from `sources/<mapId>`. So an
 * arbitrary width works for any sheet whose `sources/` entry exists, and that is
 * almost all of them.
 *
 * `eca788e5-…-20260911` has **no `sources/` entry** — `?force_proxy=1` returns
 * `{"error":"Source not found"}` — so its R2 misses are hard 404s with nothing
 * behind them. It serves the two derivatives it was mirrored with, 400 and 800,
 * and 404s every other width including the three its own `info.json` lists. That
 * is a gap in the bucket's data, not a second kind of service.
 *
 * Do not reach for `info.json` to tell these apart — but the reason changed on
 * 2026-09-14. It used to be that the field lied: the worker hardcoded
 * `profile: 'level2'` on every R2-backed response. Now it says `level0` and
 * lists the sizes R2 really holds (`index.ts:269`), so it would answer
 * truthfully. The reason is now cost: this runs per thumbnail, off a stored URL,
 * and fetching info.json to place one catalog cell is a round trip per card.
 * `sizes` also spells its entries `w,h` while `atWidth` asks by width alone.
 *
 * Measured over the 39 sheets /catalog draws: `200,` is refused by 1 and
 * `1200,` (FeaturedSheet's plate) by 3. Asking every sheet for 400 to protect
 * the one that refuses 200 spends ~15 kB × 38 rows to save one 84-byte 404 —
 * the wrong trade, and reverted once already.
 *
 * So `stepDown` below, and **hardcode no width**: 400 is not a property of the
 * service, it is what that one sheet happens to have been mirrored with. The
 * final fall back to the stored URL is the step that guarantees a picture.
 *
 * ponytail: regex over parsing the IIIF URL. The only failure it can cause is a
 * width the server will not cut, and `stepDown` is what catches that.
 */
export function atWidth(src: string | undefined, width: number): string | undefined {
  return src?.replace(/\/full\/[^/]+\/(\d+)\/(\w+)\.(\w+)$/, `/full/${width},/$1/$2.$3`);
}

/**
 * `on:error` for an `<img>` whose `src` came from `atWidth`: climb to 400 — the
 * widest cut anything here draws — then give up on the stored URL, which is the
 * one width every sheet is certain to have, being where the column came from. Two steps, marked on the element, so a sheet
 * that refuses every width cannot loop.
 *
 * It replaces the one-step "fall back to the stored 800": the sheet that
 * refuses 200 was landing on a 145 kB original to fill a 48px cell.
 */
export function stepDown(e: Event, stored: string | undefined): void {
  const img = e.currentTarget as HTMLImageElement;
  if (!stored) return;
  if (!img.dataset.widened) {
    img.dataset.widened = '1';
    const wider = atWidth(stored, 400);
    if (wider && wider !== img.src) {
      img.src = wider;
      return;
    }
  }
  if (img.src !== stored) img.src = stored;
}
