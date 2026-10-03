import { COMMAND_EXAMPLES } from './viewer-commands.js';

export function createCommandBox({ execute, document: doc = document }) {
  const box = doc.createElement('details');
  box.id = 'viewer-command-box';
  box.innerHTML = `<summary>View commands <span>local · free</span></summary>
    <form><label for="viewer-command-input">Describe the view</label>
    <textarea id="viewer-command-input" rows="3" maxlength="1200" placeholder="Show meridional ur, equatorial Br and CMB Br"></textarea>
    <div class="command-actions"><button type="submit">Apply</button><button type="button" data-action="undo">Undo</button><button type="button" data-action="examples">Examples</button></div></form>
    <div class="command-feedback" role="status" aria-live="polite">Commands run in your browser. Open Examples to see supported phrases.</div>
    <div class="command-examples" hidden></div>`;
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
    }
  };
  form.addEventListener('submit', event => { event.preventDefault(); void run(input.value); });
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); void run(input.value); }
    if (event.key === 'Escape') { box.open = false; box.querySelector('summary').focus(); }
  });
  box.querySelector('[data-action="undo"]').addEventListener('click', () => void run('undo'));
  box.querySelector('[data-action="examples"]').addEventListener('click', () => { examples.hidden = !examples.hidden; });
  return { element: box };
}
