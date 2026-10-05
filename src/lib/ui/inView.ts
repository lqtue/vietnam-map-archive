/**
 * `use:inView={() => …}` — calls back each time the element scrolls into (or near) view. A list
 * puts one at its foot to draw the next slice; `rootMargin` makes it fire a screen early.
 */
export function inView(node: HTMLElement, onSeen: () => void) {
  let cb = onSeen;
  const io = new IntersectionObserver(
    (entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      cb();
      // An observer only reports a change, so if the foot is still near the viewport after the
      // callback (a short slice, a collapsed group) it would never ask again. Re-observing
      // delivers a fresh first report.
      io.unobserve(node);
      requestAnimationFrame(() => io.observe(node));
    },
    { rootMargin: '600px 0px' }
  );
  io.observe(node);
  return {
    update(next: () => void) {
      cb = next;
    },
    destroy: () => io.disconnect(),
  };
}
