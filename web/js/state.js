/* AppState: one object, one event bus, no component reaching into another.
 * BUILD_SPEC section 8.
 *
 * Every view is linkable, so state serialises to the URL hash:
 *   #cdk2/structure?cmpd=17&res=A:80,A:83&edit=cdk2-e04
 *
 * Loop guard: the bus dispatches once per user action. A panel must not emit while handling
 * an event, and if it tries, the attempt is dropped and reported rather than allowed to
 * recurse. That is enforced here rather than trusted to every panel author. */

const KEYS = [
  'paper', 'tab', 'register', 'compound', 'antiTargetOn', 'structure',
  'residues', 'motif', 'edit', 'assayX', 'assayY', 'beat', 'theme',
];

const DEFAULTS = {
  paper: 'cdk2',
  tab: 'story',
  register: 'specialist',
  compound: null,
  antiTargetOn: false,
  structure: null,
  residues: [],
  motif: null,
  edit: null,
  assayX: null,
  assayY: null,
  beat: null,
  theme: null,          // null means follow the system, which is the honest default
};

/* Short hash parameter names, so a shared URL stays readable. */
const HASH_KEYS = {
  cmpd: 'compound',
  res: 'residues',
  motif: 'motif',
  edit: 'edit',
  x: 'assayX',
  y: 'assayY',
  beat: 'beat',
  anti: 'antiTargetOn',
  reg: 'register',
  pdb: 'structure',
};

class AppState {
  /* Seed a key without dispatching, for boot-time values that no panel can have
   * subscribed to yet (the stored theme). Everything after boot goes through set(). */
  seed(patch) {
    for (const [key, value] of Object.entries(patch)) {
      if (!KEYS.includes(key)) throw new Error(`unknown state key: ${key}`);
      this._state[key] = key === 'residues' ? normaliseResidues(value) : value;
    }
  }

  constructor() {
    this._state = { ...DEFAULTS };
    this._subscribers = new Map();   // key -> Set<fn>
    this._any = new Set();
    this._dispatching = false;
    this._queue = [];
    this._applyingHash = false;
    this.theme = new ThemeStore(this);
  }

  get(key) {
    if (!KEYS.includes(key)) throw new Error(`unknown state key: ${key}`);
    return this._state[key];
  }

  snapshot() {
    return { ...this._state, residues: [...this._state.residues] };
  }

  /* Subscribe to one key, several keys, or '*' for every change. */
  on(keys, fn) {
    const list = keys === '*' ? null : (Array.isArray(keys) ? keys : [keys]);
    if (!list) {
      this._any.add(fn);
      return () => this._any.delete(fn);
    }
    list.forEach((key) => {
      if (!KEYS.includes(key)) throw new Error(`unknown state key: ${key}`);
      if (!this._subscribers.has(key)) this._subscribers.set(key, new Set());
      this._subscribers.get(key).add(fn);
    });
    return () => list.forEach((key) => this._subscribers.get(key)?.delete(fn));
  }

  /* The only way to change state. `origin` names the panel, for debugging cross-links. */
  set(patch, origin = 'unknown') {
    if (this._dispatching) {
      /* A panel emitted while handling an event. Dropping it keeps the single-dispatch
       * guarantee; reporting it makes the mistake findable instead of mysterious. */
      console.warn(`[state] ignored a set() from "${origin}" during dispatch of `
        + `"${this._dispatchOrigin}": panels must not emit while handling an event`,
        Object.keys(patch));
      return false;
    }

    const changed = {};
    for (const [key, value] of Object.entries(patch)) {
      if (!KEYS.includes(key)) throw new Error(`unknown state key: ${key}`);
      const next = key === 'residues' ? normaliseResidues(value) : value;
      if (!sameValue(this._state[key], next)) {
        changed[key] = next;
        this._state[key] = next;
      }
    }
    if (Object.keys(changed).length === 0) return false;

    this._dispatching = true;
    this._dispatchOrigin = origin;
    try {
      const seen = new Set();
      for (const key of Object.keys(changed)) {
        for (const fn of this._subscribers.get(key) || []) {
          if (seen.has(fn)) continue;      // a panel watching three changed keys runs once
          seen.add(fn);
          safely(fn, changed, this);
        }
      }
      for (const fn of this._any) safely(fn, changed, this);
    } finally {
      this._dispatching = false;
      this._dispatchOrigin = null;
    }

    if (!this._applyingHash) this.writeHash();
    return true;
  }

  /* ------------------------------------------------------------------ URL hash */

