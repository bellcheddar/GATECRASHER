/* Boot and shell wiring: the paper switcher, the tabs, the register and theme toggles,
 * the keyboard, and the one place where a bundle swap happens.
 *
 * BUILD_SPEC 7.1: the switcher swaps the data bundle and nothing else. Layout, selected tab
 * and equivalent selections persist across a paper change, falling back to that paper's lead
 * compound and primary structure where an equivalent does not exist. */

import { loadIndex, loadPaper } from './data.js';
import { appState } from './state.js';
import { initRail } from './panels/rail.js';
import { initStructure } from './panels/structure.js';
import { initEditLog } from './panels/editlog.js';
import { initSar } from './panels/sar.js';
import { initProperties } from './panels/properties.js';
import { initStory } from './panels/story.js';
import { initRdkit } from './viewers/rdkit.js';
import { redrawAll } from './viewers/plotly.js';

const TABS = ['story', 'structure', 'editlog', 'sar', 'properties'];

const panels = {};
let papers = [];
let bundle = null;

async function boot() {
  const state = appState;

  /* Theme first, so nothing renders in the wrong palette and then repaints. */
  const stored = state.theme.load();
  state.seed({ theme: stored });
  updateThemeButton();

  /* RDKit is optional: the app shows precomputed depictions without it, so booting does
   * not wait for the WASM before drawing the first paper. */
  initRdkit();

  panels.rail = initRail(state);
  panels.structure = initStructure(state);
  panels.editlog = initEditLog(state);
  panels.sar = initSar(state);
  panels.properties = initProperties(state);
  panels.story = initStory(state);

  const index = await loadIndex();
  papers = index.papers;
  renderSwitcher();

  const fromHash = state.readHash(papers.map((p) => p.slug), TABS);
  const slug = fromHash.paper || papers[0]?.slug;
  if (!slug) return;

  /* Wire the shell BEFORE the first bundle loads. Doing it afterwards means the keyboard
   * shortcuts and the toggles do not exist until the heaviest panel has finished drawing,
   * so a key pressed during load is silently swallowed: press 2 while CDK2 is still
   * rendering and nothing happens at all. The handlers are safe to attach early because
   * paper switches are serialised and every panel guards on its bundle. */
  wireShell();
  window.addEventListener('hashchange', onHashChange);
  await selectPaper(slug, fromHash);
}

/* ------------------------------------------------------------------ paper swap */

/* Paper switches are serialised. A visitor can press 2 while the first bundle is still
 * loading, and two concurrent switches race: the slower one finishes last and overwrites
 * the paper the reader actually asked for. */
let switching = Promise.resolve();

function selectPaper(slug, patch = {}) {
  switching = switching.catch(() => {}).then(() => selectPaperNow(slug, patch));
  return switching;
}

async function selectPaperNow(slug, patch = {}) {
  bundle = await loadPaper(slug);
  const state = appState;

  /* Carry an equivalent selection across where it exists in the new paper, otherwise fall
   * back to this paper's lead compound and primary structure. */
  const previousCompound = patch.compound ?? state.get('compound');
  const compound = bundle.index.compoundById.has(previousCompound)
    ? previousCompound
    : (bundle.compounds.find((c) => c.role === 'lead') || bundle.compounds[0])?.compound_id || null;

  const previousStructure = patch.structure ?? state.get('structure');
  const structure = bundle.structures.some((s) => s.pdb_id === previousStructure)
    ? previousStructure
    : (bundle.structures.find((s) => s.role === 'primary') || bundle.structures[0])?.pdb_id || null;

  const residues = (patch.residues || []).filter((key) =>
    bundle.index.residuesByKey.has(`${structure}|${key}`));

  const edit = patch.edit && bundle.index.editById.has(patch.edit) ? patch.edit : null;

  state.applyHash({
    paper: slug,
    tab: patch.tab || state.get('tab'),
    register: patch.register === 'plain' ? 'plain' : state.get('register'),
    antiTargetOn: patch.antiTargetOn ?? false,
    compound,
    structure,
    residues,
    edit,
    motif: null,
    beat: null,
  }, 'app:select-paper');

  /* The address bar follows the reader's action immediately. Waiting until every panel has
   * finished means the URL lags the click by however long the heaviest bundle takes to
   * draw its depictions and fetch its coordinates, which for FGFR is seconds: long enough
   * for a copied link to be the previous paper. */
  state.writeHash();

  panels.rail.setBundle(bundle);
  await panels.story.setBundle(bundle);
  await panels.structure.setBundle(bundle);
  await panels.editlog.setBundle(bundle);
  panels.sar.setBundle(bundle);
  panels.properties.setBundle(bundle);

  renderSwitcher();
  showTab(state.get('tab'));
  state.writeHash();
}

