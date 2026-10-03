import { COMMAND_EXAMPLES } from './viewer-commands.js';
import { settingName } from './command-settings.js';

export const COMMAND_COLOURS = ['blue','red','green','white','black','yellow','orange','purple','cyan','magenta','pink','grey'];
const comparable = text => String(text).toLowerCase().replace(/meriodional|merdional/g,'meridional').replace(/\s+/g,' ').trimStart();
const fieldText = text => /^[\w:.-]+$/.test(text) ? text : JSON.stringify(text);
const valueText = value => typeof value === 'string' ? JSON.stringify(value) : String(value);

// Only split actions outside quotes; the "and" between levels/colours stays put.
export function commandCompletionStart(text) {
  let start = 0, quoted = false, escaped = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (escaped) { escaped = false; continue; }
    if (quoted && c === '\\') { escaped = true; continue; }
    if (c === '"') { quoted = !quoted; continue; }
    if (quoted) continue;
    if (c === ';' || c === ',') start = i + 1;
    const join = /^(?:and|then)\s+(?=(?:show|hide|remove|set|change|open|close|reset|use|display)\b)/i.exec(text.slice(i));
    if (join && (i === 0 || /\s/.test(text[i-1]))) { start = i + join[0].length; i = start - 1; }
  }
  while (/\s/.test(text[start] || '') && start < text.length) start++;
  return start;
}

export function commandSuggestions(input, settings = [], limit = 8) {
  const text = String(input), start = commandCompletionStart(text), prefix = text.slice(0,start), clause = text.slice(start);
  const query = comparable(clause), results = [], seen = new Set();
  const add = (command, hint = '') => {
    const value = prefix + command;
    if (results.length >= limit || seen.has(value) || comparable(command) === query) return;
    seen.add(value); results.push({value, label:command, hint});
  };
  const palette = settings.find(s=>s.key==='radialColormap')?.options || [];
  const colourSuffix = /^(.*\bisosurfaces?\b.*?\bin\s+)([\w#-]*)(?:\s+and\s+([\w#-]*))?$/i.exec(clause);
  if (colourSuffix) {
    const stem = colourSuffix[3] === undefined ? colourSuffix[1] : `${colourSuffix[1]}${colourSuffix[2]} and `;
    const partial = colourSuffix[3] ?? colourSuffix[2];
    for (const color of COMMAND_COLOURS) if (color.startsWith(partial.toLowerCase())) add(stem+color,'Isosurface colour');
    return results;
  }
  const paletteSuffix = /^(.*\s(?:using|with colou?r ?map|with colou?rbar)\s+)([\w -]*)$/i.exec(clause);
  if (paletteSuffix) {
    for (const o of palette) if (comparable(o.value).startsWith(comparable(paletteSuffix[2]))) add(paletteSuffix[1]+o.value,'Colour map');
    return results;
  }
  const setter = /^(?:set|change)\s+(.+?)\s+to\s+(.*)$/i.exec(clause);
  if (setter) {
    let target = setter[1];
    try { if (target.startsWith('"')) target = JSON.parse(target); } catch { return []; }
    const found = settings.filter(s=>[s.key,s.label,...(s.aliases||[])].some(n=>settingName(n)===settingName(target)));
    const stem = clause.slice(0,clause.length-setter[2].length);
    if (found.length === 1) {
      const s=found[0];
      const options = s.options || (s.type==='boolean' ? [{value:'on'},{value:'off'}]
        : s.color ? COMMAND_COLOURS.map(value=>({value})) : setter[2] ? [] : [{value:s.value}]);
      const partial = setter[2].replace(/^"/, '').toLowerCase();
      for (const o of options) if (String(o.value).toLowerCase().startsWith(partial)) {
        add(stem+(s.type==='string'?JSON.stringify(String(o.value)):String(o.value)),s.label);
      }
    } else if (/^(?:meridional(?: [12])?|equatorial(?: [12])?|cmb|icb|radial|mollweide|earth|field lines) colou?r(?:bar| ?map)$/i.test(target)) {
      for(const o of palette) if(comparable(o.value).startsWith(comparable(setter[2])))add(stem+o.value,'Colour map');
    }
    return results;
  }
  if (/^(?:set|change)(?:\s|$)/i.test(clause)) {
    const words = query.replace(/^(?:set|change)\s*/, '').replace(/"/g,'').trim().split(/\s+/).filter(Boolean);
    for (const s of settings) {
      const haystack=comparable([s.key,s.label,...(s.aliases||[])].join(' '));
      if (words.every(word=>haystack.includes(word))) add(`set ${JSON.stringify(s.label)} to `,'Choose a value');
    }
    return results;
  }
  const displays = [
    ['meridional','meridianField'],['meridional 2','meridian2Field'],
    ['equatorial','equatorField'],['equatorial 2','equator2Field'],
    ['CMB','cmbField'],['ICB','icbField'],['Mollweide','mollweideField'],
  ];
  for(const [display,key] of displays) {
    for(const option of settings.find(s=>s.key===key)?.options || []) {
      const command=`show ${display} ${fieldText(option.value)}`;
      if(comparable(command).startsWith(query))add(command,'Loaded field');
    }
  }
  for(const option of settings.find(s=>s.key==='isoField')?.options || []) {
    const command=`show isosurface of ${fieldText(option.value)} at `;
    if(comparable(command).startsWith(query))add(command,'Enter an isovalue');
  }
  for(const example of [...COMMAND_EXAMPLES,'remove field lines','hide CMB','hide isosurfaces','undo','reset view','help']) {
    if(comparable(example).startsWith(query))add(example);
  }
  return results;
}
