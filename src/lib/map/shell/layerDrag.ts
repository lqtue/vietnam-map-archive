/** Hold a layer's menu button to drag; commit stack order only on release. */
export interface LayerDragOptions {
  id: string;
  onDrag: (id: string | null) => void;
  onMove: (id: string, targetId: string) => void;
}

export function layerDrag(node: HTMLElement, initial: LayerDragOptions | null) {
  let options = initial;
  let finish: ((commit?: boolean) => void) | undefined;
  let suppressClick = false;
  let clickTimeout: ReturnType<typeof setTimeout> | undefined;
  function click(event: MouseEvent) {
    if (!suppressClick) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    suppressClick = false;
  }
  function start(event: PointerEvent) {
    if (!options || event.button !== 0 || !event.isPrimary) return;
    finish?.();
    const settings = options;
    const list = node.closest('ul');
    const originalElement = node.closest<HTMLElement>('[data-layer-id]');
    if (!list || !originalElement) return;
    const original = originalElement;
    let scrollArea: HTMLElement | null = list.parentElement;
    while (scrollArea && !/(auto|scroll)/.test(getComputedStyle(scrollArea).overflowY))
      scrollArea = scrollArea.parentElement;
    const pointer = event.pointerId;
    const initialX = event.clientX;
    const initialY = event.clientY;
    let x = initialX;
    let y = initialY;
    let dragging = false;
    let frame = 0;
    let ghost: HTMLElement | null = null;
    let marker: HTMLElement | null = null;
    let targetId: string | null = null;
    let entries: { row: HTMLElement; rect: DOMRect; transform: string; transition: string }[] = [];
    let offsetY = 0;
    let startScroll = 0;
    let gap = 0;
    node.focus();

    function updatePreview() {
      if (!ghost || !marker) return;
      ghost.style.top = `${y - offsetY}px`;
      const scrollDelta = (scrollArea?.scrollTop ?? 0) - startScroll;
      const others = entries.filter(({ row }) => row !== original);
      const insertion = others.findIndex(
        ({ rect }) => y < rect.top + rect.height / 2 - scrollDelta
      );
      const index = insertion < 0 ? others.length : insertion;
      const from = entries.findIndex(({ row }) => row === original);
      targetId = index === from ? null : (entries[index]?.row.dataset.layerId ?? null);
      const shift = original.getBoundingClientRect().height + gap;
      for (let i = 0; i < entries.length; i++) {
        const { row, transform } = entries[i];
        if (row === original) continue;
        const delta =
          index > from && i > from && i <= index
            ? -shift
            : index < from && i >= index && i < from
              ? shift
              : 0;
        row.style.transform = delta ? `translateY(${delta}px)` : transform;
      }
      const destination = entries[index]?.rect;
      if (!destination) return;
      const top =
        index > from
          ? destination.bottom - original.getBoundingClientRect().height
          : destination.top;
      marker.style.top = `${top - scrollDelta}px`;
    }
    function animate() {
      if (scrollArea) {
        const rect = scrollArea.getBoundingClientRect();
        if (x >= rect.left && x <= rect.right)
          scrollArea.scrollTop += y < rect.top + 32 ? -8 : y > rect.bottom - 32 ? 8 : 0;
      }
      updatePreview();
      frame = requestAnimationFrame(animate);
    }
    function activate() {
      dragging = true;
      suppressClick = true;
      const popover = node.parentElement?.querySelector<HTMLElement>('[popover]');
      if (popover?.matches(':popover-open')) popover.hidePopover();
      entries = [...list!.querySelectorAll<HTMLElement>(':scope > [data-layer-id]')].map((row) => ({
        row,
        rect: row.getBoundingClientRect(),
        transform: row.style.transform,
        transition: row.style.transition,
      }));
      for (const { row } of entries) {
        if (row !== original && !window.matchMedia('(prefers-reduced-motion: reduce)').matches)
          row.style.transition = 'transform 160ms ease';
      }
      const rect = original!.getBoundingClientRect();
      offsetY = initialY - rect.top;
      startScroll = scrollArea?.scrollTop ?? 0;
      gap = parseFloat(getComputedStyle(list!).rowGap) || 0;
      ghost = original!.cloneNode(true) as HTMLElement;
      ghost.removeAttribute('data-layer-id');
      ghost.classList.remove('is-hidden', 'is-dragging');
      ghost.setAttribute('aria-hidden', 'true');
      ghost.inert = true;
      ghost.querySelectorAll('[popover], .series-folder').forEach((element) => element.remove());
      ghost.querySelectorAll('[id]').forEach((element) => element.removeAttribute('id'));
      Object.assign(ghost.style, {
        position: 'fixed',
        left: `${rect.left}px`,
        top: `${rect.top}px`,
        width: `${rect.width}px`,
        boxSizing: 'border-box',
        margin: '0',
        pointerEvents: 'none',
        zIndex: '1000',
        opacity: '1',
        display: 'flex',
        padding: '.5rem',
        gap: '.5rem',
        color: 'var(--sb-text)',
        background: 'var(--sb-card-bg)',
        border: '2px solid var(--sb-accent)',
        borderRadius: 'var(--sb-radius)',
        boxShadow: 'var(--shadow-solid-sm)',
      });
      marker = document.createElement('div');
      marker.setAttribute('aria-hidden', 'true');
      Object.assign(marker.style, {
        position: 'fixed',
        left: `${rect.left}px`,
        width: `${rect.width}px`,
        height: '3px',
        pointerEvents: 'none',
        zIndex: '999',
        background: 'var(--sb-accent)',
      });
      document.body.append(ghost, marker);
      settings.onDrag(settings.id);
      updatePreview();
      frame = requestAnimationFrame(animate);
    }
    const hold = setTimeout(activate, 350);
    function move(next: PointerEvent) {
      if (next.pointerId !== pointer) return;
      x = next.clientX;
      y = next.clientY;
      if (!dragging && Math.hypot(x - initialX, y - initialY) > 6) {
        finish?.();
        return;
      }
      if (dragging) {
        next.preventDefault();
        updatePreview();
      }
    }
    function end(next: PointerEvent) {
      if (next.pointerId === pointer) finish?.(next.type === 'pointerup');
    }
    function escape(next: KeyboardEvent) {
      if (next.key === 'Escape') {
        next.preventDefault();
        finish?.();
      }
    }
    function blur() {
      finish?.();
    }
    finish = (commit = false) => {
      clearTimeout(hold);
      cancelAnimationFrame(frame);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', end);
      window.removeEventListener('pointercancel', end);
      window.removeEventListener('blur', blur);
      window.removeEventListener('keydown', escape);
      ghost?.remove();
      marker?.remove();
      for (const { row, transform, transition } of entries) {
        row.style.transition = transition;
        row.style.transform = transform;
      }
      if (dragging) {
        settings.onDrag(null);
        if (commit && targetId) settings.onMove(settings.id, targetId);
        clearTimeout(clickTimeout);
        clickTimeout = setTimeout(() => {
          suppressClick = false;
        }, 250);
      }
      finish = undefined;
    };
    window.addEventListener('pointermove', move, { passive: false });
    window.addEventListener('pointerup', end);
    window.addEventListener('pointercancel', end);
    window.addEventListener('blur', blur);
    window.addEventListener('keydown', escape);
  }
  node.addEventListener('pointerdown', start);
  node.addEventListener('click', click, true);
  return {
    update(next: LayerDragOptions | null) {
      options = next;
    },
    destroy() {
      finish?.();
      clearTimeout(clickTimeout);
      node.removeEventListener('pointerdown', start);
      node.removeEventListener('click', click, true);
    },
  };
}