  writeHash() {
    const s = this._state;
    const params = new URLSearchParams();
    for (const [short, key] of Object.entries(HASH_KEYS)) {
      const value = s[key];
      if (value === null || value === undefined || value === '' || value === false) continue;
      if (key === 'residues') {
        if (value.length) params.set(short, value.join(','));
      } else if (key === 'antiTargetOn') {
        params.set(short, '1');
      } else if (key === 'register' && value === DEFAULTS.register) {
        continue;
      } else {
        params.set(short, String(value));
      }
    }
    const query = params.toString();
    const hash = `#${s.paper}/${s.tab}${query ? `?${query}` : ''}`;
    if (window.location.hash !== hash) {
      history.replaceState(null, '', hash);
    }
  }

  readHash(papers = [], tabs = []) {
    const raw = window.location.hash.replace(/^#/, '');
    if (!raw) return {};
    const [path, query = ''] = raw.split('?');
    const [paper, tab] = path.split('/');
    const patch = {};
    if (paper && papers.includes(paper)) patch.paper = paper;
    if (tab && tabs.includes(tab)) patch.tab = tab;

    const params = new URLSearchParams(query);
    for (const [short, key] of Object.entries(HASH_KEYS)) {
      if (!params.has(short)) continue;
      const value = params.get(short);
      if (key === 'residues') patch.residues = normaliseResidues(value.split(','));
      else if (key === 'antiTargetOn') patch.antiTargetOn = value === '1' || value === 'true';
      else patch[key] = value;
    }
    return patch;
  }

  /* Applying a hash must not write the hash back: an incoming link is the source of truth
   * for that one dispatch. */
  applyHash(patch, origin = 'hash') {
    this._applyingHash = true;
    try {
      return this.set(patch, origin);
    } finally {
      this._applyingHash = false;
    }
  }
}

/* --------------------------------------------------------------------- theme */

class ThemeStore {
  constructor(state) {
    this.state = state;
    this.KEY = 'gatecrasher.theme';
  }

  /* localStorage can throw or come back empty in a private window, with site data cleared,
   * or during a thumbnail capture, so every read and write is guarded and the page renders
   * correctly regardless. */
  load() {
    let stored = null;
    try {
      stored = window.localStorage.getItem(this.KEY);
    } catch (err) {
      stored = null;
    }
    const theme = stored === 'light' || stored === 'dark' ? stored : null;
    /* BUILD_SPEC 6.1: this app defaults to DARK when nothing is stored, rather than
     * following the system. So with no stored choice the root is stamped dark explicitly,
     * which also stops a light-preferring system winning through the media query. The
     * stamp is not saved: a viewer who has never touched the toggle has made no choice,
     * and if the default ever changes theirs changes with it. */
    this.apply(theme || 'dark');
    return theme;
  }

  save(theme) {
    try {
      if (theme) window.localStorage.setItem(this.KEY, theme);
      else window.localStorage.removeItem(this.KEY);
    } catch (err) {
      /* Not fatal: the choice simply does not persist for this viewer. */
    }
  }

  apply(theme) {
    const root = document.documentElement;
    if (theme) root.setAttribute('data-theme', theme);
    else root.removeAttribute('data-theme');
  }

  /* Dark is this app's default when nothing is stored, per BUILD_SPEC 6.1, so an unset
   * theme reads as dark rather than as whatever the system prefers. Asking the system here
   * would make the toggle disagree with the page it is sitting on: the root is stamped dark
   * on load, so a light-preferring system would show a dark page under a button labelled
   * "Light", and the first click would go the wrong way. */
  effective(theme) {
    return theme === 'light' || theme === 'dark' ? theme : 'dark';
  }

  toggle(origin = 'theme-toggle') {
    const next = this.effective(this.state.get('theme')) === 'dark' ? 'light' : 'dark';
    this.apply(next);
    this.save(next);
    this.state.set({ theme: next }, origin);
    return next;
  }
}

/* ------------------------------------------------------------------- helpers */

function normaliseResidues(value) {
  const list = Array.isArray(value) ? value : String(value || '').split(',');
  const seen = new Set();
  const out = [];
  for (const item of list) {
    const id = String(item).trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

function sameValue(a, b) {
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((item, i) => item === b[i]);
  }
  return a === b;
}

function safely(fn, changed, state) {
  try {
    fn(changed, state);
  } catch (err) {
    /* One broken panel must not stop the other panels from updating. */
    console.error('[state] subscriber failed', err);
  }
}

export const appState = new AppState();
export { AppState, KEYS, DEFAULTS };
