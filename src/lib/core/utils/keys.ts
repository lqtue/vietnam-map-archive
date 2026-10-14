/**
 * keys.ts — `use:keys`, the one keyboard language for tools.
 *
 *   <div class="page" use:keys={{ j: next, k: prev, v: approve, 'mod+z': undo }}>
 *
 * It sits on the page's root element but listens on `window`, so focus need not be inside.
 *
 * What it does, so a tool does not redo it:
 *  - runs the handler for `e.key`, exact: `r` and `R` are different bindings, as are `?` and `/`;
 *  - skips while the person is typing (`isTypingTarget`: input, textarea, select, editable);
 *  - skips a key that already had its default prevented (a dialog or widget took it);
 *  - skips a plain binding when Ctrl, Meta or Alt is held, so browser shortcuts are left alone.
 *    A binding asks for a modifier by prefix: `mod+z` (Ctrl or Cmd), `ctrl+`, `meta+`, `alt+`;
 *  - lets `Enter` and Space activate a focused button or link instead of also firing a binding;
 *  - calls `preventDefault` when it handled the key (return `false` from the handler to keep the
 *    browser's default);
 *  - `update` swaps the map, `destroy` removes the listener.
 *
 * The house map and the reasons are in `docs/guides/design-system.md` § Keys.
 */
import { isTypingTarget } from './commandPalette';

export type KeyHandler = (e: KeyboardEvent) => void | false;
export type KeyMap = Record<string, KeyHandler>;

type Binding = { key: string; mod: boolean; ctrl: boolean; meta: boolean; alt: boolean };

/** `"mod+z"` → `{ key: 'z', mod: true, … }`. The key is whatever follows the last prefix. */
export function parseBinding(spec: string): Binding {
  const b: Binding = { key: spec, mod: false, ctrl: false, meta: false, alt: false };
  for (;;) {
    const m = /^(mod|ctrl|meta|alt)\+(.+)$/.exec(b.key);
    if (!m) return b;
    b[m[1] as 'mod' | 'ctrl' | 'meta' | 'alt'] = true;
    b.key = m[2];
  }
}

/** Whether a keystroke is exactly this binding: same key, same modifiers, no extras. */
export function matches(
  b: Binding,
  e: Pick<KeyboardEvent, 'key' | 'ctrlKey' | 'metaKey' | 'altKey'>
): boolean {
  if (e.key !== b.key || e.altKey !== b.alt) return false;
  return b.mod ? e.ctrlKey || e.metaKey : e.ctrlKey === b.ctrl && e.metaKey === b.meta;
}

/** Enter and Space belong to a focused control; a binding on them must not double up. */
function activatesControl(e: KeyboardEvent): boolean {
  if (e.key !== 'Enter' && e.key !== ' ') return false;
  const el = e.target as HTMLElement | null;
  return !!el?.closest?.('button, a[href], summary, [role="button"]');
}

/** The keydown handler, split out so it can be tested without a window. */
export function dispatchKey(map: KeyMap, e: KeyboardEvent): boolean {
  if (e.defaultPrevented || isTypingTarget(e.target) || activatesControl(e)) return false;
  for (const spec of Object.keys(map)) {
    if (!matches(parseBinding(spec), e)) continue;
    if (map[spec](e) !== false) e.preventDefault();
    return true;
  }
  return false;
}

export function keys(_node: HTMLElement, initial: KeyMap) {
  let map = initial;
  const onKey = (e: KeyboardEvent) => void dispatchKey(map, e);
  window.addEventListener('keydown', onKey);
  return {
    update(next: KeyMap) {
      map = next;
    },
    destroy() {
      window.removeEventListener('keydown', onKey);
    },
  };
}
