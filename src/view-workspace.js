// View-only history and browser-local presets. No data buffers or dataset paths.
export const NAMED_VIEWS_KEY = 'deepscope.named-views.v1';
const clone = value => JSON.parse(JSON.stringify(value));
const signature = value => {
  if (!value?.params) return JSON.stringify(value);
  // Ignore imperceptible camera damping/roundoff, not scientific field limits.
  const round = n => Math.round(n * 1e7) / 1e7;
  const params = Object.fromEntries(Object.entries(value.params).map(([key,item]) =>
    [key, key.startsWith('camera') && typeof item === 'number' ? round(item) : item]));
  const cameraPose = value.cameraPose && Object.fromEntries(Object.entries(value.cameraPose).map(([key,item]) =>
    [key, Array.isArray(item) ? item.map(round) : typeof item === 'number' ? round(item) : item]));
  return JSON.stringify({...value,params,...(cameraPose ? {cameraPose} : {})});
};
const placementKeys = /^(?:(?:primary|secondary)(?:Native|Physical)Radius|placementUnit)$/;

export function portableView(snapshot, includeFields = true) {
  const result = clone(snapshot);
  for (const key of Object.keys(result.params || {})) {
    if (placementKeys.test(key) || key.startsWith('sequence') || /dataset/i.test(key)
        || (!includeFields && (key.endsWith('Field') || key.startsWith('phiAvg')))) delete result.params[key];
  }
  return result;
}

export function mergeNamedView(current, saved, includeFields = true) {
  const appearance = portableView(saved, includeFields);
  return {...clone(current), ...appearance, params:{...current.params, ...appearance.params}};
}

export function validateView(snapshot) {
  if (!snapshot || snapshot.version !== 2 || !snapshot.params || Array.isArray(snapshot.params)
      || Object.keys(snapshot.params).length > 1000) throw new Error('Expected a DEEPscope version 2 view.');
  for (const [key, value] of Object.entries(snapshot.params)) {
    if (['__proto__', 'constructor', 'prototype'].includes(key)
        || !['number', 'string', 'boolean'].includes(typeof value)
        || (typeof value === 'number' && !Number.isFinite(value))
        || (typeof value === 'string' && value.length > 4096)) throw new Error('Invalid view parameter.');
  }
  return snapshot;
}

export class NamedViews {
  constructor(storage) { this.storage = storage; }
  list() {
    const raw = this.storage.getItem(NAMED_VIEWS_KEY);
    if (!raw) return [];
    return this.parse(raw);
  }
  parse(raw) {
    if (raw.length > 2_000_000) throw new Error('Saved views file exceeds 2 MB.');
    const data = JSON.parse(raw);
    if (data.format !== 'deepscope-named-views' || data.version !== 1 || !Array.isArray(data.views)
        || data.views.length > 100) throw new Error('Invalid named views file (maximum 100 views).');
    const names = new Set();
    return data.views.map(item => {
      const name = String(item?.name || '').trim();
      if (!name || name.length > 80 || names.has(name)) throw new Error('View names must be unique and 1–80 characters long.');
      names.add(name);
      return { name, snapshot: portableView(validateView(item.snapshot)) };
    });
  }
  write(views) {
    const raw = JSON.stringify({format:'deepscope-named-views', version:1, views});
    this.parse(raw);
    // Let quota/privacy failures propagate; never report a save that did not persist.
    this.storage.setItem(NAMED_VIEWS_KEY, raw);
  }
  save(name, snapshot, replace = false) {
    name = name.trim();
    const views = this.list(), index = views.findIndex(view => view.name === name);
    if (index >= 0 && !replace) throw new Error('That name already exists. Use Update selected or choose a new name.');
    const item = {name, snapshot:portableView(validateView(snapshot))};
    if (index < 0) views.push(item); else views[index] = item;
    this.write(views);
    return name;
  }
  rename(oldName, name) {
    name = name.trim();
    const views = this.list(), item = views.find(view => view.name === oldName);
    if (!item) throw new Error('Select a saved view.');
    item.name = name;
    this.write(views);
    return name;
  }
  remove(name) { this.write(this.list().filter(view => view.name !== name)); }
  export() { return JSON.stringify({format:'deepscope-named-views',version:1,views:this.list()}, null, 2); }
  import(raw) {
    const incoming = this.parse(raw), views = this.list(), names = new Set(views.map(view => view.name));
    for (const view of incoming) {
      const base = view.name.slice(0, 68); let n = 2;
      while (names.has(view.name)) view.name = `${base} (${n++})`;
      names.add(view.name); views.push(view);
    }
    this.write(views);
    return incoming.length;
  }
}

