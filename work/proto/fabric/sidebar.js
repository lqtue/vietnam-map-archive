const $ = id => document.getElementById(id);

export function createSidebar() {
  const sheet = $('sheet');
  const handle = $('sheet-handle');
  const shortcuts = $('sheet-shortcuts');
  const updateCollapsedHeight = () => {
    const height = handle.offsetHeight + shortcuts.offsetHeight;
    if (height) document.documentElement.style.setProperty('--sheet-collapsed-height', `${height}px`);
  };
  const sizeObserver = new ResizeObserver(updateCollapsedHeight);
  sizeObserver.observe(shortcuts);
  sizeObserver.observe(handle);
  const tabs = [
    { id: 'sheets', button: $('tab-sheets'), panel: $('legend'), label: 'Sheets' },
    { id: 'names', button: $('tab-names'), panel: $('controls'), label: 'Names' },
    { id: 'place', button: $('tab-place'), panel: $('nearby'), label: 'Place' },
  ];

  function show(id, focusTab = false) {
    sheet.dataset.tab = id;
    for (const tab of tabs) {
      const active = tab.id === id;
      tab.button.setAttribute('aria-selected', String(active));
      tab.button.tabIndex = active ? 0 : -1;
      tab.panel.hidden = !active;
      if (active) {
        $('sheet-handle-label').textContent = tab.label;
        if (focusTab) tab.button.focus();
      }
    }
  }

  function expand(open) {
    sheet.classList.toggle('expanded', open);
    handle.setAttribute('aria-expanded', String(open));
    document.body.classList.toggle('sheet-expanded', open);
  }

  tabs.forEach((tab, index) => {
    tab.button.onclick = () => show(tab.id);
    tab.button.onkeydown = event => {
      const direction = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
        : direction ? (index + direction + tabs.length) % tabs.length : null;
      if (next === null) return;
      event.preventDefault();
      show(tabs[next].id, true);
    };
  });
  handle.onclick = () => expand(!sheet.classList.contains('expanded'));

  return { show, expand };
}
