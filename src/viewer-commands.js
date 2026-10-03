// A deliberately bounded, local grammar. No network, eval, or generated code.
export const COMMAND_EXAMPLES = [
  'Show meridional ur, equatorial Br, CMB Br, and open one northern octant',
  'Show meridional 2 temperature from dataset 2',
  'Show Br at radius 0.7',
  'Open northern octant between 0 and 90 degrees',
  'Set all colour scales to minmax',
  'Hide field lines and show time',
];
const norm = text => String(text).toLowerCase().trim()
  .replace(/meriodional|merdional|meridian/g, 'meridional')
  .replace(/cross[ -]?sections?|slices?|cuts?/g, ' ')
  .replace(/\bu_r\b/g, 'ur').replace(/\bb_r\b/g, 'br')
  .replace(/\s+/g, ' ').trim();
const aliases = { 'radial velocity': 'ur', 'radial magnetic field': 'Br',
  'temperature': 'T', 'composition': 'C', 'azimuthal velocity': 'up',
  'latitudinal velocity': 'ut', 'magnetic strength': 'Babs', 'speed': 'Uabs' };
const slots = {
  meridional: ['meridian', 'showMeridian'], 'meridional 2': ['meridian2', 'showMeridian2'],
  equatorial: ['equator', 'showEquator'], 'equatorial 2': ['equator2', 'showEquator2'],
  cmb: ['cmb', 'showCMB'], icb: ['icb', 'showICB'], radial: ['radial', 'showRadialSurface'],
};
const mod = n => ((n % 360) + 360) % 360;
const number = '(-?\\d+(?:\\.\\d+)?)';

export function parseViewerCommand(input, { fields = {}, params = {}, cameraAzimuth = 0 } = {}) {
  let text = norm(input).replace(/[.!?]+$/, '').replace(/^please\s+/, '');
  if (!text || text.length > 1200) throw new Error('Enter a command of 1–1200 characters.');
  if (/^(undo|help|examples)$/.test(text)) return { action: text === 'undo' ? 'undo' : 'help' };
  // Preserve the "and" in an explicit longitude interval before splitting clauses.
  text = text.replace(new RegExp(`between ${number} and ${number}`, 'g'), 'between $1 to $2');
  text = text.replace(/\bwith (?:a )?(?:sphere )?open\b/g, '; open');
  const clauses = text.split(/\s*(?:[,;]|\band\b|\bthen\b)\s*/).filter(Boolean);
  const patch = {}, descriptions = [];
  let opening = null;
  for (const original of clauses) {
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
    let radius = null;
    clause = clause.replace(new RegExp(`(?:at )?radius ${number}(?:\\s*r\\/ro)?$`), (_, r) => { radius = Number(r); return 'radial'; }).trim();
    let match = /^(meridional(?: [12])?|equatorial(?: [12])?|cmb|icb|radial)(?:\s+(?:field\s+)?(?:of\s+|to\s+)?(.+))?$/.exec(clause);
    if (!match) {
      const reversed = /^(.+?) (?:at|on|in|for) (?:the )?(meridional(?: [12])?|equatorial(?: [12])?|cmb|icb|radial)$/.exec(clause);
      if (reversed) match = [reversed[0], reversed[2], reversed[1]];
      else if (radius !== null) {
        const radial = /^(.+?)\s+radial$/.exec(clause);
        if (radial) match = [radial[0], 'radial', radial[1]];
      }
    }
    if (!match) throw new Error(`Unrecognised instruction: “${original}”. Use Examples for supported commands; nothing was changed.`);
    const label = match[1].replace(/ 1$/, ''), [slot, show] = slots[label];
    if (hidden && (match[2] || dataset !== null || radius !== null)) throw new Error(`Use “hide ${label}” without a field or position.`);
    const available = fields[slot] || [];
    if (!hidden && !available.length) throw new Error(`No fields are available for ${label} in the loaded datasets.`);
    patch[show] = !hidden;
    let field = null;
    if (!hidden && (match[2] || dataset !== null)) {
      const requested = (match[2] || params[`${slot}Field`] || '').trim();
      const wanted = norm(aliases[requested] || requested.replace(/^field /, ''));
      // Field entries carry the dataset explicitly; do not guess a secondary prefix.
      const candidates = available.filter(f => (dataset === null || f.dataset === dataset)
        && (norm(f.name) === wanted || norm(f.value) === wanted));
      field = candidates.find(f => f.dataset === (dataset || 1)) || candidates[0];
      if (!field) throw new Error(`Field “${requested}” is unavailable for ${label}${dataset ? ` in dataset ${dataset}` : ''}. Available: ${available.slice(0, 20).map(f => `${f.name} (dataset ${f.dataset})`).join(', ')}.`);
      patch[`${slot}Field`] = field.value;
      if (slot.startsWith('meridian')) {
        patch[`${slot}LeftField`] = field.value;
        patch[`${slot}IndependentSides`] = false;
      }
    }
    if (radius !== null) {
      if (radius < 0 || radius > 1) throw new Error('Radius must lie between 0 and 1 in r/ro.');
      patch.radialSurfaceRadiusRo = radius;
    }
    descriptions.push(`${hidden ? 'Hide' : 'Show'} ${label}${field ? `: ${field.name} (dataset ${field.dataset})` : ''}${radius !== null ? ` at r/ro=${radius}` : ''}`);
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
  return { action: 'apply', patch, descriptions };
}

// Keep undo snapshots tied to the loaded data and roll back failed updates.
export function createCommandHistory({ capture, apply, identity, ready }) {
  let history = [], dataset = null, busy = false;
  return {
    async run(command) {
      if (busy) throw new Error('A command is already running.');
      ready();
      const current = identity();
      if (dataset !== current) { history = []; dataset = current; }
      const before = capture();
      const target = command.action === 'undo' ? history.at(-1) : { ...before, params: { ...before.params, ...command.patch } };
      if (!target) throw new Error('Nothing to undo for this dataset.');
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
