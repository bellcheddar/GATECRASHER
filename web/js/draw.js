/* Blueprint drawing primitives. BUILD_SPEC section 6.4.
 *
 * The grammar is implemented once here and used by every panel, so a measured distance looks
 * the same in a 2D callout as in the structure overlay. Rules that matter:
 *   - a measured distance is ALWAYS rendered from a PLIP distance, never hand-placed
 *   - amber means measured, cyan means annotation, rose means anti-target, coral means
 *     liability, green is reserved for edit consequences
 *   - measure lines draw themselves over 240 ms, and honour prefers-reduced-motion */

const SVG_NS = 'http://www.w3.org/2000/svg';

export function svg(tag, attrs = {}, parent = null) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined) continue;
    node.setAttribute(key, String(value));
  }
  if (parent) parent.appendChild(node);
  return node;
}

export function surface(host, { width, height, viewBox } = {}) {
  host.replaceChildren();
  const root = svg('svg', {
    xmlns: SVG_NS,
    viewBox: viewBox || `0 0 ${width || host.clientWidth || 600} ${height || host.clientHeight || 300}`,
    width: '100%',
    height: height ? `${height}` : '100%',
    role: 'presentation',
  }, host);
  return root;
}

/* ------------------------------------------------------------- measure line
 * Amber, with end ticks, and the value in mono with an angstrom sign. `distance` must be a
 * measured number: passing null draws nothing rather than an empty tick pair, because a
 * measure line with no measurement is exactly the lie this grammar exists to prevent. */
export function measureLine(root, { x1, y1, x2, y2, distance, label, animate = true, tick = 5 }) {
  if (distance === null || distance === undefined) return null;
  const group = svg('g', { class: 'measure' }, root);
  const line = svg('line', { class: 'measure-line', x1, y1, x2, y2 }, group);

  const angle = Math.atan2(y2 - y1, x2 - x1);
  const nx = Math.sin(angle) * tick;
  const ny = -Math.cos(angle) * tick;
  svg('line', { class: 'measure-line', x1: x1 - nx, y1: y1 - ny, x2: x1 + nx, y2: y1 + ny }, group);
  svg('line', { class: 'measure-line', x1: x2 - nx, y1: y2 - ny, x2: x2 + nx, y2: y2 + ny }, group);

  const text = svg('text', {
    class: 'measure-label',
    x: (x1 + x2) / 2 + nx * 1.6,
    y: (y1 + y2) / 2 + ny * 1.6,
    'text-anchor': 'middle',
    'dominant-baseline': 'middle',
  }, group);
  text.textContent = label || `${Number(distance).toFixed(2)} Å`;

  if (animate && !reducedMotion()) {
    const length = Math.hypot(x2 - x1, y2 - y1);
    line.style.setProperty('--dash-length', String(Math.ceil(length)));
    line.classList.add('is-drawing');
  }
  return group;
}

/* --------------------------------------------------------------- annotation
 * Cyan leader line with a 3-2 dash, pointing at a named motif or subpocket. Rose when the
 * annotation belongs to the anti-target, so a pair reads without a legend. */
export function annotation(root, { x1, y1, x2, y2, text, anti = false, anchor = 'start' }) {
  const group = svg('g', { class: anti ? 'anti' : '' }, root);
  svg('path', {
    class: 'annotation-line',
    d: `M ${x1} ${y1} L ${x2} ${y2}`,
  }, group);
  const label = svg('text', {
    class: 'annotation-label',
    x: x2 + (anchor === 'end' ? -6 : 6),
    y: y2,
    'text-anchor': anchor === 'end' ? 'end' : 'start',
    'dominant-baseline': 'middle',
  }, group);
  label.textContent = text;
  return group;
}

/* Coral, solid, with a short hatch: a clash or a liability. */
export function clash(root, { x1, y1, x2, y2, hatch = 4 }) {
  const group = svg('g', { class: 'clash' }, root);
  svg('line', { class: 'clash-line', x1, y1, x2, y2 }, group);
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const steps = Math.max(2, Math.round(Math.hypot(x2 - x1, y2 - y1) / 7));
  for (let i = 1; i < steps; i += 1) {
    const t = i / steps;
    const px = x1 + (x2 - x1) * t;
    const py = y1 + (y2 - y1) * t;
    svg('line', {
      class: 'clash-line',
      x1: px - Math.sin(angle) * hatch,
      y1: py + Math.cos(angle) * hatch,
      x2: px + Math.sin(angle) * hatch,
      y2: py - Math.cos(angle) * hatch,
    }, group);
  }
  return group;
}

