/**
 * cli.mjs — one flag convention for anything that can write.
 *
 * The scripts in `scripts/oneoff/` disagreed about this, and the disagreement
 * was the dangerous kind: eight wrote only with `--apply`, four wrote unless
 * you passed `--dry`. Same directory, opposite defaults, and the writing
 * default was the one that looks like a normal invocation — `node --env-file=.env
 * scripts/oneoff/ingest_indochine_nakala.mjs` inserted rows and tiled scans.
 *
 * So: nothing writes without `--apply`. `--dry` is still accepted everywhere it
 * used to be, and now means what it always read as.
 */

/**
 * @param {string[]} [argv]
 * @returns {boolean} true only if `--apply` was passed.
 */
export function willApply(argv = process.argv.slice(2)) {
  if (argv.includes('--apply') && argv.includes('--dry')) {
    // A stack trace here would be noise: this is a typo at the prompt, not a
    // fault in the script.
    console.error('--apply and --dry together: say which one you mean.');
    process.exit(2);
  }
  return argv.includes('--apply');
}

/**
 * @param {string} name e.g. `--model`
 * @param {string[]} [argv]
 * @returns {boolean}
 */
export function flag(name, argv = process.argv.slice(2)) {
  return argv.includes(name);
}

/**
 * The value after `--name`, or null.
 * @param {string} name
 * @param {string[]} [argv]
 * @returns {string | null}
 */
export function opt(name, argv = process.argv.slice(2)) {
  const i = argv.indexOf(name);
  if (i < 0 || i === argv.length - 1) return null;
  const v = argv[i + 1];
  return v.startsWith('--') ? null : v;
}

/**
 * The line every dry run ends on, so they all end the same way.
 * @param {string} [extra] what `--apply` would do, in the caller's words.
 */
export function dryNotice(extra) {
  console.log(`\nDry run. Nothing was written.${extra ? ` ${extra}` : ''} Re-run with --apply.`);
}
