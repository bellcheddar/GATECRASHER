# Vendored libraries

Served from our own origin, not from a CDN. BUILD_SPEC section 2 asks for pinned CDN builds,
but cdnjs does not carry Mol\*, and serving all three locally satisfies the spec's own Stage 4
rule that no runtime request may go anywhere except this app's origin. It also means a CDN
outage cannot take the app down, and nothing about a visitor reaches a third party.

| File | Version | Source | Licence |
|---|---|---|---|
| `molstar.js`, `../css/molstar.css` | 5.11.0 | Copied from `GOBSMACKED/app/static/vendor/`, which took the plain viewer build that sets a global `molstar` | MIT |
| `plotly.min.js` | 2.35.2 | Copied from `GOBSMACKED/app/static/vendor/` (header: plotly.js v2.35.2, Copyright 2012-2024 Plotly, Inc.) | MIT |
| `RDKit_minimal.js`, `RDKit_minimal.wasm` | 2025.3.4-1.0.0 | `https://cdn.jsdelivr.net/npm/@rdkit/rdkit@2025.3.4-1.0.0/dist/` | BSD-3-Clause |

## Notes

- **npm publishes RDKit.js with a suffixed version**, `2025.3.4-1.0.0`, not a bare
  `2025.3.4`. A plain version number 404s, silently producing a zero-byte file if curl is
  called without `-f`.
- **`RDKit_minimal.js` fetches `RDKit_minimal.wasm` from its own directory**, so the two
  must stay side by side and be served with `application/wasm`.
- **Mol\* must be created with `extensions: []`**, or the Volumes and Segmentations
  extension makes a network request as soon as the viewer exists.
- Every reference to these files is cache-busted with `?v=<mtime>`, because nginx serves
  static assets `immutable`: without the stamp a deploy is invisible to anyone who has
  already loaded the page.
- Upgrades are deliberate. Replace the file, update the version in this table, and re-run
  the cross-link smoke test.