/* --------------------------------------------------------------- callouts */

export function calloutBox(root, { x, y, width, height, title, lines = [], anti = false }) {
  const group = svg('g', { class: anti ? 'anti' : '' }, root);
  svg('rect', {
    x, y, width, height,
    fill: 'var(--surface-2)',
    stroke: anti ? 'var(--anti)' : 'var(--line)',
    'stroke-width': 1,
    rx: 2,
  }, group);
  const head = svg('text', { class: 'annotation-label', x: x + 8, y: y + 16 }, group);
  head.textContent = title;
  lines.forEach((line, i) => {
    const text = svg('text', {
      class: 'measure-label',
      x: x + 8,
      y: y + 34 + i * 14,
    }, group);
    text.textContent = line;
  });
  return group;
}

/* ------------------------------------------------------- isostere swap row
 * Before and after side by side with a mono arrow, changed atoms highlighted by the
 * caller's depiction, deltas in mono beneath. Morphs rather than cuts. */
export function swapRow({ beforeSvg, afterSvg, deltas = [], changeType = '', reason = '' }) {
  const wrap = document.createElement('div');
  wrap.className = 'edit-swap morph';

  const before = document.createElement('div');
  before.className = 'depiction';
  before.innerHTML = beforeSvg || '';

  const arrow = document.createElement('div');
  arrow.className = 'edit-arrow mono';
  arrow.textContent = '⟶';
  if (changeType) {
    const tag = document.createElement('div');
    tag.className = 'change-tag';
    tag.textContent = changeType.replace(/_/g, ' ');
    arrow.appendChild(tag);
  }

  const after = document.createElement('div');
  after.className = 'depiction';
  after.innerHTML = afterSvg || '';

  wrap.append(before, arrow, after);

  const container = document.createElement('div');
  container.append(wrap);

  if (reason) {
    const why = document.createElement('p');
    why.textContent = reason;
    container.append(why);
  }

  if (deltas.length) {
    const row = document.createElement('div');
    row.className = 'edit-deltas';
    for (const delta of deltas) {
      const chip = document.createElement('span');
      chip.className = `edit-delta ${delta.direction === 'gain' ? 'gain' : delta.direction === 'loss' ? 'loss' : ''}`;
      chip.textContent = delta.text;
      row.append(chip);
    }
    container.append(row);
  }
  return container;
}

/* --------------------------------------------------------------- empty state
 * An absent value is a first-class answer: "not stated in this paper" is information, and
 * it is styled as information rather than as an error. */
export function emptyState(message, detail = '') {
  const box = document.createElement('div');
  box.className = 'sheet-empty';
  const strong = document.createElement('strong');
  strong.textContent = message;
  box.append(strong);
  if (detail) {
    const p = document.createElement('p');
    p.textContent = detail;
    box.append(p);
  }
  return box;
}

export function reducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/* Colour for a motif, read from the CSS custom properties so the palette lives in one
 * place and both themes are handled without a second table in JavaScript. */
export function motifColour(motif) {
  const probe = document.createElement('span');
  probe.className = `motif-${motif}`;
  probe.style.display = 'none';
  document.body.appendChild(probe);
  const value = getComputedStyle(probe).getPropertyValue('--motif').trim();
  probe.remove();
  return value || getComputedStyle(document.documentElement).getPropertyValue('--ink-dim').trim();
}

/* Mol* wants an integer, CSS gives us a colour string. */
export function colourToInt(colour) {
  const probe = document.createElement('span');
  probe.style.color = colour;
  document.body.appendChild(probe);
  const computed = getComputedStyle(probe).color;
  probe.remove();
  const match = computed.match(/rgba?\((\d+)[,\s]+(\d+)[,\s]+(\d+)/);
  if (!match) return 0x6FD3FF;
  const [, r, g, b] = match.map(Number);
  return (r << 16) | (g << 8) | b;
}