/* --------------------------------------------------------------------- shell */

function renderSwitcher() {
  const host = document.getElementById('paper-switcher');
  host.replaceChildren();
  const current = appState.get('paper');
  papers.forEach((paper, i) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('aria-pressed', String(paper.slug === current));
    button.title = `${paper.title} (${paper.authors_short} ${paper.year})`;
    button.textContent = paper.target;
    const key = document.createElement('kbd');
    key.textContent = String(i + 1);
    button.append(key);
    button.addEventListener('click', () => {
      if (paper.slug !== appState.get('paper')) selectPaper(paper.slug);
    });
    host.append(button);
  });
}

function showTab(tab) {
  for (const button of document.querySelectorAll('#tab-strip button')) {
    button.setAttribute('aria-selected', String(button.dataset.tab === tab));
  }
  for (const name of TABS) {
    const section = document.getElementById(`tab-${name}`);
    if (section) section.hidden = name !== tab;
  }
  /* Plotly sizes to its container, and a container inside a hidden section measures zero,
   * so every figure is redrawn once its tab is actually visible. */
  redrawAll();
}

function wireShell() {
  const state = appState;

  for (const button of document.querySelectorAll('#tab-strip button')) {
    button.addEventListener('click', () => {
      state.set({ tab: button.dataset.tab }, 'shell:tab');
    });
  }
  state.on(['tab'], () => showTab(state.get('tab')));

  document.getElementById('register-button').addEventListener('click', () => {
    const next = state.get('register') === 'plain' ? 'specialist' : 'plain';
    state.set({ register: next }, 'shell:register');
  });
  state.on(['register'], updateRegisterButton);
  updateRegisterButton();

  document.getElementById('theme-button').addEventListener('click', () => {
    state.theme.toggle('shell:theme');
  });
  state.on(['theme'], () => {
    updateThemeButton();
    /* Plotly reads its colours from the CSS tokens at draw time, so a theme change means
     * every figure has to be redrawn: it cannot re-theme itself. */
    redrawAll();
    panels.structure?.render();
  });

  /* The system theme can change under a viewer who has made no explicit choice. */
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (!state.get('theme')) {
      redrawAll();
      updateThemeButton();
    }
  });

  window.addEventListener('keydown', (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const target = event.target;
    if (target instanceof HTMLElement
      && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;

    const asNumber = Number(event.key);
    if (asNumber >= 1 && asNumber <= papers.length) {
      const paper = papers[asNumber - 1];
      if (paper.slug !== state.get('paper')) selectPaper(paper.slug);
      return;
    }
    if (event.key === 't') state.theme.toggle('shell:key-t');
    if (event.key === 'r') {
      state.set({ register: state.get('register') === 'plain' ? 'specialist' : 'plain' },
        'shell:key-r');
    }
    if (event.key === 'Escape') {
      state.set({ residues: [], motif: null, edit: null }, 'shell:escape');
    }
  });
}

function updateRegisterButton() {
  const button = document.getElementById('register-button');
  const plain = appState.get('register') === 'plain';
  button.textContent = plain ? 'Plain' : 'Specialist';
  button.setAttribute('aria-pressed', String(plain));
  button.title = plain
    ? 'Showing the plain register. Click for the specialist register.'
    : 'Showing the specialist register. Click for plain English.';
}

function updateThemeButton() {
  const effective = appState.theme.effective(appState.get('theme'));
  document.getElementById('theme-label').textContent = effective === 'dark' ? 'Dark' : 'Light';
  document.getElementById('theme-button').title =
    `${effective === 'dark' ? 'Dark' : 'Light'} drawing. Click to switch.`;
}

function onHashChange() {
  const patch = appState.readHash(papers.map((p) => p.slug), TABS);
  if (patch.paper && patch.paper !== appState.get('paper')) {
    selectPaper(patch.paper, patch);
    return;
  }
  appState.applyHash(patch, 'app:hashchange');
}

boot().catch((err) => {
  console.error('[app] boot failed', err);
  const main = document.querySelector('main');
  if (main) {
    const box = document.createElement('div');
    box.className = 'sheet-empty';
    box.innerHTML = '<strong>The app could not start</strong>'
      + '<p>The data bundles under <code>data/papers/</code> are plain CSV and JSON '
      + 'if you would rather read them directly.</p>';
    main.prepend(box);
  }
});
