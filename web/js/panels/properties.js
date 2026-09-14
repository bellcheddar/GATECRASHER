/* The Properties sheet. BUILD_SPEC 7.7: Plotly only, on one shared Blueprint template.
 *
 *   - potency against a selectable property, property axis drawn from assays.json adme
 *   - ligand efficiency across the campaign, with the lead tracked
 *   - the PK species ladder where the paper reports one
 *
 * Only exact measurements are plotted as points. A bound is drawn as an open marker at the
 * bound, so a compound measured as '>400' is visible as measured-and-beyond rather than
 * quietly missing from the figure. */

import { formatValue, measurement, numericValue } from '../data.js';
import { emptyState } from '../draw.js';
import { campaignLine, compoundScatter, draw, speciesLadder } from '../viewers/plotly.js';

export function initProperties(state) {
  let bundle = null;

  const el = {
    axis: document.getElementById('property-axis'),
    property: document.getElementById('plot-property'),
    efficiency: document.getElementById('plot-efficiency'),
    pk: document.getElementById('plot-pk'),
    pkNote: document.getElementById('pk-note'),
    pkSheet: document.getElementById('sheet-pk'),
    storyPlot: document.getElementById('story-plot'),
  };

  function propertyOptions() {
    const wanted = ['adme', 'property'];
    return Object.entries(bundle.assays)
      .filter(([id, spec]) => wanted.includes(spec.category) && bundle.index.byAssay.has(id))
      .map(([id, spec]) => ({ id, label: spec.label, units: spec.units }));
  }

  function renderAxisOptions() {
    const options = propertyOptions();
    el.axis.replaceChildren();
    for (const option of options) {
      const node = document.createElement('option');
      node.value = option.id;
      node.textContent = `${option.label}${option.units ? ` (${option.units})` : ''}`;
      el.axis.append(node);
    }
    const current = state.get('assayX');
    if (current && options.some((o) => o.id === current)) el.axis.value = current;
    else if (options.length) state.set({ assayX: options[0].id }, 'properties:default-axis');
  }

  /* Points for a pair of assays. A compound missing either value is left out of the
   * scatter, and the count of those is reported under the plot rather than hidden. */
  function points(xAssay, yAssay) {
    const out = [];
    let dropped = 0;
    for (const compound of bundle.compounds) {
      const rowX = measurement(bundle, compound.compound_id, xAssay);
      const rowY = measurement(bundle, compound.compound_id, yAssay);
      if (!rowX || !rowY || rowX.value === null || rowY.value === null) {
        dropped += 1;
        continue;
      }
      out.push({
        id: compound.compound_id,
        label: `cmpd ${compound.label}: `
          + `${formatValue(bundle, rowX, { withUnits: true })}, `
          + `${formatValue(bundle, rowY, { withUnits: true })}`,
        x: rowX.value,
        y: rowY.value,
        boundedX: rowX.qualifier !== '=',
        boundedY: rowY.qualifier !== '=',
        role: compound.role,
      });
    }
    return { out, dropped };
  }

  function renderPropertyPlot() {
    const yAssay = bundle.index.primaryAssay;
    const xAssay = state.get('assayX') || el.axis.value;
    if (!xAssay || !yAssay) {
      el.property.replaceChildren(emptyState('No property axis available',
        'This paper reports no ADME or physicochemical column.'));
      return;
    }
    const { out, dropped } = points(xAssay, yAssay);
    if (!out.length) {
      el.property.replaceChildren(emptyState('Nothing to plot for this pair',
        'No compound in this paper has both values.'));
      return;
    }
    const xSpec = bundle.assays[xAssay];
    const ySpec = bundle.assays[yAssay];
    const { traces, layout } = compoundScatter(out, {
      selected: state.get('compound'),
      xTitle: `${xSpec.label}${xSpec.units ? ` (${xSpec.units})` : ''}`,
      yTitle: `${ySpec.label}${ySpec.units ? ` (${ySpec.units})` : ''}`,
      logX: Boolean(xSpec.log),
      logY: Boolean(ySpec.log),
    });
    layout.title = dropped
      ? { text: `${dropped} compound${dropped === 1 ? '' : 's'} not shown: one of the two values is not reported`, font: { size: 10 } }
      : undefined;
    draw(el.property, traces, layout, {
      onPointClick: (id) => state.set({ compound: id }, 'properties:point'),
    });
  }

  /* Ligand efficiency: the primary potency per heavy atom. Only exact values qualify,
   * because pIC50 of a bound is not a number. */
  function renderEfficiency() {
    const primary = bundle.index.primaryAssay;
    const spec = bundle.assays[primary] || {};
    const rows = [];
    for (const compound of bundle.compounds) {
      const value = numericValue(measurement(bundle, compound.compound_id, primary));
      if (!value || !compound.hac) continue;
      /* LE = 1.37 * pIC50 / heavy atom count, with IC50 in molar. */
      const pIC50 = -Math.log10(value * 1e-9);
      rows.push({
        id: compound.compound_id,
        label: compound.label,
        y: Number(((1.37 * pIC50) / compound.hac).toFixed(3)),
      });
    }
    if (!rows.length) {
      el.efficiency.replaceChildren(emptyState('No ligand efficiency to show',
        'Every potency value in this paper is a bound rather than a measurement.'));
      return;
    }
    const lead = bundle.compounds.find((c) => c.role === 'lead');
    const { traces, layout } = campaignLine(rows, {
      yTitle: `ligand efficiency from ${spec.short || primary}`,
      logY: false,
      leadId: lead?.compound_id || null,
    });
    draw(el.efficiency, traces, layout, {
      onPointClick: (id) => state.set({ compound: id }, 'properties:efficiency-point'),
    });
  }

  function renderPk() {
    const pkAssays = (bundle.index.byCategory.pk || []).filter((id) => bundle.index.byAssay.has(id));
    if (!pkAssays.length) {
      el.pkSheet.hidden = true;
      return;
    }
    el.pkSheet.hidden = false;

    /* Oral bioavailability is the number these campaigns are actually judged on, so it is
     * the default ladder where it exists. */
    const preferred = pkAssays.find((id) => /_po_f$/.test(id)) || pkAssays[0];
    const suffix = preferred.replace(/^[a-z]+_/, '');
    const species = [...new Set(pkAssays
      .filter((id) => id.endsWith(suffix))
      .map((id) => bundle.assays[id].species || id.split('_')[0]))];

    const groups = species.map((name) => {
      const assayId = pkAssays.find((id) => (bundle.assays[id].species || id.split('_')[0]) === name
        && id.endsWith(suffix));
      const rows = [];
      for (const compound of bundle.compounds) {
        const row = measurement(bundle, compound.compound_id, assayId);
        if (!row || row.value === null) continue;
        rows.push({
          id: compound.compound_id,
          label: compound.label,
          y: row.value,
          note: row.source_note || '',
        });
      }
      return { species: name, points: rows };
    }).filter((group) => group.points.length);

    if (!groups.length) {
      el.pk.replaceChildren(emptyState('No PK values for this assay', ''));
      return;
    }
    const spec = bundle.assays[preferred];
    const { traces, layout } = speciesLadder(groups, {
      yTitle: `${spec.label.replace(/^[A-Za-z]+ /, '')}${spec.units ? ` (${spec.units})` : ''}`,
    });
    draw(el.pk, traces, layout, {
      onPointClick: (id) => state.set({ compound: id }, 'properties:pk-bar'),
    });

    /* The doses differ row by row, and an AUC without its dose is not comparable: the
     * note has to be on the sheet, not only in a tooltip. */
    const notes = new Set();
    for (const group of groups) for (const point of group.points) if (point.note) notes.add(point.note);
    el.pkNote.textContent = notes.size
      ? `Doses differ per row: ${[...notes].join(' · ')}`
      : '';
  }

  /* The small plot pinned beside the Story column: the selectivity view, because that is
   * the spine of all four campaigns. */
  function renderStoryPlot() {
    if (!el.storyPlot) return;
    const primary = bundle.index.primaryAssay;
    const anti = bundle.index.antiTargets.find((a) => bundle.index.byAssay.has(a.id));
    if (!primary || !anti) {
      el.storyPlot.replaceChildren(emptyState('No selectivity pair to plot', ''));
      return;
    }
    const { out } = points(primary, anti.id);
    if (!out.length) {
      el.storyPlot.replaceChildren(emptyState('No compound has both values', ''));
      return;
    }
    const { traces, layout } = compoundScatter(out, {
      selected: state.get('compound'),
      xTitle: `${bundle.assays[primary].short} (${bundle.assays[primary].units})`,
      yTitle: `${bundle.assays[anti.id].short} (${bundle.assays[anti.id].units})`,
      logX: true,
      logY: true,
    });
    layout.height = 260;
    draw(el.storyPlot, traces, layout, {
      onPointClick: (id) => state.set({ compound: id }, 'story:plot-point'),
    });
  }

  el.axis.addEventListener('change', () => {
    state.set({ assayX: el.axis.value }, 'properties:axis-select');
  });

  state.on(['assayX', 'assayY'], () => {
    if (!bundle) return;
    if (state.get('assayX') && el.axis.value !== state.get('assayX')) {
      const options = [...el.axis.options].map((o) => o.value);
      if (options.includes(state.get('assayX'))) el.axis.value = state.get('assayX');
    }
    renderPropertyPlot();
  });

  state.on(['compound'], () => {
    if (!bundle) return;
    renderPropertyPlot();
    renderStoryPlot();
  });

  return {
    setBundle(next) {
      bundle = next;
      renderAxisOptions();
      renderPropertyPlot();
      renderEfficiency();
      renderPk();
      renderStoryPlot();
    },
    render() {
      if (!bundle) return;
      renderPropertyPlot();
      renderEfficiency();
      renderPk();
      renderStoryPlot();
    },
  };
}
