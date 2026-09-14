/* The About sheet. BUILD_SPEC 10, Stage 4.
 *
 * Three things a reader is entitled to: how the numbers got here, what built them, and a
 * plain statement of what is rendered rather than reproduced. All of it comes from
 * data/software.json so this page and the repository's own record cannot drift apart.
 */

import { emptyState } from '../draw.js';

export function initAbout(state) {
  const el = {
    statement: document.getElementById('about-statement'),
    flow: document.getElementById('about-flow'),
    software: document.getElementById('about-software'),
    sources: document.getElementById('about-sources'),
  };
  let loaded = null;

  async function load(base = 'data') {
    if (loaded) return loaded;
    const response = await fetch(`${base}/software.json`, { cache: 'no-cache' });
    if (!response.ok) throw new Error(`software.json: ${response.status}`);
    loaded = await response.json();
    return loaded;
  }

  function link(url, text) {
    const a = document.createElement('a');
    a.href = url;
    a.textContent = text;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    return a;
  }

  function renderFlow(stages) {
    el.flow.replaceChildren();
    stages.forEach((stage, i) => {
      if (i) {
        const arrow = document.createElement('div');
        arrow.className = 'about-arrow';
        arrow.setAttribute('aria-hidden', 'true');
        arrow.textContent = '→';
        el.flow.append(arrow);
      }
      const card = document.createElement('div');
      card.className = 'about-stage';

      const number = document.createElement('span');
      number.className = 'about-stage-n mono';
      number.textContent = String(i + 1).padStart(2, '0');

      const name = document.createElement('h3');
      name.textContent = stage.label;

      const detail = document.createElement('p');
      detail.textContent = stage.detail;

      card.append(number, name, detail);
      el.flow.append(card);
    });
  }

  function renderSoftware(rows) {
    el.software.replaceChildren();
    const head = el.software.createTHead().insertRow();
    for (const text of ['Tool', 'Version', 'Runs', 'What it does', 'Licence']) {
      const th = document.createElement('th');
      th.scope = 'col';
      th.textContent = text;
      head.append(th);
    }
    const body = el.software.createTBody();
    for (const tool of rows) {
      const tr = body.insertRow();

      const name = tr.insertCell();
      name.append(link(tool.url, tool.name));
      if (tool.doi) {
        name.append(document.createTextNode(' '));
        const doi = link(`https://doi.org/${tool.doi}`, 'doi');
        doi.className = 'mono';
        doi.style.fontSize = '10px';
        name.append(doi);
      }

      const version = tr.insertCell();
      version.className = 'mono';
      version.textContent = tool.version;

      const stage = tr.insertCell();
      stage.textContent = tool.stage === 'browser' ? 'in your browser' : 'on the Mac';
      stage.className = 'mono';

      tr.insertCell().textContent = tool.role;
      tr.insertCell().textContent = tool.licence;
    }
  }

  function renderSources(rows) {
    el.sources.replaceChildren();
    for (const source of rows) {
      const item = document.createElement('div');
      item.className = 'about-source';

      const name = document.createElement('h3');
      name.append(link(source.url, source.name));
      if (source.doi) {
        name.append(document.createTextNode(' '));
        const doi = link(`https://doi.org/${source.doi}`, source.doi);
        doi.className = 'mono';
        doi.style.fontSize = '11px';
        name.append(doi);
      }

      const role = document.createElement('p');
      role.textContent = source.role;

      item.append(name, role);
      el.sources.append(item);
    }
  }

  async function render() {
    try {
      const data = await load();
      el.statement.textContent = data.statement;
      renderFlow(data.pipeline);
      renderSoftware(data.software);
      renderSources(data.data_sources);
    } catch (err) {
      el.flow.replaceChildren(emptyState('The software record did not load',
        'It lives at data/software.json and is plain JSON if you would rather read it directly.'));
      console.error('[about]', err);
    }
  }

  /* Rendered once, on first view: nothing here depends on which paper is open. */
  let started = false;
  state.on(['tab'], () => {
    if (state.get('tab') === 'about' && !started) {
      started = true;
      render();
    }
  });

  return { render };
}
