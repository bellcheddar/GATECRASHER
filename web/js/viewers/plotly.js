/* Plotly on one shared Blueprint template. BUILD_SPEC section 7.7.
 *
 * Every figure in the app uses this template, so a point means the same thing on every plot.
 * The template reads its colours from the CSS custom properties, which is what makes the
 * plots theme-aware: AlphaFraud's layout hard-codes dark ink and would be unreadable here.
 *
 * Two rules the data forces:
 *   - only an exact measurement is plotted as a point. A bound such as '>10000' is drawn as
 *     an open marker at the bound with an arrow, never as a number.
 *   - potency axes are log, because the campaigns span four orders of magnitude. */

import { loadLibrary, whenVisible } from '../loader.js';

const RESIZE_DEBOUNCE = 150;

function token(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

export function template() {
  const ink = token('--ink', '#DCEAF6');
  const inkDim = token('--ink-dim', '#8FB4CF');
  const grid = token('--line', 'rgba(127,179,213,.35)');
  return {
    font: { family: 'IBM Plex Mono, ui-monospace, monospace', size: 11, color: ink },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { l: 58, r: 16, t: 28, b: 48 },
    hoverlabel: {
      bgcolor: token('--surface-2', '#143458'),
      bordercolor: token('--line-strong', '#7FB3D5'),
      font: { family: 'IBM Plex Mono, monospace', size: 11, color: ink },
    },
    colorway: [
      token('--target', '#6FD3FF'),
      token('--measure', '#FFD166'),
      token('--gain', '#5FD39B'),
      token('--anti', '#FF6FA5'),
      token('--loss', '#FF5C5C'),
    ],
    xaxis: axis(inkDim, grid),
    yaxis: axis(inkDim, grid),
    legend: {
      orientation: 'h', y: -0.22, x: 0,
      font: { size: 10, color: inkDim },
      bgcolor: 'rgba(0,0,0,0)',
    },
    showlegend: true,
  };
}

function axis(inkDim, grid) {
  return {
    color: inkDim,
    gridcolor: grid,
    zerolinecolor: grid,
    linecolor: grid,
    ticks: 'outside',
    ticklen: 4,
    tickfont: { size: 10, color: inkDim },
    automargin: true,
  };
}

export const CONFIG = {
  displayModeBar: false,
  responsive: false,     // sized explicitly below: autosize proved unreliable in AlphaFraud
  scrollZoom: false,
  doubleClick: 'reset',
};

const hosts = new Map();

/* Plotly is fetched on first use, not as a blocking <script>, and only once some figure that
 * wants it is actually on screen: a figure in a hidden tab or below a phone's fold does not
 * pull 1 MB of JavaScript in. A figure asked for before Plotly arrives is remembered (the
 * latest request per host wins) and drawn when it lands. */
const waiting = new Map();
const watched = new WeakSet();
let loading = null;

function startLoading() {
  if (loading) return;
  loading = loadLibrary('plotly')
    .then(() => {
      const queued = [...waiting.entries()];
      waiting.clear();
      for (const [queuedHost, queuedArgs] of queued) draw(queuedHost, ...queuedArgs);
    })
    .catch((err) => {
      console.warn('[plotly] did not load', err);
      loading = null;
    });
}

function whenPlotly(host, args) {
  waiting.set(host, args);
  if (!watched.has(host)) {
    watched.add(host);
    whenVisible(host).then(startLoading);
  }
  return null;
}

/* Render or update a figure. Width comes from the container, because the panel can be in a
 * grid track that Plotly's autosize measures wrongly. */
export function draw(host, data, layout = {}, { onPointClick = null } = {}) {
  if (typeof window.Plotly === 'undefined') {
    return whenPlotly(host, [data, layout, { onPointClick }]);
  }
  const width = host.clientWidth || host.parentElement?.clientWidth || 600;
  const narrow = width < 620;

  const merged = {
    ...template(),
    ...layout,
    width,
    height: layout.height || (narrow ? 260 : 320),
    autosize: false,
    xaxis: { ...template().xaxis, ...(layout.xaxis || {}) },
    yaxis: { ...template().yaxis, ...(layout.yaxis || {}) },
  };
  if (narrow) {
    merged.margin = { ...merged.margin, l: 46, r: 8 };
    merged.showlegend = false;
  }

  window.Plotly.react(host, data, merged, CONFIG);

  if (!hosts.has(host)) {
    hosts.set(host, { data, layout: merged, onPointClick });
    const observer = new ResizeObserver(debounce(() => {
      const entry = hosts.get(host);
      if (entry) draw(host, entry.data, entry.layout, { onPointClick: entry.onPointClick });
    }, RESIZE_DEBOUNCE));
    observer.observe(host);
    if (onPointClick) {
      host.on('plotly_click', (event) => {
        const point = event?.points?.[0];
        if (point) onPointClick(point.customdata ?? point.text, point);
      });
    }
  } else {
    hosts.set(host, { data, layout: merged, onPointClick });
  }
  return host;
}

export function redrawAll() {
  for (const [host, entry] of hosts.entries()) {
    draw(host, entry.data, entry.layout, { onPointClick: entry.onPointClick });
  }
}

/* -------------------------------------------------------------- trace builders */

/* A scatter of compounds. `points` are { id, x, y, role, boundedX, boundedY, label }.
 * The selected compound is drawn as its own trace on top, so highlighting never has to
 * mutate the marker array of the main trace. */
export function compoundScatter(points, { selected = null, xTitle = '', yTitle = '',
  logX = false, logY = false, colour = null } = {}) {
  const exact = points.filter((p) => !p.boundedX && !p.boundedY);
  const bounded = points.filter((p) => p.boundedX || p.boundedY);
  const target = colour || token('--target', '#6FD3FF');

  const traces = [{
    /* SVG scatter, not scattergl: a campaign is tens of compounds, where WebGL buys nothing,
     * and it keeps the app on Plotly's basic bundle (a third of the full one's size). */
    type: 'scatter',
    mode: 'markers',
    name: 'compounds',
    x: exact.map((p) => p.x),
    y: exact.map((p) => p.y),
    text: exact.map((p) => p.label),
    customdata: exact.map((p) => p.id),
    hovertemplate: '%{text}<extra></extra>',
    marker: {
      size: exact.map((p) => (p.role === 'lead' ? 13 : p.role === 'milestone' ? 10 : 8)),
      color: target,
      line: { width: 1, color: token('--bg', '#0B2542') },
      opacity: 0.9,
    },
    cliponaxis: false,
  }];

  /* Bounded values are shown, not hidden: an open marker at the bound, so a reader can see
   * that the compound was measured and the answer was "beyond here". */
  if (bounded.length) {
    traces.push({
      type: 'scatter',
      mode: 'markers',
      name: 'bounded (>, <)',
      x: bounded.map((p) => p.x),
      y: bounded.map((p) => p.y),
      text: bounded.map((p) => `${p.label} (bound)`),
      customdata: bounded.map((p) => p.id),
      hovertemplate: '%{text}<extra></extra>',
      marker: {
        size: 10,
        color: 'rgba(0,0,0,0)',
        line: { width: 1.5, color: token('--ink-dim', '#8FB4CF') },
        symbol: 'circle-open',
      },
      cliponaxis: false,
    });
  }

  const chosen = points.find((p) => p.id === selected);
  if (chosen) {
    traces.push({
      type: 'scatter',
      mode: 'markers+text',
      name: 'selected',
      x: [chosen.x],
      y: [chosen.y],
      text: [chosen.id],
      textposition: 'top center',
      textfont: { color: token('--measure', '#FFD166'), size: 11 },
      customdata: [chosen.id],
      hoverinfo: 'skip',
      marker: {
        size: 16,
        color: 'rgba(0,0,0,0)',
        line: { width: 2, color: token('--measure', '#FFD166') },
      },
      cliponaxis: false,
    });
  }

  const layout = {
    xaxis: { title: { text: xTitle, font: { size: 11 } }, type: logX ? 'log' : 'linear' },
    yaxis: { title: { text: yTitle, font: { size: 11 } }, type: logY ? 'log' : 'linear' },
    showlegend: bounded.length > 0,
  };
  return { traces, layout };
}

/* The campaign walk: one point per compound in published order, with the lead marked. */
export function campaignLine(points, { yTitle = '', logY = true, leadId = null } = {}) {
  const traces = [{
    type: 'scatter',
    mode: 'lines+markers',
    name: yTitle || 'value',
    x: points.map((p) => p.label),
    y: points.map((p) => p.y),
    customdata: points.map((p) => p.id),
    line: { color: token('--target', '#6FD3FF'), width: 1.5, shape: 'hv' },
    marker: {
      size: points.map((p) => (p.id === leadId ? 13 : 8)),
      color: points.map((p) => (p.id === leadId ? token('--measure', '#FFD166') : token('--target', '#6FD3FF'))),
    },
    hovertemplate: '%{x}: %{y}<extra></extra>',
    cliponaxis: false,
  }];
  return {
    traces,
    layout: {
      xaxis: { title: { text: 'compound' }, type: 'category' },
      yaxis: { title: { text: yTitle }, type: logY ? 'log' : 'linear' },
      showlegend: false,
    },
  };
}

/* PK ladder: grouped bars by species. Doses differ per row, so the note travels in the
 * hover text: an AUC without its dose is not comparable. */
export function speciesLadder(groups, { yTitle = '' } = {}) {
  const traces = groups.map((group, i) => ({
    type: 'bar',
    name: group.species,
    x: group.points.map((p) => p.label),
    y: group.points.map((p) => p.y),
    customdata: group.points.map((p) => p.id),
    text: group.points.map((p) => p.note || ''),
    hovertemplate: '%{x} %{y}<br>%{text}<extra>' + group.species + '</extra>',
    marker: { color: i === 0 ? token('--target', '#6FD3FF') : token('--gain', '#5FD39B') },
  }));
  return {
    traces,
    layout: { barmode: 'group', xaxis: { type: 'category' }, yaxis: { title: { text: yTitle } } },
  };
}

function debounce(fn, ms) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
