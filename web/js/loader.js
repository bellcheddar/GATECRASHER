/* Load a vendored library the first time something needs it.
 *
 * The three libraries used to be plain <script> tags, which blocked the first paint behind
 * roughly 16 MB of decoded JavaScript and WebAssembly that the landing sheet does not need
 * before its text is on screen. Lighthouse scored the page 0 on mobile for it.
 *
 * URLs carry the library version rather than deploy.sh's mtime stamp, because deploy.sh only
 * rewrites index.html and nginx serves these immutable: without a version in the URL an
 * upgraded library would never reach a returning reader. Bump the version with the file. */

export const VENDOR = {
  molstar: { script: 'js/vendor/molstar.js?v=5.11.0', style: 'css/molstar.css?v=5.11.0' },
  plotly: { script: 'js/vendor/plotly-basic.min.js?v=2.35.2' },
  rdkit: { script: 'js/vendor/RDKit_minimal.js?v=2025.3.4-1.0.0' },
};

const pending = new Map();

function once(key, make) {
  if (!pending.has(key)) pending.set(key, make());
  return pending.get(key);
}

export function loadScript(src) {
  return once(src, () => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => { pending.delete(src); reject(new Error(`could not load ${src}`)); };
    document.head.append(script);
  }));
}

export function loadStyle(href) {
  return once(href, () => new Promise((resolve) => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    /* A missing stylesheet degrades the look, not the function, so it never rejects. */
    link.onload = () => resolve();
    link.onerror = () => resolve();
    document.head.append(link);
  }));
}

/* Resolves the first time `element` is on screen or within `margin` of it. A container in a
 * hidden tab, or below the fold on a phone, does not intersect, so whatever waits on this is
 * not fetched until a reader could actually see it. On a phone the Story sheet's viewer and
 * plot sit below its text, and loading Mol* and Plotly for them at boot cost Lighthouse
 * about 1.7 s of main-thread time. */
export function whenVisible(element, margin = '200px') {
  return new Promise((resolve) => {
    if (!element || typeof IntersectionObserver === 'undefined') {
      resolve();
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        observer.disconnect();
        resolve();
      }
    }, { rootMargin: margin });
    observer.observe(element);
  });
}

export function loadLibrary(name) {
  const spec = VENDOR[name];
  return Promise.all([
    loadScript(spec.script),
    spec.style ? loadStyle(spec.style) : Promise.resolve(),
  ]).then(() => undefined);
}