export class ViewJournal {
  constructor({capture, apply, identity, ready, limit = 50}) {
    Object.assign(this, {capture, apply, identity, ready, limit});
    this.states = []; this.index = -1; this.key = null; this.busy = false;
  }
  sync() {
    const key = this.identity();
    if (key !== this.key) { this.key = key; this.states = []; this.index = -1; }
  }
  record() {
    if (this.busy || !this.ready()) return;
    this.sync();
    const current = clone(this.capture());
    if (signature(current) === signature(this.states[this.index])) return;
    this.states.splice(this.index + 1);
    this.states.push(current);
    if (this.states.length > this.limit) this.states.shift();
    this.index = this.states.length - 1;
  }
  async restore(target, nextIndex = null) {
    if (this.busy || !this.ready()) throw new Error('Wait for loading, playback or export to finish.');
    this.record();
    const before = clone(this.capture()), key = this.key;
    this.busy = true;
    try {
      await this.apply(clone(target));
      if (this.identity() !== key) throw new Error('The dataset changed while restoring the view.');
      if (nextIndex !== null) this.index = nextIndex;
    } catch (error) {
      if (this.identity() === key) {
        try { await this.apply(before); }
        catch (rollback) { throw new Error(`${error.message} Restoring the preceding view failed: ${rollback.message}`); }
      }
      throw error;
    } finally { this.busy = false; }
    // Capture the actually applied state (some unavailable hidden fields may be skipped).
    if (nextIndex !== null) this.states[this.index] = clone(this.capture());
    else this.record();
  }
  async step(direction) {
    this.record();
    const index = this.index + direction;
    if (index < 0 || index >= this.states.length) throw new Error(`Nothing to ${direction < 0 ? 'undo' : 'redo'} for this dataset.`);
    await this.restore(this.states[index], index);
  }
}

export function validCameraPose(pose) {
  if (!pose || !['position','target','up'].every(key => Array.isArray(pose[key])
      && pose[key].length === 3 && pose[key].every(x => Number.isFinite(x) && Math.abs(x) < 1e9))
      || !Number.isFinite(pose.fov) || !(pose.fov >= 5 && pose.fov <= 120)) return false;
  const d = pose.position.map((x,i) => x - pose.target[i]);
  const cross = [d[1]*pose.up[2]-d[2]*pose.up[1], d[2]*pose.up[0]-d[0]*pose.up[2], d[0]*pose.up[1]-d[1]*pose.up[0]];
  return Math.hypot(...d) > 1e-8 && Math.hypot(...cross) > 1e-10;
}

export function captureGuiFolders(gui, path = '', state = {}) {
  if (!gui) return state;
  state[path] = !gui._closed;
  for (const folder of gui.folders || []) captureGuiFolders(folder, `${path}/${folder._title}`, state);
  return state;
}

export function restoreGuiFolders(gui, state, path = '') {
  if (!gui) return;
  if (Object.hasOwn(state, path)) gui.open(state[path]);
  for (const folder of gui.folders || []) restoreGuiFolders(folder, state, `${path}/${folder._title}`);
}

