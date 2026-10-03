import { parseSettingCommand, validateCommandRanges, commandColor } from './command-settings.js';
// A deliberately bounded, local grammar. No network, eval, or generated code.
export const COMMAND_EXAMPLES = [
  'Show meridional ur, equatorial Br, CMB Br, and open one northern octant',
  'Show meridional 2 temperature from dataset 2',
  'Show Br at radius 0.7 with -1 and +1 using viridis',
  'Set radial colourbar to blue-white-red',
  'Show Mollweide Br',
  'Show isosurface of ur at -100',
  'Remove field lines; show isosurface of ur at +100 and -100 in blue and red',
  'Open northern octant between 0 and 90 degrees',
  'Set all colour scales to minmax',
  'Hide field lines and show time',
  'Set camera azimuth to 45',
  'Reset view',
];
const norm = text => String(text).toLowerCase().trim()
  .replace(/meriodional|merdional|meridian/g, 'meridional')
  .replace(/cross[ -]?sections?|slices?|cuts?/g, ' ')
  .replace(/−/g, '-')
  .replace(/iso[ -]surfaces?/g, 'isosurface')
  .replace(/\bu_r\b/g, 'ur').replace(/\bb_r\b/g, 'br')
  .replace(/\s+/g, ' ').trim();
const aliases = { 'radial velocity': 'ur', 'radial magnetic field': 'Br',
  'temperature': 'T', 'composition': 'C', 'azimuthal velocity': 'up',
  'latitudinal velocity': 'ut', 'magnetic strength': 'Babs', 'speed': 'Uabs' };
const slots = {
  meridional: ['meridian', 'showMeridian'], 'meridional 2': ['meridian2', 'showMeridian2'],
  equatorial: ['equator', 'showEquator'], 'equatorial 2': ['equator2', 'showEquator2'],
  mollweide: ['mollweide', 'showMollweide'], earth: ['earth', 'showEarthSurface'],
  cmb: ['cmb', 'showCMB'], icb: ['icb', 'showICB'], radial: ['radial', 'showRadialSurface'],
};
const mod = n => ((n % 360) + 360) % 360;
const number = '(-?\\d+(?:\\.\\d+)?)';

function commandField(requested, available, dataset, label) {
  const wanted = norm(aliases[requested.toLowerCase()] || requested.replace(/^field /, ''));
  const candidates = available.filter(f => (dataset === null || f.dataset === dataset)
    && (norm(f.name) === wanted || norm(f.value) === wanted));
  const field = candidates.find(f => f.dataset === (dataset || 1)) || candidates[0];
  if (!field) throw new Error(`Field “${requested}” is unavailable for ${label}${dataset ? ` in dataset ${dataset}` : ''}. Available: ${available.slice(0, 20).map(f => `${f.name} (dataset ${f.dataset})`).join(', ')}.`);
  return field;
}
const isoNumber = '[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:e[+-]?\\d+)?';

