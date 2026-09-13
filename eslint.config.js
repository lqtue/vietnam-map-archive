import js from '@eslint/js';
import ts from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import prettier from 'eslint-config-prettier';
import globals from 'globals';

export default ts.config(
  js.configs.recommended,
  ...ts.configs.recommended,
  ...svelte.configs['flat/recommended'],
  prettier,
  ...svelte.configs['flat/prettier'],
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      // ponytail: repo has ~100 `as any` today; tracked as debt, not a lint failure
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/no-unused-expressions': 'warn',
      'no-empty': ['warn', { allowEmptyCatch: true }],
      // runes-era rules; this codebase is legacy syntax ($:, export let, stores) by convention
      'svelte/no-navigation-without-resolve': 'off',
      'svelte/prefer-svelte-reactivity': 'off',
      'svelte/require-each-key': 'warn',
      'svelte/no-immutable-reactive-statements': 'warn',
      'svelte/no-unused-svelte-ignore': 'warn',
      'svelte/no-useless-mustaches': 'warn',
      // real signals, kept visible; baseline has ~10, fix in module passes
      'svelte/infinite-reactive-loop': 'warn',
      'svelte/no-reactive-functions': 'warn',
      'svelte/no-dom-manipulating': 'warn',
      'svelte/no-at-html-tags': 'warn',
    },
  },
  {
    files: ['**/*.svelte', '**/*.svelte.ts'],
    languageOptions: { parserOptions: { parser: ts.parser } },
    // typescript-eslint's no-unused-vars crashes on the svelte AST (8.68 / plugin-svelte 3.x);
    // svelte-check already reports unused vars/props in components.
    rules: { '@typescript-eslint/no-unused-vars': 'off' },
  },
  // A4: the layering rule, enforced. core -> data -> map -> features -> routes;
  // `ui` is leaf primitives; `$lib/server` is guarded by SvelteKit itself at build time.
  // Deep relative imports across layers don't exist in this tree (all cross-dir imports use $lib/*),
  // so matching on the alias is enough.
  ...[
    ['src/lib/core/**', ['data', 'map', 'features', 'ui', 'server']],
    ['src/lib/data/**', ['map', 'features', 'ui', 'server']],
    ['src/lib/map/**', ['features', 'server']],
    ['src/lib/features/**', ['server']],
    ['src/lib/ui/**', ['data', 'map', 'features', 'server']],
    ['src/lib/server/**', ['map', 'features', 'ui']],
  ].map(([files, forbidden]) => ({
    files: [files],
    rules: {
      // ts-eslint's variant so type-only imports are allowed: they erase at build,
      // so they carry no runtime coupling — only real dependencies are the rule's business.
      '@typescript-eslint/no-restricted-imports': [
        'error',
        {
          patterns: forbidden.map((dir) => ({
            group: [`$lib/${dir}`, `$lib/${dir}/*`],
            message: `Layering rule (CLAUDE.md): ${files.split('/')[2]} may not import $lib/${dir}.`,
            allowTypeImports: true,
          })),
        },
      ],
    },
  })),
  // Feature isolation. A feature may reach into another feature only through a declared
  // seam: `$lib/features/shared/**` (cross-cutting UI: layer panels, SidebarCard, search) or
  // `$lib/features/<x>/shared/**` (that feature's public API). Everything else under
  // another feature is private. Before this rule, `features/catalog` was a shared layer
  // nobody had declared — four features imported its panels.
  // `regex`, not `group`: gitignore-style `!` negation is not honoured by this rule.
  ...['admin', 'catalog', 'contribute', 'explore', 'stories', 'studio', 'shared'].map((feat) => ({
    files: [`src/lib/features/${feat}/**`],
    rules: {
      '@typescript-eslint/no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              regex: `^\\$lib/features/(?!(${feat}|shared)/|[^/]+/shared/)`,
              message: `Feature isolation (CLAUDE.md): ${feat} may import another feature only via $lib/features/shared or $lib/features/<x>/shared.`,
              allowTypeImports: true,
            },
            // the layering rule still applies inside features
            {
              group: ['$lib/server', '$lib/server/*'],
              message: 'Layering rule (CLAUDE.md): features may not import $lib/server.',
              allowTypeImports: true,
            },
          ],
        },
      ],
    },
  })),
  {
    ignores: [
      '.svelte-kit/',
      'build/',
      'node_modules/',
      'work/',
      'scripts/',
      'worker/',
      'static/',
      // Playwright artefacts. Gitignored, but eslint does not read .gitignore,
      // so `npm run lint` broke for anyone who had run the suite.
      'test-results/',
      'playwright-report/',
      // Same story for wrangler's build scratch: a deploy leaves bundled
      // worker code in `.wrangler/tmp/`, and linting somebody's bundler output
      // reported 334 errors in four generated files and none in ours.
      '.wrangler/',
    ],
  }
);
