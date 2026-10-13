<!--
  HowItWorks.svelte — the "how this works" section on the front page.

  Four steps, each a picture beside a paragraph. It replaced `HeroDemo`, a clip
  of the map with a live-map upgrade behind a button: that was one composition
  fitted to every screen, so it was a 16:9 film on a desktop and a cropped stripe
  of satellite on a phone, and the sheet — the point of it — was on screen for a
  few seconds of nine. Pictures and sentences reflow instead: side by side on a
  wide screen, stacked on a narrow one, and nothing here has to load, play or be
  waited for.

  The pictures are real screenshots, written by
  `scripts/gen-how-it-works-shots.mjs`, which is also where to look when a
  count in the copy no longer matches what the picture shows.
-->
<script lang="ts">
  import { t, locale } from '$lib/core/i18n';
  import { openPaletteWith } from '$lib/core/utils/commandPalette';

  /** The 1882 sheet's readable address, for the first step's link. */
  export let slug: string;
  /** Approved footprints, names a person has checked and the sheets they sit on. */
  export let footprints: number;
  export let names: number;
  export let nameSheets: number;
  /** Legend entries placed on the ground, and the sheets they are on. */
  export let legendEntries: number;
  export let legendSheets: number;

  /** 1,178 in English, 1.178 in Vietnamese. */
  $: num = new Intl.NumberFormat($locale === 'vi' ? 'vi-VN' : 'en-US').format;

  /** Two widths of each shot, written together by the script. */
  const srcset = (name: string) =>
    `/images/how/${name}-600.webp 600w, /images/how/${name}.webp 1200w`;
  /** Half the column on a wide screen, all of it on a narrow one. */
  const SIZES = '(max-width: 800px) 100vw, 640px';
</script>

<section class="home-section how" id="how-it-works">
  <div class="how-head">
    <h2 class="feature-title">{$t('How this works')}</h2>
    <p class="feature-description">
      {$t(
        'From a scan in a library to a name you can search: four steps, and every picture below is the real app.'
      )}
    </p>
  </div>

  <ol class="how-steps">
    <li class="how-step">
      <img
        class="how-shot"
        src="/images/how/how-1-pin.webp"
        srcset={srcset('how-1-pin')}
        sizes={SIZES}
        alt={$t('The edge of the 1882 Saigon survey, half-transparent over the modern map')}
        width="1200"
        height="800"
        loading="lazy"
        decoding="async"
      />
      <div class="how-text">
        <h3 class="how-title">{$t('Pin the scan to the ground')}</h3>
        <p class="feature-description">
          {$t(
            'Volunteers match points on the scan — a street corner, a church, a bend in the river — to the same places on the modern map. The sheet then lies over the city, and you can see where the streets stayed and where they did not.'
          )}
        </p>
        <a href="/explore?map={slug}" class="text-link">{$t('Open this sheet in the viewer')}</a>
      </div>
    </li>

    <li class="how-step">
      <img
        class="how-shot"
        src="/images/how/how-2-trace.webp"
        srcset={srcset('how-2-trace')}
        sizes={SIZES}
        alt={$t('Traced plots and buildings drawn over the 1882 survey of Saigon')}
        width="1200"
        height="800"
        loading="lazy"
        decoding="async"
      />
      <div class="how-text">
        <h3 class="how-title">{$t('Trace what it shows')}</h3>
        <p class="feature-description">
          {$t(
            '{N} building outlines on the 1882 survey have been traced and approved, and more are waiting for a second look. Outlines turn a picture of a city into shapes a computer can count, compare and search.',
            { N: footprints }
          )}
        </p>
        <a href="/scan?mode=shapes" class="text-link">{$t('Trace buildings')}</a>
      </div>
    </li>

    <li class="how-step">
      <img
        class="how-shot"
        src="/images/how/how-3-names.webp"
        srcset={srcset('how-3-names')}
        sizes={SIZES}
        alt={$t(
          'A search for Khánh Hội: the places the archive has read, and the maps that print the name'
        )}
        width="1200"
        height="800"
        loading="lazy"
        decoding="async"
      />
      <div class="how-text">
        <h3 class="how-title">{$t('Read the names off it')}</h3>
        <p class="feature-description">
          {$t(
            'A model reads every printed word and a person checks its work. {N} names on {M} sheets have been checked so far, and each one becomes a place you can search for, across every map that prints it.',
            { N: num(names), M: nameSheets }
          )}
        </p>
        <button
          type="button"
          class="text-link how-link"
          on:click={() => openPaletteWith('Khánh Hội')}>{$t('Search for Khánh Hội')}</button
        >
      </div>
    </li>

    <li class="how-step">
      <img
        class="how-shot"
        src="/images/how/how-4-legend.webp"
        srcset={srcset('how-4-legend')}
        sizes={SIZES}
        alt={$t(
          'The Legend tab of the 1923 Saigon–Cholon plan: a numbered list beside the map, with entry 9, the Institut Pasteur, marked on it'
        )}
        width="1200"
        height="800"
        loading="lazy"
        decoding="async"
      />
      <div class="how-text">
        <h3 class="how-title">{$t('Follow the legend')}</h3>
        <p class="feature-description">
          {$t(
            'Many plans print a numbered key to their buildings. Each number is placed on the ground, so the key becomes a list you can click: {N} entries on {M} sheets so far, from Saigon in 1878 to the city plans of 1968.',
            { N: num(legendEntries), M: legendSheets }
          )}
        </p>
        <a href="/explore?map=saigon-cholon" class="text-link">{$t('Open the 1923 plan')}</a>
      </div>
    </li>
  </ol>
</section>

<style>
  .how-head {
    max-width: 62ch;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .how-steps {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 3rem;
    counter-reset: step;
  }

  /* The picture takes the wider track, and every second step flips sides so the
     column reads as a zigzag rather than four copies of one row. */
  .how-step {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
    align-items: center;
    gap: 1.5rem 3rem;
    counter-increment: step;
  }

  .how-step:nth-child(even) {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
  }

  .how-step:nth-child(even) .how-shot {
    order: 2;
  }

  /* 3:2 whatever the shot's own size, so the section's height is known before
     any image arrives. */
  .how-shot {
    display: block;
    width: 100%;
    height: auto;
    aspect-ratio: 3 / 2;
    object-fit: cover;
    border: var(--border-thick);
    border-radius: var(--radius-md);
    background: var(--color-bg);
  }

  .how-text {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }

  /* The step's number, from the counter, so the list needs no markup for it. */
  .how-text::before {
    content: counter(step);
    display: grid;
    place-items: center;
    width: 2rem;
    height: 2rem;
    border: var(--border-thin);
    border-radius: var(--radius-pill);
    font-family: var(--font-family-display);
    font-size: 0.9rem;
    font-weight: 800;
  }

  .how-title {
    margin: 0;
    font-family: var(--font-family-display);
    font-size: clamp(1.3rem, 2.4vw, 1.6rem);
    font-weight: 800;
    line-height: 1.2;
  }

  /* A button that looks like the link beside it: `.text-link` supplies the
     type and the underline; this takes off what a button brings. */
  .how-link {
    padding: 0;
    border: 0;
    background: none;
    cursor: pointer;
  }

  @media (max-width: 800px) {
    .how-steps {
      gap: 2.5rem;
    }

    /* One column, picture first — also for the flipped steps. */
    .how-step,
    .how-step:nth-child(even) {
      grid-template-columns: minmax(0, 1fr);
    }

    .how-step:nth-child(even) .how-shot {
      order: 0;
    }
  }
</style>