export function parseViewerCommand(input, { fields = {}, params = {}, cameraAzimuth = 0, settings = [], colormaps = [] } = {}) {
  const quotes = [];
  const protectedInput = String(input).replace(/"(?:\\.|[^"\\])*"/g, value => {
    quotes.push(JSON.parse(value)); return `quotedtoken${quotes.length - 1}`;
  });
  const restore = value => value.replace(/quotedtoken(\d+)/g, (_, index) => quotes[Number(index)] ?? _);
  let text = norm(protectedInput).replace(/[.!?]+$/, '').replace(/^please\s+/, '');
  if (!text || String(input).length > 1200) throw new Error('Enter a command of 1–1200 characters.');
  if (/^reset(?: (?:the )?view)?$/.test(text)) return { action: 'reset' };
  if (/^(undo|help|examples)$/.test(text)) return { action: text === 'undo' ? 'undo' : 'help' };
  // Preserve the "and" in an explicit longitude interval before splitting clauses.
  text = text.replace(new RegExp(`between ${number} and ${number}`, 'g'), 'between $1 to $2');
  text = text.replace(/\bwith (?:a )?(?:sphere )?open\b/g, '; open');
  text = text.replace(new RegExp(`((?:with|range(?: to)?) ${isoNumber}) and (${isoNumber})(?=\\s|$)`, 'g'), '$1 to $2');
  // Keep paired levels and their ordered colours together before splitting actions.
  const isoColor = '(?:#[a-f0-9]+|[a-z][a-z0-9_-]*)';
  text = text.replace(new RegExp(`(\\bisosurfaces? [^;,]+? at (?:value )?${isoNumber}) and (${isoNumber})(?=\\s|$)`, 'g'), '$1 isopair $2');
  text = text.replace(new RegExp(`(\\bisosurfaces? [^;,]+? at (?:value )?${isoNumber}(?: isopair ${isoNumber})? in ${isoColor}) and ((?!(?:show|hide|remove|set|change|open|close|reset|use|display)\\b)${isoColor})(?=\\s|$|[,;])`, 'g'), '$1 isocolor $2');
  const clauses = text.split(/\s*(?:[,;]|\band\b|\bthen\b)\s*/).filter(Boolean);
  const patch = {}, descriptions = [];
  let opening = null, isoField = null;
  function setStyle(prefix, palette, limits) {
    if (palette) {
      const canonical = colormaps.find(name => norm(name).replace(/[ -]/g,'') === norm(palette).replace(/[ -]/g,''));
      if (!canonical) throw new Error(`Unknown colour map “${palette}”. Choose: ${colormaps.join(', ')}.`);
      patch[`${prefix}Colormap`] = canonical;
    }
    if (limits) {
      if (!limits.every(Number.isFinite) || limits[0] >= limits[1]) throw new Error('The colour-range minimum must be smaller than its maximum.');
      patch[`${prefix}Scale`] = 'manual';
      patch[`${prefix}Min`] = limits[0]; patch[`${prefix}Max`] = limits[1];
    }
  }
  for (const original of clauses) {
    const setting = parseSettingCommand(original, settings, restore);
    if (setting) {
      patch[setting.key] = setting.value;
      descriptions.push(setting.description);
      continue;
    }
    let clause = original.replace(/^(?:show me|show|display|enable|change|set|use)\s+/, '')
      .replace(/^the\s+/, '');
    const hidden = /^(hide|disable|remove)\s+/.test(clause);
    if (hidden) clause = clause.replace(/^(hide|disable|remove)\s+(?:the\s+)?/, '');
    const visibility = { 'field lines': 'showFieldLines', 'magnetic field lines': 'showFieldLines',
      axes: 'showAxes', time: 'showSimulationTime', 'simulation time': 'showSimulationTime' };
    if (visibility[clause]) {
      patch[visibility[clause]] = !hidden;
      descriptions.push(`${hidden ? 'Hide' : 'Show'} ${clause}`); continue;
    }
    if (!hidden && /^(?:close (?:the )?(?:sphere|opening)|full sphere)$/.test(clause)) {
      if (opening) throw new Error('Choose either an open octant or a closed sphere in one command.');
      patch.cmbClipWithMeridian = false; patch.cmbClipMode = 'none';
      descriptions.push('Close the surface opening'); continue;
    }
    if (!hidden && clause.startsWith('open ')) {
      const match = /^(?:open )(?:(?:a |the )?sphere )?(?:(?:for )?(?:one |an? |1\/8(?:th)? |one eighth |1\/8 of (?:the )?)?)(north(?:ern)?|south(?:ern)?)(?: hemisphere)?(?: octant)?(?: between (-?\d+(?:\.\d+)?) to (-?\d+(?:\.\d+)?)(?: degrees|°)?)?$/.exec(clause);
      if (!match) throw new Error('Use “open northern octant” or “open northern octant between 0 and 90 degrees”.');
      const start = match[2] === undefined ? Math.floor(mod(cameraAzimuth) / 90) * 90 : mod(Number(match[2]));
      const end = match[3] === undefined ? mod(start + 90) : mod(Number(match[3]));
      if (Math.abs(mod(end - start) - 90) > 1e-8) throw new Error('An octant opening must span exactly 90° in longitude.');
      if (patch.cmbClipMode === 'none') throw new Error('Choose either an open octant or a closed sphere in one command.');
      if (opening) throw new Error('Specify one octant opening per command.');
      opening = { start, end, north: match[1].startsWith('north') }; continue;
    }
    const scale = /^(?:all )?colou?r scales? (?:to )?(min[–-]?max|symmetric)$/.exec(clause);
    if (!hidden && scale) {
      const value = scale[1] === 'symmetric' ? 'symmetric' : 'minmax';
      for (const slot of ['cmb', 'icb', 'radial', 'earth', 'equator', 'equator2', 'meridian', 'meridianLeft', 'meridian2', 'meridian2Left', 'mollweide']) patch[`${slot}Scale`] = value;
      // Field-line strength has no signed symmetric scale.
      if (value === 'minmax') patch.lineScale = value;
      descriptions.push(`Surface and slice colour scales: ${value}`); continue;
    }
    let dataset = null;
    clause = clause.replace(/\s+(?:from |using )?dataset ([12])$/, (_, d) => { dataset = Number(d); return ''; });
    let palette = null, limits = null;
    clause = clause.replace(/\s+(?:using|with colou?rmap|with colou?r map|with colou?rbar) (.+)$/, (_, name) => { palette = restore(name); return ''; });
    clause = clause.replace(new RegExp(`\\s+with (${isoNumber}) to (${isoNumber})$`), (_, low, high) => { limits = [Number(low), Number(high)]; return ''; });
    const style = /^(meridional(?: [12])?|equatorial(?: [12])?|cmb|icb|radial|mollweide|earth|field lines) (colou?rbar|colou?r ?map|colou?r scale|range) (?:to )?(.+)$/.exec(clause);
    if (!hidden && style) {
      const prefix = style[1] === 'field lines' ? 'line' : slots[style[1].replace(/ 1$/, '')][0];
      if (palette || limits) throw new Error('Specify one colour setting per instruction.');
      if (style[2] === 'range') {
        const pair = new RegExp(`^(${isoNumber}) to (${isoNumber})$`).exec(style[3]);
        if (!pair) throw new Error('Use “set radial range to -1 and +1”.');
        limits = [Number(pair[1]),Number(pair[2])];
      } else if (/scale/.test(style[2])) {
        if (!['minmax','min-max','symmetric','manual'].includes(style[3])) throw new Error('Colour scale must be minmax, symmetric or manual.');
        if (prefix === 'line' && style[3] === 'symmetric') throw new Error('Field-line strength supports minmax or manual.');
        patch[`${prefix}Scale`] = style[3].replace('min-max','minmax');
      } else palette = restore(style[3]);
      setStyle(prefix, palette, limits);
      descriptions.push(`${style[1]} ${style[2]}: ${restore(style[3])}`); continue;
    }
    if (/^isosurfaces?(?: |$)/.test(clause)) {
      if (hidden && /^isosurfaces?$/.test(clause) && dataset === null) {
        patch.showIsosurfaces = false; descriptions.push('Hide isosurfaces'); continue;
      }
      const iso = new RegExp(`^isosurfaces? (?:of |for )?(.+?) at (?:value )?(${isoNumber})(?: isopair (${isoNumber}))?(?: in (${isoColor})(?: isocolor (${isoColor}))?)?$`).exec(clause);
      if (hidden || !iso) throw new Error('Use “show isosurface of ur at +100 and -100 in blue and red” or “hide isosurfaces”.');
      const values = [iso[2], ...(iso[3] === undefined ? [] : [iso[3]])].map(Number);
      if (!values.every(Number.isFinite)) throw new Error('The isosurface values must be finite.');
      if (palette || limits) throw new Error('Isosurfaces use positive/negative colours, not a colourbar. Choose these in All settings.');
      const colors = [iso[4],iso[5]].filter(value => value !== undefined).map(restore);
      if (colors.length > values.length) throw new Error('Specify one colour per isosurface level, in the same order.');
      const parsedColors = colors.map(color => commandColor(color));
      const field = commandField(restore(iso[1]), fields.iso || [], dataset, 'isosurface');
      if (isoField && isoField !== field.value) throw new Error('The viewer supports one isosurface field at a time. Use the same field for both levels.');
      if (!isoField) { patch.showIsoPositive = false; patch.showIsoNegative = false; }
      isoField = field.value;
      patch.isoField = field.value; patch.showIsosurfaces = true;
      for (const [i,value] of values.entries()) {
        const sign = value < 0 ? 'Negative' : 'Positive';
        if (patch[`showIso${sign}`] && patch[`iso${sign}Value`] !== value) {
          throw new Error('Use at most one negative and one nonnegative isosurface level per command.');
        }
        patch[`showIso${sign}`] = true;
        patch[`iso${sign}Value`] = value;
        const color = parsedColors.length === 1 ? parsedColors[0] : parsedColors[i];
        if (color) patch[`iso${sign}Color`] = color;
        descriptions.push(`Show isosurface: ${field.name} = ${value} (dataset ${field.dataset})${color ? ` in ${colors.length === 1 ? colors[0] : colors[i]}` : ''}`);
      }
      continue;
    }
    let radius = null;
    clause = clause.replace(new RegExp(`(?:at )?radius ${number}(?:\\s*r\\/ro)?$`), (_, r) => { radius = Number(r); return 'radial'; }).trim();
    let match = /^(meridional(?: [12])?|equatorial(?: [12])?|cmb|icb|radial|mollweide|earth)(?:\s+(?:field\s+)?(?:of\s+|to\s+)?(.+))?$/.exec(clause);
    if (!match) {
      const reversed = /^(.+?) (?:at|on|in|for) (?:the )?(meridional(?: [12])?|equatorial(?: [12])?|cmb|icb|radial|mollweide|earth)$/.exec(clause);
      if (reversed) match = [reversed[0], reversed[2], reversed[1]];
      else if (radius !== null) {
        const radial = /^(.+?)\s+radial$/.exec(clause);
        if (radial) match = [radial[0], 'radial', radial[1]];
      }
    }
    if (!match) throw new Error(`Unrecognised instruction: “${original}”. Use Examples for supported commands; nothing was changed.`);
    const label = match[1].replace(/ 1$/, ''), [slot, show] = slots[label];
    if (hidden && (match[2] || dataset !== null || radius !== null || palette || limits)) throw new Error(`Use “hide ${label}” without a field or position.`);
    const available = fields[slot] || [];
    if (!hidden && !available.length) throw new Error(`No fields are available for ${label} in the loaded datasets.`);
    patch[show] = !hidden;
    let field = null;
    if (!hidden && (match[2] || dataset !== null)) {
      const requested = restore((match[2] || params[`${slot}Field`] || '').trim());
      field = commandField(requested, available, dataset, label);
      patch[`${slot}Field`] = field.value;
      if (slot.startsWith('meridian')) {
        patch[`${slot}LeftField`] = field.value;
        patch[`${slot}IndependentSides`] = false;
      }
    }
    if (slot === 'earth' && field) patch.earthDisplayMode = 'magnetic';
    setStyle(slot, palette, limits);
    if (radius !== null) {
      if (radius < 0 || radius > 1) throw new Error('Radius must lie between 0 and 1 in r/ro.');
      patch.radialSurfaceRadiusRo = radius;
    }
    descriptions.push(`${hidden ? 'Hide' : 'Show'} ${label}${field ? `: ${field.name} (dataset ${field.dataset})` : ''}${radius !== null ? ` at r/ro=${radius}` : ''}${limits ? `; range ${limits[0]} to ${limits[1]}` : ''}${palette ? `; colour map ${palette}` : ''}`);
  }
  if (opening) {
    const { start, end, north } = opening;
    if (patch.showMeridian === false && patch.showMeridian2 === false) throw new Error('Keep at least one meridional cut enabled to define the opening.');
    if (!(fields.meridian || []).length) throw new Error('An octant opening requires a dataset with volume fields for a meridional cut.');
    // Existing clipping uses the two meridians (or a perpendicular second plane).
    const useSecond = patch.showMeridian === false;
    if (useSecond) { patch.showMeridian2 = true; patch.meridian2PhiDeg = start; }
    else {
      patch.showMeridian = true; patch.meridianPhiDeg = start;
      patch.meridian2PhiDeg = end;
    }
    patch.cmbClipWithMeridian = true; patch.cmbClipMode = 'selected-eight-quarters';
    for (const h of ['N', 'S']) for (let i = 1; i <= 4; i++) patch[`quarter${h}${i}`] = true;
    const bounds = [start, end, mod(start + 180), mod(end + 180)].sort((a, b) => a - b);
    patch[`quarter${north ? 'N' : 'S'}${bounds.indexOf(start) + 1}`] = false;
    descriptions.push(`Open ${north ? 'northern' : 'southern'} surface octant ${start}°–${end === 0 ? 360 : end}°; align meridional planes to its edges`);
  }
  if (!Object.keys(patch).length) throw new Error('No supported viewer action was found.');
  for (const prefix of ['meridian','meridian2']) {
    if (Object.keys(patch).some(key=>key.startsWith(`${prefix}Left`)) && !(`${prefix}IndependentSides` in patch)) {
      patch[`${prefix}IndependentSides`] = true;
    }
  }
  validateCommandRanges(patch, params);
  return { action: 'apply', patch, descriptions };
}

// Keep undo snapshots tied to the loaded data and roll back failed updates.
export function createCommandHistory({ capture, apply, identity, ready, initial = () => null }) {
  let history = [], dataset = null, busy = false;
  return {
    async run(command) {
      if (busy) throw new Error('A command is already running.');
      ready();
      const current = identity();
      if (dataset !== current) { history = []; dataset = current; }
      const before = capture();
      const target = command.action === 'undo' ? history.at(-1) : command.action === 'reset' ? initial() : { ...before, params: { ...before.params, ...command.patch } };
      if (!target) throw new Error(command.action === 'reset' ? 'No initial view is available; open a dataset first.' : 'Nothing to undo for this dataset.');
      busy = true;
      try {
        await apply(target);
        if (identity() !== current) throw new Error('Dataset changed while applying the command.');
        if (command.action === 'undo') history.pop();
        else { history.push(before); if (history.length > 20) history.shift(); }
      } catch (error) {
        if (identity() === current) {
          try { await apply(before); }
          catch (rollback) { throw new Error(`${error.message} Restoring the previous view also failed: ${rollback.message}`); }
        }
        throw error;
      } finally { busy = false; }
    },
  };
}
