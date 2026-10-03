import { COMMAND_EXAMPLES } from './viewer-commands.js';

export function createCommandBox({ execute, getSettings = () => [], document: doc = document }) {
  const box = doc.createElement('details');
  box.id = 'viewer-command-box';
  box.innerHTML = `<summary>View commands <span>local · free</span></summary>
    <form><label for="viewer-command-input">Describe the view</label>
    <textarea id="viewer-command-input" rows="3" maxlength="1200" placeholder="Show meridional ur, equatorial Br and CMB Br"></textarea>
    <div class="command-actions"><button type="submit">Apply</button><button type="button" data-action="undo">Undo</button><button type="button" data-action="reset">Reset view</button><button type="button" data-action="examples">Examples</button><button type="button" data-action="settings">All settings</button></div></form>
    <div class="command-feedback" role="status" aria-live="polite">Commands run in your browser. Open Examples to see supported phrases.</div>
    <div class="command-examples" hidden></div>
    <div class="command-settings" hidden>
      <label>Find a setting or field<input type="search" class="command-setting-search" placeholder="e.g. colour, camera, Br, phi" /></label>
      <label>Setting<select class="command-setting-list" size="5"></select></label>
      <label>Value<select class="command-setting-choice" hidden></select><input class="command-setting-value" type="text" /></label>
      <div class="command-setting-hint"></div><button type="button" data-action="insert">Use command</button>
      <small>View settings only. Use the existing buttons to load data, run playback or export.</small>
    </div>`;
  doc.body.appendChild(box);
  const form = box.querySelector('form'), input = box.querySelector('textarea');
  const feedback = box.querySelector('.command-feedback'), examples = box.querySelector('.command-examples');
  const buttons = [...box.querySelectorAll('button')];
  for (const example of COMMAND_EXAMPLES) {
    const button = doc.createElement('button');
    button.type = 'button'; button.textContent = example;
    button.addEventListener('click', () => { input.value = example; input.focus(); });
    examples.appendChild(button);
  }
  const catalogue = box.querySelector('.command-settings');
  const search = box.querySelector('.command-setting-search');
  const list = box.querySelector('.command-setting-list');
  const choices = box.querySelector('.command-setting-choice');
  const valueInput = box.querySelector('.command-setting-value');
  const hint = box.querySelector('.command-setting-hint');
  let settings = [];
  const selected = () => settings.find(s => s.key === list.value);
  const showValue = () => {
    const setting = selected();
    choices.replaceChildren();
    if (!setting) { hint.textContent = 'No matching setting. Try another search.'; return; }
    const values = setting.options || (setting.type === 'boolean' ? [{label:'on',value:true},{label:'off',value:false}] : null);
    choices.hidden = !values; valueInput.hidden = Boolean(values);
    if (values) {
      for (const item of values) {
        const option = doc.createElement('option'); option.value = String(item.value); option.textContent = item.label;
        choices.appendChild(option);
      }
      choices.value = String(setting.value);
      if (choices.selectedIndex < 0 && choices.options.length) choices.selectedIndex = 0;
    } else valueInput.value = String(setting.value);
    hint.textContent = setting.type === 'number'
      ? `${setting.integer ? 'Integer' : 'Number'}${setting.min !== undefined ? ` ≥ ${setting.min}` : ''}${setting.max !== undefined ? ` ≤ ${setting.max}` : ''}`
      : values ? `${values.length} available choices` : setting.color ? 'Hex colour, e.g. #3366cc' : 'Text (quoted automatically)';
  };
  const refreshSettings = () => {
    const oldKey = list.value, query = search.value.toLowerCase();
    settings = getSettings(); list.replaceChildren();
    for (const setting of settings) {
      const text = [setting.label, setting.key, ...(setting.aliases || []), ...(setting.options || []).map(o => o.label)].join(' ').toLowerCase();
      if (query && !text.includes(query)) continue;
      const option = doc.createElement('option'); option.value = setting.key; option.textContent = setting.label;
      list.appendChild(option);
    }
    if ([...list.options].some(o=>o.value===oldKey)) list.value = oldKey;
    showValue();
  };
  search.addEventListener('input', refreshSettings); list.addEventListener('change', showValue);
  box.querySelector('[data-action="settings"]').addEventListener('click', () => {
    catalogue.hidden = !catalogue.hidden;
    if (!catalogue.hidden) { refreshSettings(); search.focus(); }
  });
  box.querySelector('[data-action="insert"]').addEventListener('click', () => {
    const setting = selected(); if (!setting) return;
    const raw = choices.hidden ? valueInput.value : choices.value;
    if (!choices.hidden && choices.selectedIndex < 0) return;
    input.value = `set ${JSON.stringify(setting.label)} to ${setting.type === 'string' ? JSON.stringify(raw) : raw}`;
    input.focus();
  });
  const run = async text => {
    if (!text.trim()) { input.focus(); return; }
    for (const button of buttons) button.disabled = true;
    input.disabled = true; box.setAttribute('aria-busy', 'true');
    feedback.classList.remove('error'); feedback.textContent = 'Applying view…';
    try {
      const result = await execute(text);
      if (result.help) { examples.hidden = false; feedback.textContent = 'Choose an example, edit it, then Apply. Combine instructions with commas or “and”.'; }
      else feedback.textContent = result.message;
    } catch (error) {
      feedback.classList.add('error'); feedback.textContent = error.message;
    } finally {
      for (const button of buttons) button.disabled = false;
      input.disabled = false; box.removeAttribute('aria-busy');
      if (!catalogue.hidden) refreshSettings();
    }
  };
  form.addEventListener('submit', event => { event.preventDefault(); void run(input.value); });
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); void run(input.value); }
    if (event.key === 'Escape') { box.open = false; box.querySelector('summary').focus(); }
  });
  box.querySelector('[data-action="reset"]').addEventListener('click', () => void run('reset view'));
  box.querySelector('[data-action="undo"]').addEventListener('click', () => void run('undo'));
  box.querySelector('[data-action="examples"]').addEventListener('click', () => { examples.hidden = !examples.hidden; });
  return { element: box };
}
