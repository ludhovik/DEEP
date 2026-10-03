// Typed settings supplied by the viewer, never executable text.
export const settingName = text => String(text).toLowerCase().replace(/colou?r/g, 'color')
  .replace(/meridional|meridian/g, 'meridian').replace(/equatorial/g, 'equator')
  .replace(/[^a-z0-9φ]+/g, ' ').trim().replace(/\s+/g, ' ');

export function commandColor(raw, label = 'Isosurface colour') {
  const named = {red:'#ff0000',blue:'#0000ff',white:'#ffffff',black:'#000000',green:'#008000',yellow:'#ffff00',orange:'#ffa500',purple:'#800080',grey:'#808080',gray:'#808080',cyan:'#00ffff',magenta:'#ff00ff',pink:'#ffc0cb',brown:'#a52a2a',navy:'#000080',teal:'#008080',lime:'#00ff00'};
  let value = named[String(raw).toLowerCase()] || String(raw);
  if (/^#[0-9a-f]{3}$/i.test(value)) value = '#' + [...value.slice(1)].map(x=>x+x).join('');
  if (!/^#[0-9a-f]{6}$/i.test(value)) throw new Error(`${label}: unknown colour “${raw}”. Use a named colour such as blue/red or a hex colour such as #3366cc.`);
  return value;
}

export function parseSettingCommand(clause, settings, restore = text => text) {
  const match = /^(?:set|change) (.+?) to (.+)$/.exec(clause);
  if (!match) return null;
  const requested = settingName(restore(match[1]));
  const matches = settings.filter(s => [s.key, s.label, ...(s.aliases || [])]
    .some(name => settingName(name) === requested));
  if (!matches.length) return null;
  if (matches.length > 1) throw new Error(`Ambiguous setting. Use its full name from All settings: ${matches.map(s => s.label).join('; ')}.`);
  const setting = matches[0], raw = restore(match[2]).trim();
  let value;
  if (setting.options) {
    if (!setting.options.length) throw new Error(`${setting.label}: no choices are available for this dataset.`);
    const choice = setting.options.find(o => settingName(o.label) === settingName(raw)
      || String(o.value).toLowerCase() === raw.toLowerCase());
    if (!choice) throw new Error(`${setting.label}: choose ${setting.options.map(o => o.label).join(', ')}.`);
    value = choice.value;
  } else if (setting.type === 'boolean') {
    if (!/^(true|false|on|off|yes|no|show|hide|enabled|disabled)$/i.test(raw)) throw new Error(`${setting.label}: use on or off.`);
    value = /^(true|on|yes|show|enabled)$/i.test(raw);
  } else if (setting.type === 'number') {
    if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(raw)) throw new Error(`${setting.label}: enter a number.`);
    value = Number(raw);
    if (!Number.isFinite(value) || value < (setting.min ?? -Infinity) || value > (setting.max ?? Infinity)
      || (setting.integer && !Number.isInteger(value))) {
      throw new Error(`${setting.label}: use ${setting.integer ? 'an integer' : 'a finite number'} between ${setting.min ?? '−∞'} and ${setting.max ?? '∞'}.`);
    }
  } else {
    value = raw;
    if (setting.color) value = commandColor(raw, setting.label);
  }
  return { key: setting.key, value, description: `${setting.label}: ${raw}` };
}

export function validateCommandRanges(patch, params) {
  const state = {...params,...patch};
  for (const key of Object.keys(state)) {
    if (!key.endsWith('Scale') || state[key] !== 'manual') continue;
    const prefix = key.slice(0,-5), lo = `${prefix}Min`, hi = `${prefix}Max`;
    if (![key,lo,hi].some(k=>k in patch)) continue;
    if (!Number.isFinite(state[lo]) || !Number.isFinite(state[hi]) || state[lo] >= state[hi]) {
      throw new Error(`${prefix}: the colour-range minimum must be smaller than its maximum. Set both values in one command.`);
    }
  }
}
