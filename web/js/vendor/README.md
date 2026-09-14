# Vendored libraries

Served from our own origin, not from a CDN. BUILD_SPEC section 2 asks for pinned CDN builds,
but cdnjs does not carry Mol\*, and serving all three locally satisfies the spec's own Stage 4
rule that no runtime request may go anywhere except this app's origin. It also means a CDN
outage cannot take the app down, and nothing about a visitor reaches a third party.

| File | Version | Source | Licence | Notice |
|---|---|---|---|---|
| `molstar.js`, `../css/molstar.css` | 5.11.0 | Copied from `GOBSMACKED/app/static/vendor/`, which took the plain viewer build that sets a global `molstar` | MIT | `molstar.LICENSE.txt` |
| `plotly-basic.min.js` | 2.35.2 | `https://cdn.jsdelivr.net/npm/plotly.js-basic-dist-min@2.35.2/` (sha256 `138c2e81…7f021dfcfa`) | MIT | `plotly.LICENSE.txt`, `plotly-basic.min.js.LICENSE.txt` |
| `RDKit_minimal.js`, `RDKit_minimal.wasm` | 2025.3.4-1.0.0 | `https://cdn.jsdelivr.net/npm/@rdkit/rdkit@2025.3.4-1.0.0/dist/` | BSD-3-Clause | `RDKit_minimal.LICENSE.txt` |

None of these is a `<script>` tag. `js/loader.js` fetches each on first use, so nothing blocks
the first paint: Mol\* when a structure viewer is created, Plotly when a figure is drawn,
RDKit.js when the Edit log or SAR sheet is first opened.

## Notes

- **npm publishes RDKit.js with a suffixed version**, `2025.3.4-1.0.0`, not a bare
  `2025.3.4`. A plain version number 404s, silently producing a zero-byte file if curl is
  called without `-f`.
- **`RDKit_minimal.js` fetches `RDKit_minimal.wasm` from its own directory**, so the two
  must stay side by side and be served with `application/wasm`.
- **Mol\* must be created with `extensions: []`**, or the Volumes and Segmentations
  extension makes a network request as soon as the viewer exists.
- **Plotly is the basic partial bundle** (scatter, bar, pie): 345 kB gzipped against the full
  build's 1.5 MB. The app draws only scatter and bar traces. A new trace type means checking
  it is in the basic bundle first; `scattergl` is not.
- These files are cache-busted with `?v=<version>` in `js/loader.js`, not with deploy.sh's
  `?v=<mtime>`, because deploy.sh stamps only the URLs written in `index.html`. nginx serves
  them `immutable`, so without a version in the URL an upgrade never reaches a returning
  reader.
- Upgrades are deliberate. Replace the file, update the version in this table AND in
  `js/loader.js`, and re-run the browser checks.
