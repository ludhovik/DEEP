// Layout preferences are device-local, independent of scientific view codes.
export function useMobileLayout(mode, width, height, coarsePointer) {
  if (mode === 'mobile') return true;
  if (mode === 'desktop') return false;
  return width <= 700 || (coarsePointer && Math.min(width, height) <= 600);
}

export function createMobileLayout() {
  const root = document.documentElement;
  const pointer = matchMedia('(pointer: coarse)');
  let mode = 'auto', active = null, mobile = false, gui, pov;
  let mounts = [];
  try { mode = localStorage.getItem('deepscope.layout') || 'auto'; } catch {}
  if (!['auto', 'mobile', 'desktop'].includes(mode)) mode = 'auto';
  const ui = document.createElement('div');
  ui.id = 'responsive-ui';
  ui.innerHTML = `
    <label id="layout-choice">Layout <select aria-label="Viewer layout">
      <option value="auto">Auto</option><option value="mobile">Phone</option><option value="desktop">Desktop</option>
    </select></label>
    <nav id="mobile-nav" aria-label="Viewer controls">
      ${['Dataset','Fields','View','Legend','Export'].map(label => `<button type="button" data-panel="${label.toLowerCase()}" aria-controls="mobile-sheet" aria-expanded="false">${label}</button>`).join('')}
    </nav>
    <section id="mobile-sheet" hidden aria-labelledby="mobile-sheet-title">
      <header><strong id="mobile-sheet-title"></strong><button type="button" id="mobile-close" aria-label="Close controls">Done</button></header>
      <div id="mobile-sheet-body"></div>
    </section>`;
  document.body.append(ui);
  const select = ui.querySelector('select'); select.value = mode;
  const sheet = ui.querySelector('#mobile-sheet');
  const content = ui.querySelector('#mobile-sheet-body');
  const title = ui.querySelector('#mobile-sheet-title');
  const buttons = [...ui.querySelectorAll('[data-panel]')];
  const info = document.getElementById('info-panel');
  const hint = info?.querySelector('.hint');
  const desktopHint = hint?.innerHTML;
  function syncInfo() {
    const button = document.getElementById('info-collapse-button');
    if (!button || !info) return;
    const expanded = mobile ? info.classList.contains('mobile-info-expanded') : !info.classList.contains('collapsed');
    button.textContent = expanded ? '−' : '+';
    button.setAttribute('aria-expanded', String(expanded));
    button.setAttribute('aria-label', expanded ? 'Collapse title box' : 'Expand title box');
  }
  if (info) new MutationObserver(syncInfo).observe(info, {attributes:true, attributeFilter:['class']});

  function restore() {
    for (const {element, marker, closed, instance} of mounts) {
      if (!element.isConnected) { marker.remove(); continue; }
      if (marker.isConnected) marker.replaceWith(element);
      else element.remove();
      element.classList.remove('mobile-mounted');
      if (instance && closed) instance.close();
    }
    mounts = [];
  }
  function mount(element, instance) {
    if (!element?.isConnected) return;
    const marker = document.createComment('desktop panel position');
    element.before(marker);
    mounts.push({element, marker, instance, closed: instance?._closed});
    element.classList.add('mobile-mounted');
    content.append(element);
    instance?.open();
  }
  function show(panel, focus = true) {
    restore(); active = mobile ? panel : null;
    root.dataset.mobilePanel = active || '';
    sheet.hidden = !active;
    buttons.forEach(b => b.setAttribute('aria-expanded', String(b.dataset.panel === active)));
    if (!active) return;
    title.textContent = active[0].toUpperCase() + active.slice(1);
    if (['dataset','fields','view','export'].includes(active)) mount(gui?.domElement, gui);
    if (active === 'view') mount(pov?.domElement, pov);
    if (active === 'legend') mount(document.getElementById('legend-panel'));
    if (active === 'export') mount(document.getElementById('export-panel'));
    content.scrollTop = 0;
    if (focus) ui.querySelector('#mobile-close').focus();
  }
  function close() {
    const previous = active; show(null);
    buttons.find(b => b.dataset.panel === previous)?.focus();
  }
  function update() {
    const next = useMobileLayout(mode, innerWidth, innerHeight, pointer.matches);
    if (mobile !== next) { show(null, false); mobile = next; }
    root.classList.toggle('mobile-layout', mobile);
    syncInfo();
    if (hint) hint.innerHTML = mobile ? 'One finger: rotate<br>Two fingers: zoom (default)<br>Double tap: centre sphere<br>To pan: View → Two fingers → Pan only' : desktopHint;
  }
  buttons.forEach(b => b.addEventListener('click', () => show(active === b.dataset.panel ? null : b.dataset.panel)));
  ui.querySelector('#mobile-close').addEventListener('click', close);
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && active) close(); });
  select.addEventListener('change', () => {
    mode = select.value;
    try { localStorage.setItem('deepscope.layout', mode); } catch {}
    update();
  });
  function updateViewport() {
    const viewport = window.visualViewport;
    root.style.setProperty('--mobile-keyboard-inset', `${viewport ? Math.max(0, innerHeight - viewport.height - viewport.offsetTop) : 0}px`);
    root.style.setProperty('--mobile-viewport-height', `${viewport?.height || innerHeight}px`);
  }
  window.addEventListener('resize', update);
  window.addEventListener('resize', updateViewport);
  window.visualViewport?.addEventListener('resize', updateViewport);
  window.visualViewport?.addEventListener('scroll', updateViewport);
  updateViewport();
  pointer.addEventListener('change', update);
  // Expand the compact status without changing saved desktop panel settings.
  info?.querySelector('#info-collapse-button')?.addEventListener('click', e => {
    if (!mobile) return;
    e.stopImmediatePropagation();
    const expanded = info.classList.toggle('mobile-info-expanded');
    e.currentTarget.setAttribute('aria-expanded', String(expanded));
    e.currentTarget.setAttribute('aria-label', expanded ? 'Collapse title box' : 'Expand title box');
  }, true);
  document.getElementById('info-warning-button')?.addEventListener('click', () => {
    if (mobile) info.classList.add('mobile-info-expanded');
  });
  for (const id of ['info-header', 'legend-header', 'export-header']) {
    document.getElementById(id)?.addEventListener('pointerdown', e => {
      if (mobile) e.stopImmediatePropagation();
    }, true);
  }
  update();
  return {
    get isMobile() { return mobile; },
    attach(main, camera) {
      // Dataset changes rebuild lil-gui; discard detached old roots and restore fixed panels.
      restore(); gui = main; pov = camera;
      for (const child of gui.children) child.domElement.dataset.mobileSection = 'fields';
      for (const folder of gui.folders) {
        const label = folder._title;
        folder.domElement.dataset.mobileSection = label === 'Dataset' || label === 'Sequence playback' ? 'dataset'
          : /Export|PNG|Video/i.test(label) ? 'export'
          : /View state|Lighting|Appearance|Other visualisation/i.test(label) ? 'view' : 'fields';
      }
      if (mobile) show(active, false);
      syncInfo();
    }
  };
}
