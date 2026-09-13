/**
 * The public version history.
 *
 * This is the reader-facing half: what changed, in plain language, one entry
 * per version. `CHANGELOG.md` at the repo root is the engineering half — the
 * same versions with the migrations, the deploy failures and the bug detail.
 * Add a release here and there together; nothing generates one from the other.
 *
 * `current: true` marks the version running now. Newest first.
 */
export interface Release {
  version: string;
  /** ISO date the version's work landed, or its first day. */
  date: string;
  /** What this version is, in a few words. */
  headline: string;
  /** Plain-language changes. Three to six is the useful length. */
  changes: string[];
  current?: boolean;
  /** Set when the version lived in an earlier repository. */
  legacy?: boolean;
  /**
   * A real screenshot of that version running, or nothing.
   *
   * Only two versions have one, and that is not an omission to fill in later:
   * 3.0 through 6.0 have no deployed instance, and their code against today's
   * database renders error pages rather than that version's front page. A
   * reconstruction would be a picture of something that never shipped. Both
   * files come from `scripts/gen-changelog-shots.mjs`; `src` is the 1200px cut
   * and the 600 beside it is offered as the small end of the srcset.
   */
  image?: { src: string; alt: string; caption: string };
}

export const releases: Release[] = [
  {
    version: '7.2',
    date: '2026-09-13',
    headline: 'Whole surveys, and a page for every sheet in one',
    current: true,
    changes: [
      "Two complete map surveys go onto the map as a single layer each: the US Army's 1:50,000 of all Vietnam (1963–1989) and the French 1:25,000 of Tonkin and Thanh Hóa (1903–1927). 514 sheets, two taps.",
      'Every survey now has a page listing every sheet it contains — including the ones the archive does not have. It says how many are held, how many have a scan someone has located, and how many nobody has found anywhere.',
      'Each of those sheets has its own page too, with the patch of ground it covers and a way to open the map there. 452 sheets of the 1:50,000 were drawable on the map but appeared in no list and no search, because the archive held them as tiles rather than as records.',
      'A survey is something you can send someone: the link now carries which survey is on the map, the same way it already carried which single sheet.',
      'The map thumbnails on the catalogue were blank for 56 published sheets. They are not blank any more, and the archive stopped asking for picture sizes that were never made.',
      'The front page says what the archive holds today rather than what it held in May, and no longer stops its date range at 1968 when the newest sheets run to 1984.',
    ],
  },
  {
    version: '7.1',
    date: '2026-09-12',
    headline: 'The volunteer tools, named after the work',
    changes: [
      'The tools for working on a scanned sheet are called what they do: Prepare a sheet, Check the text, Draw shapes. No more "triage" and "OCR".',
      'Checking the text is now four jobs you can pick between — the names on the map, the printed index, the numbers, and everything else — each showing how many rows are left. Clear all four and the sheet is done.',
      'Checking the printed legend or the name list frames the table on screen and reads it as a table, in the order the paper prints it.',
      'Drawing shapes, handing a sheet to the model, and checking what it drew are one page with three tabs instead of three separate pages.',
      'Every table in the archive sorts the same way and can be sorted from the keyboard. Blank cells stay at the bottom whichever way a column points.',
      'The catalogue reads top down: the filters fold out of one line above the results instead of standing in a column down the side, so the table has the whole page and shows every column again.',
      'The catalogue can be read as a list or as a wall of map thumbnails, and it remembers which you chose.',
      'The list of maps beside the map is the same list as the catalogue, with fewer columns — and each row now shows the sheet itself. Tap the picture to put it on the map.',
      'Tabs look and behave the same everywhere, and can be used from the keyboard. There were five different sets of them.',
      'Buttons, badges and cards were drawn nine different ways across the site; now there is one of each, in a few sizes. Nothing looks different — there is just far less of it to keep in step.',
      'Every old link still works.',
    ],
  },
  {
    version: '7.0',
    date: '2026-09-01',
    headline: 'Sixteen pages instead of twenty-three, and a front page that costs nothing',
    image: {
      src: '/images/changelog/changelog-7.0.webp',
      alt: 'The archive\u2019s front page: a two-tier top bar, the 1882 Plan Cadastral of Saigon over satellite imagery, a search box, and the Today\u20131882 slider pushed to the 1882 end.',
      caption:
        'The front page with the header slider pushed to 1882. The same gesture the whole archive is about, working before any JavaScript has run.',
    },
    changes: [
      'The archive is one place again. Every tool sits behind one Tools menu, the map is at /explore and scanned sheets at /scan, and switching what you are doing no longer reloads the map.',
      'A dark theme, and one set of colours across the whole site — taken off the printed sheets themselves.',
      'The front page opens with two photographs and a slider between them. The live map is further down, so a visitor who only wants to read does not pay for it.',
      'The map viewer has two panels now: the archive on the left, the sheet you are looking at on the right. One search box drives both.',
      'Reading the names off a sheet can finally be measured. A sheet that prints its own street directory is scored against it, so a change to the reader is judged on numbers rather than on how the output looks.',
      'The basemap is ours, hosted by us, covering Hanoi to the Mekong — no third-party tile service, no API key.',
    ],
  },
  {
    version: '6.0',
    date: '2026-08-02',
    headline: 'A queue, a worker, and a codebase in layers',
    changes: [
      'Publishing a map now queues its own work — mirroring, tiling, warping — instead of someone running commands by hand.',
      'The machines that read sheets hold no database password. They are given a key that can only talk to the archive.',
      'One rule about what is visible: a sheet is draft, public or featured, and nothing else decides.',
      'Stories submitted by contributors go into a review queue.',
      'About 3,100 lines of dead code deleted, and the source split into layers a tool can check.',
    ],
  },
  {
    version: '5.2',
    date: '2026-06-01',
    headline: '/explore and /trip',
    changes: [
      'The map viewer became its own page, with a guided tour and a "what covers this spot" lookup.',
      '/trip plays a story on the map — the page a printed QR code points at.',
      'Catalogue search became one engine instead of three.',
    ],
  },
  {
    version: '5.1',
    date: '2026-05-12',
    headline: 'One layer stack, and a viewer that works on a phone',
    changes: [
      'Sheets stack like layers, each with its own opacity, and the stack survives a reload.',
      'On a phone the viewer is a full-bleed map with three tabs at the bottom.',
      'Sheets can be uploaded in batches, and Scout looks for candidates in other libraries.',
      'Full-text search across the catalogue.',
    ],
  },
  {
    version: '5.0',
    date: '2026-04-04',
    headline: 'The catalogue, the tracing tools, and the first reading pipeline',
    changes: [
      'One catalogue for everything, with editing built into it for staff.',
      'Footprints can be traced by hand — buildings, roads, waterways.',
      'The first pipeline that reads the printed names off a sheet.',
      'Scans are mirrored to our own storage, so the archive does not depend on someone else keeping a file online.',
    ],
  },
  {
    version: '4.1',
    date: '2026-03-08',
    headline: 'Blog, export, and the first attempt at automatic tracing',
    changes: [
      'An about page and a blog.',
      'Anything traced can be exported as a data file.',
      'A first go at tracing shapes automatically, later replaced.',
    ],
  },
  {
    version: '4.0',
    date: '2026-02-08',
    headline: 'Accounts, a database, and stories',
    changes: [
      'Sign-in, so contributions have an author and staff have tools.',
      'The maps moved into a real database instead of a file in the repository.',
      'Stories: a route across the map with stops and text, published for anyone to play.',
      'Installable on a phone.',
    ],
  },
  {
    version: '3.4',
    date: '2026-01-18',
    headline: 'View modes',
    changes: ['Side-by-side and lens comparison between an old sheet and the city now.'],
  },
  {
    version: '3.3',
    date: '2025-12-16',
    headline: 'Undo, shareable links, and rotation',
    changes: [
      'Drawing on the map can be undone and redone.',
      'A link carries the exact view it was copied at.',
      'Sheets can be rotated to sit square with the paper.',
    ],
  },
  {
    version: '3.0',
    date: '2025-10-27',
    headline: 'Rebuilt from scratch',
    changes: [
      'The same project, written a second time — this time as a real application rather than one long HTML file.',
    ],
  },
  {
    version: '2.1',
    date: '2025-06-17',
    headline: 'A time slider',
    legacy: true,
    image: {
      src: '/images/changelog/changelog-2.1.webp',
      alt: 'The 2025 site in Vietnamese: a 1799 plan of Saigon floating over satellite imagery, with a row of years from 1799 to 1984 along the bottom as a slider.',
      caption:
        'The 2025 site, still published. The row of years along the foot is the version\u2019s one new idea, and the reason it earned a number.',
    },
    changes: ['The maps could be moved through by year, instead of picked from a list.'],
  },
  {
    version: '2.0',
    date: '2025-04-20',
    headline: 'First stable public site',
    legacy: true,
    changes: ['A welcome screen, instructions, and a written narrative alongside the maps.'],
  },
  {
    version: '1.0',
    date: '2025-04-12',
    headline: 'One page and a folder of scans',
    legacy: true,
    changes: [
      'A single hand-written page showing scanned sheets of Saigon, published on GitHub Pages.',
    ],
  },
];
