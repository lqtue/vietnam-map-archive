// The local, six-sheet version of the archive's place-time context query.
// It works from the prototype's OCR extract; the live /api/context also has
// reviewed footprints and stories. Printed labels are proximity evidence,
// not proof that the named features meet at the clicked point.

const $ = id => document.getElementById(id);
const archiveLink = path => `https://maparchive.vn${path}`;
const spotParams = at => `${at[0].toFixed(6)},${at[1].toFixed(6)}`;

function link(href, text, className = '') {
  const element = document.createElement('a');
  element.href = href;
  element.textContent = text;
  element.className = className;
  element.target = '_blank';
  element.rel = 'noopener';
  return element;
}

export function createPlaceContext({ layers, metersPerUnit, groundOrigin, metersPerDegree, span, onChange }) {
  const hint = $('nearby-hint');
  const summary = $('nearby-summary');
  const location = $('nearby-location');
  const note = $('nearby-note');
  const radiusSelect = $('nearby-radius');
  const clearButton = $('nearby-clear');
  const results = $('nearby-results');
  let point = null;
  let sourceIndex = null;

  function covers(layer, groundPoint) {
    const [a, b, c, d, e, f] = layer.image.matrix;
    const determinant = a * d - b * c;
    if (Math.abs(determinant) < 1e-10) return false;
    const px = (d * (groundPoint[0] - e) - c * (groundPoint[1] - f)) / determinant;
    const py = (-b * (groundPoint[0] - e) + a * (groundPoint[1] - f)) / determinant;
    return px >= 0 && py >= 0 && px <= layer.image.width && py <= layer.image.height;
  }

  function toLngLat(groundPoint) {
    return [
      (groundOrigin[0] + groundPoint[0] * metersPerUnit) / metersPerDegree[0],
      (groundOrigin[1] + (span - groundPoint[1]) * metersPerUnit) / metersPerDegree[1],
    ];
  }

  function query(groundPoint, radius) {
    const at = toLngLat(groundPoint);
    const maps = layers.filter(layer => covers(layer, groundPoint)).map(layer => ({
      id: layer.map_id, name: layer.label, year: layer.year,
    }));
    const labels = layers.flatMap(layer => (layer.labels || []).map(label => ({
      map_id: layer.map_id, map_name: layer.label, year: layer.year,
      text: label.t, category: label.k, p: label.p,
      distance_m: Math.hypot(label.p[0] - groundPoint[0], label.p[1] - groundPoint[1]) * metersPerUnit,
      at: toLngLat(label.p),
    }))).filter(label => label.distance_m <= radius)
      .sort((a, b) => a.distance_m - b.distance_m);
    return { at, radius_m: radius, maps, labels };
  }

  function renderYear(layer, index, context) {
    const hits = context.labels.filter(label => label.map_id === layer.map_id);
    const covered = context.maps.some(map => map.id === layer.map_id);
    const section = document.createElement('details');
    section.className = 'nearby-year';
    section.open = sourceIndex === index;

    const heading = document.createElement('summary');
    const year = document.createElement('b'); year.textContent = `${layer.year} · ${layer.label}`;
    const count = document.createElement('small');
    count.textContent = covered ? `${hits.length} ${hits.length === 1 ? 'label' : 'labels'}` : 'outside scan';
    heading.append(year, count);
    section.append(heading);

    const body = document.createElement('div'); body.className = 'nearby-year-body';
    body.append(link(archiveLink(`/catalog/${layer.map_id}`), 'Source sheet ↗', 'nearby-source'));
    if (layer.georef.exact) {
      const warning = document.createElement('small');
      warning.textContent = '3 control points; no independent placement residual';
      body.append(warning);
    }
    if (covered && !hits.length) {
      const empty = document.createElement('small'); empty.textContent = 'No OCR labels found here';
      body.append(empty);
    }
    for (const hit of hits) {
      const row = document.createElement('div'); row.className = 'nearby-hit';
      const label = link(archiveLink(`/explore?map=${layer.map_id}&at=${spotParams(hit.at)}`), hit.text);
      label.title = `${hit.category || 'label'} · open position on ${layer.year} scan`;
      const distance = document.createElement('span'); distance.textContent = `${Math.round(hit.distance_m)} m`;
      row.append(label, distance);
      body.append(row);
    }
    section.append(body);
    return section;
  }

  function render() {
    results.replaceChildren();
    location.replaceChildren();
    clearButton.hidden = !point;
    summary.hidden = !point;
    location.hidden = !point;
    note.hidden = !point;
    if (!point) {
      hint.textContent = 'Click a spot on a scan to see what its maps name nearby.';
      onChange(null, null);
      return;
    }
    const radius = Number(radiusSelect.value);
    const context = query(point, radius);
    hint.textContent = `OCR label centres within ${radius} m. Sheet alignment is approximate; an empty result is not evidence of absence.`;
    summary.textContent = `${context.maps.length} of ${layers.length} sheets cover this spot · ${context.labels.length} nearby readings`;
    location.append(`${context.at[1].toFixed(6)}° N, ${context.at[0].toFixed(6)}° E · `);
    location.append(link(
      archiveLink(`/api/context?lng=${context.at[0].toFixed(6)}&lat=${context.at[1].toFixed(6)}&radius=${radius}`),
      'Full archive context ↗',
    ));
    layers.forEach((layer, index) => results.append(renderYear(layer, index, context)));
    onChange(point, context);
  }

  radiusSelect.onchange = render;
  clearButton.onclick = () => {
    point = null;
    sourceIndex = null;
    render();
  };

  return {
    select(groundPoint, layerIndex) {
      point = groundPoint;
      sourceIndex = layerIndex;
      render();
    },
    refresh: render,
  };
}