export function createViewWorkspace({capture, apply, identity, ready, initial, openComparison, storage, onError}) {
  const journal = new ViewJournal({capture, apply, identity, ready}), presets = new NamedViews(storage);
  let last = '', since = 0, interacting = false, panel = null;
  const report = error => onError(error?.message || String(error));
  const run = async action => { try { await action(); refresh(); } catch (error) { report(error); } };
  const refresh = () => {
    if (!panel?.isConnected) return;
    const available = ready(), changed = available && journal.index >= 0 && signature(capture()) !== signature(journal.states[journal.index]);
    panel.querySelector('[data-action="undo"]').disabled = journal.busy || !available || (journal.index < 1 && !changed);
    panel.querySelector('[data-action="redo"]').disabled = journal.busy || !available || changed || journal.index >= journal.states.length - 1;
  };
  document.addEventListener('pointerdown', () => { journal.record(); interacting = true; }, true);
  for (const event of ['pointerup','pointercancel','blur']) window.addEventListener(event, () => { interacting = false; since = performance.now(); });
  const timer = window.setInterval(() => {
    if (!ready() || journal.busy) return;
    const value = signature(capture()), now = performance.now();
    journal.sync();
    if (!journal.states.length) journal.record();
    if (value !== last) { last = value; since = now; }
    else if (!interacting && now - since > 600) journal.record();
    refresh();
  }, 200);
  window.addEventListener('pagehide', () => window.clearInterval(timer), {once:true});
  window.addEventListener('keydown', event => {
    if (event.defaultPrevented || !(event.ctrlKey || event.metaKey) || event.altKey
        || event.target?.closest?.('input,textarea,select,[contenteditable="true"]')) return;
    const key = event.key.toLowerCase();
    if (key !== 'z' && key !== 'y') return;
    event.preventDefault();
    void run(() => journal.step(key === 'y' || event.shiftKey ? 1 : -1));
  });
  const refreshList = selected => {
    if (!panel?.isConnected) return;
    const select = panel.querySelector('select'), previous = selected ?? select.value;
    select.replaceChildren();
    for (const {name} of presets.list()) { const option = document.createElement('option'); option.value = option.textContent = name; select.append(option); }
    if ([...select.options].some(option => option.value === previous)) select.value = previous;
  };
  window.addEventListener('storage', event => { if (event.key === NAMED_VIEWS_KEY) { try { refreshList(); } catch(error) {report(error);} } });
  return {
    journal,
    async runCommand(command) {
      if (command.action === 'undo' || command.action === 'redo') return journal.step(command.action === 'undo' ? -1 : 1);
      if (!ready()) throw new Error('Wait for loading, playback or export to finish.');
      const before = capture();
      const target = command.action === 'reset' ? initial() : {...before,params:{...before.params,...command.patch}};
      if (!target) throw new Error('Load a dataset first.');
      if (command.action === 'apply' && Object.keys(command.patch || {}).some(key => key.startsWith('camera'))) delete target.cameraPose;
      await journal.restore(target);
    },
    mount(parent) {
      const previous = panel ? {name:panel.querySelector('[data-name]').value,
        selected:panel.querySelector('select').value, fields:panel.querySelector('[data-fields]').checked} : null;
      panel = document.createElement('div'); panel.className = 'view-workspace';
      panel.innerHTML = `<div class="view-actions"><button data-action="undo" title="Undo view change (Ctrl/Cmd+Z)">↶ Undo</button><button data-action="redo" title="Redo view change (Ctrl/Cmd+Shift+Z)">↷ Redo</button></div>
        <button data-action="compare">Side-by-side comparison ↗</button>
        <label>View name<input data-name maxlength="80" placeholder="e.g. Temperature sections"></label>
        <button data-action="save">Save new view</button>
        <label>Saved views<select aria-label="Saved views" size="4"></select></label>
        <label class="view-check"><input type="checkbox" data-fields checked> Restore field selections</label>
        <div class="view-actions"><button data-action="load">Load</button><button data-action="update">Update selected</button></div>
        <div class="view-actions"><button data-action="rename">Rename</button><button data-action="delete">Delete</button></div>
        <div class="view-actions"><button data-action="export">Export views</button><button data-action="import">Import views</button></div>
        <input data-file type="file" accept=".json,application/json" hidden>
        <small>Stored in this browser. Views keep the current datasets, frame and physical radius mapping. Export a backup to use them elsewhere.</small>
        <output aria-live="polite"></output>`;
      parent.append(panel);
      const ownPanel = panel, select = panel.querySelector('select'), name = panel.querySelector('[data-name]');
      if (previous) { name.value = previous.name; panel.querySelector('[data-fields]').checked = previous.fields; }
      const notice = text => { ownPanel.querySelector('output').textContent = text; };
      select.addEventListener('change', () => { name.value = select.value; });
      panel.querySelector('[data-file]').addEventListener('change', event => void run(async () => {
        const file = event.target.files[0]; if (!file) return;
        if (file.size > 2_000_000) throw new Error('Saved views file exceeds 2 MB.');
        const count = presets.import(await file.text()); refreshList(); notice(`Imported ${count} views.`); event.target.value = '';
      }));
      panel.addEventListener('click', event => {
        const action = event.target.closest('[data-action]')?.dataset.action; if (!action) return;
        void run(async () => {
          if (action === 'undo' || action === 'redo') { await journal.step(action === 'undo' ? -1 : 1); return; }
          if (action === 'compare') { openComparison(); return; }
          if (action === 'import') { ownPanel.querySelector('[data-file]').click(); return; }
          if (action === 'export') {
            const url = URL.createObjectURL(new Blob([presets.export()], {type:'application/json'}));
            const a = document.createElement('a'); a.href = url; a.download = 'deepscope-named-views.json'; a.click();
            window.setTimeout(() => URL.revokeObjectURL(url), 1000); notice('Exported named views.'); return;
          }
          if (action === 'save' || action === 'update') {
            if (!ready()) throw new Error('Load a dataset and wait for playback or loading to finish.');
            const saved = presets.save(action === 'update' ? select.value : name.value, capture(), action === 'update');
            refreshList(saved); notice(`Saved “${saved}”.`); return;
          }
          const item = presets.list().find(view => view.name === select.value);
          if (!item) throw new Error('Select a saved view.');
          if (action === 'load') { await journal.restore(mergeNamedView(capture(), item.snapshot, ownPanel.querySelector('[data-fields]').checked)); return; }
          if (action === 'rename') { refreshList(presets.rename(item.name, name.value)); notice('Renamed view.'); }
          if (action === 'delete') { presets.remove(item.name); refreshList(); notice(`Deleted “${item.name}”.`); }
        });
      });
      try { refreshList(previous?.selected); } catch(error) { report(error); }
      refresh();
    },
  };
}
