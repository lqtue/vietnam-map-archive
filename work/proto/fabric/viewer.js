// WebGL scene; camera drag/zoom/pan/inertia is entirely OrbitControls' job.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = (id) => document.getElementById(id);
const stage = $('stage');
const nameSearch = document.createElement('input');
nameSearch.id = 'name-search';
nameSearch.type = 'search';
nameSearch.placeholder = 'Search shared names…';
nameSearch.setAttribute('aria-label', 'Search shared names');
const namesNav = $('names');
namesNav.parentNode.insertBefore(nameSearch, namesNav);
const statusLabel = document.createElement('p');
statusLabel.id = 'status';
statusLabel.textContent = 'Loading scans…';
$('masthead').append(statusLabel);
$('instruction').textContent = 'Drag to rotate, scroll to zoom, or use Side view. Click a point to pin its name.';

// Theme: OS preference by default, [data-theme] pins it either way (set
// synchronously in <head> so reload doesn't flash the wrong one). load()
// below hands us onThemeChange once the WebGL colors it owns exist, so a
// click here recolors the scene immediately instead of waiting for reload.
let onThemeChange = null;
function currentTheme() {
  return document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light');
}
function syncThemeButton() {
  const isDark = currentTheme() === 'dark';
  $('theme-toggle').textContent = isDark ? 'Light' : 'Dark';
  $('theme-toggle').setAttribute('aria-label', isDark ? 'Switch to light theme' : 'Switch to dark theme');
}
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('theme', theme); } catch {}
  syncThemeButton();
  onThemeChange?.();
}
$('theme-toggle').onclick = () => setTheme(currentTheme() === 'dark' ? 'light' : 'dark');
syncThemeButton();

const style = getComputedStyle(document.documentElement);
const lineColor = new THREE.Color(style.getPropertyValue('--line').trim());
const warmColor = new THREE.Color(style.getPropertyValue('--warm').trim());

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 1, 20000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.domElement.style.display = 'block';
stage.prepend(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minAzimuthAngle = -Infinity;
controls.maxAzimuthAngle = Infinity;
controls.minDistance = 150;
controls.maxDistance = 4000;
controls.screenSpacePanning = true;
controls.addEventListener('start', () => play(false));
controls.addEventListener('change', updateZoomReadout);

// 89°, not 90: sheets lie flat, so a near-top-down elevation faces them
// straight at the camera by default; exactly 90 puts the view axis parallel
// to OrbitControls' up vector, which is the classic gimbal-lock singularity.
// At this near-top-down elevation, azimuth is effectively screen roll: world
// +Z is north (toWorld above), and 180° is the azimuth that puts +Z at the
// top of the screen — verified against the camera's actual look-at basis,
// not eyeballed (0° put south on top).
const REST = { distance: 950, azimuth: THREE.MathUtils.degToRad(180), elevation: THREE.MathUtils.degToRad(89) };
function applyView({ distance, azimuth, elevation }) {
  camera.position.set(
    distance * Math.cos(elevation) * Math.sin(azimuth),
    distance * Math.sin(elevation),
    distance * Math.cos(elevation) * Math.cos(azimuth),
  );
  controls.target.set(0, 0, 0);
  controls.update();
}
function currentView() {
  const offset = camera.position.clone().sub(controls.target);
  const distance = offset.length();
  return { distance, azimuth: Math.atan2(offset.x, offset.z), elevation: Math.asin(offset.y / distance) };
}
// Shortest way round the circle, so a tween never spins the long way past ±180°.
const angleDelta = (from, to) => THREE.MathUtils.euclideanModulo(to - from + Math.PI, 2 * Math.PI) - Math.PI;
const easeInOutCubic = t => (t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2);
let viewAnimation = null;
function animateView(target, duration = 900) {
  cancelAnimationFrame(viewAnimation?.raf);
  const from = currentView();
  const dAzimuth = angleDelta(from.azimuth, target.azimuth);
  const wasEnabled = controls.enabled;
  controls.enabled = false;
  const start = performance.now();
  const anim = {};
  anim.raf = requestAnimationFrame(function tick(now) {
    const t = easeInOutCubic(Math.min(1, (now - start) / duration));
    applyView({
      distance: THREE.MathUtils.lerp(from.distance, target.distance, t),
      azimuth: from.azimuth + dAzimuth * t,
      elevation: THREE.MathUtils.lerp(from.elevation, target.elevation, t),
    });
    if (t < 1) anim.raf = requestAnimationFrame(tick);
    else controls.enabled = wasEnabled;
  });
  viewAnimation = anim;
}
function updateZoomReadout() {
  if ($('zoom-value')) $('zoom-value').textContent = `${Math.round((REST.distance / camera.position.distanceTo(controls.target)) * 100)}%`;
}
function zoom(factor) {
  const offset = camera.position.clone().sub(controls.target);
  const distance = THREE.MathUtils.clamp(offset.length() / factor, controls.minDistance, controls.maxDistance);
  camera.position.copy(controls.target).add(offset.setLength(distance));
  controls.update();
}
let playing = false;
function play(value) {
  playing = value;
  controls.autoRotate = playing;
  if ($('play')) {
    $('play').textContent = playing ? '⏸' : '▶';
    $('play').setAttribute('aria-label', playing ? 'Pause' : 'Auto rotate');
    $('play').setAttribute('aria-pressed', String(playing));
  }
}
const fitScale = () => Math.min(1, innerWidth / 1100, innerHeight / 850);
function reset() {
  play(false);
  applyView({ ...REST, distance: REST.distance / fitScale() });
}
if ($('zoom-in')) $('zoom-in').onclick = () => zoom(1.2);
if ($('zoom-out')) $('zoom-out').onclick = () => zoom(1 / 1.2);
if ($('reset')) $('reset').onclick = reset;
if ($('play')) $('play').onclick = () => play(!playing);
if ($('top')) $('top').onclick = () => applyView({ ...REST, azimuth: 0, elevation: 0 });
// Free-drag from the near-top-down default overshoots a true side angle —
// OrbitControls' inertia carries it straight past the equator to the
// underside before it settles. This snaps to a fixed raking angle instead.
const SIDE = { azimuth: REST.azimuth, elevation: THREE.MathUtils.degToRad(25) };
let sideView = false;
const sideToggle = $('side-toggle');
if (sideToggle) sideToggle.onclick = () => {
  sideView = !sideView;
  play(false);
  animateView({ ...(sideView ? SIDE : REST), distance: REST.distance / fitScale() });
  sideToggle.textContent = sideView ? 'Top view' : 'Side view';
  sideToggle.setAttribute('aria-pressed', String(sideView));
};
if ($('clean')) $('clean').onclick = () => document.body.classList.toggle('clean');
if ($('restore')) $('restore').onclick = () => document.body.classList.remove('clean');
if ($('speed')) $('speed').oninput = (e) => (controls.autoRotateSpeed = Number(e.target.value));
controls.autoRotateSpeed = Number($('speed')?.value || 4);

// Hand control: an alternative to OrbitControls' mouse drag. Loads
// MediaPipe's HandLandmarker from CDN only once toggled on (webcam + a
// few-MB model, not worth paying for on every visit). Wrist position is
// read as a joystick (not a drag delta, so there's no drift to re-center),
// pinch distance (thumb tip to index tip) maps to zoom.
const handToggle = $('hand-toggle'), handVideo = $('hand-video');
let handLandmarker = null, handStream = null, handRunning = false, OneEuroFilter = null;
// Raw landmark position is noisy frame-to-frame; the 1€ filter (Casiez &
// Goguey — the reference implementation, not a homebrew smoother) trades
// lag for jitter reduction per signal. beta above 0 lets fast moves cut
// through the lag so it doesn't feel laggy on a deliberate swing.
let handFilters = null;
function freshHandFilters() {
  return {
    x: new OneEuroFilter(30, 1, 0.6, 1),
    y: new OneEuroFilter(30, 1, 0.6, 1),
    pinch: new OneEuroFilter(30, 1, 0.6, 1),
  };
}
async function startHandControl() {
  handToggle.disabled = true;
  handToggle.textContent = 'Loading…';
  if (!handLandmarker) {
    const [vision, filterModule] = await Promise.all([
      import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs'),
      import('https://cdn.jsdelivr.net/npm/1eurofilter@1.3.0/+esm'),
    ]);
    OneEuroFilter = filterModule.OneEuroFilter;
    const fileset = await vision.FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm');
    handLandmarker = await vision.HandLandmarker.createFromOptions(fileset, {
      baseOptions: {
        modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
        delegate: 'GPU',
      },
      runningMode: 'VIDEO',
      numHands: 1,
    });
  }
  handFilters = freshHandFilters();
  handStream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 }, audio: false });
  handVideo.srcObject = handStream;
  await handVideo.play();
  controls.enabled = false;
  play(false);
  document.body.classList.add('hand-active');
  handToggle.disabled = false;
  handToggle.textContent = 'Stop hand control';
  handRunning = true;
  requestAnimationFrame(handLoop);
}
function stopHandControl() {
  handRunning = false;
  handStream?.getTracks().forEach(t => t.stop());
  handStream = null;
  controls.enabled = true;
  document.body.classList.remove('hand-active');
  handToggle.disabled = false;
  handToggle.textContent = 'Hand control';
}
// ponytail: pinch-distance-to-zoom range (0.03..0.25, normalized image
// units) is eyeballed against one webcam at arm's length, not calibrated
// per hand size or camera distance — retune here if zoom feels dead or
// pinned at an end.
function handLoop() {
  if (!handRunning) return;
  if (handVideo.readyState >= 2) {
    const now = performance.now() / 1000; // seconds: what OneEuroFilter expects for its freq estimate
    const hand = handLandmarker.detectForVideo(handVideo, now * 1000).landmarks?.[0];
    if (hand) {
      const rawX = 1 - hand[0].x; // selfie camera: flip so hand-right feels like view-right
      const mirroredX = handFilters.x.filter(rawX, now);
      const y = handFilters.y.filter(hand[0].y, now);
      const rawPinch = Math.hypot(hand[4].x - hand[8].x, hand[4].y - hand[8].y);
      const pinch = handFilters.pinch.filter(rawPinch, now);
      const azimuth = REST.azimuth + THREE.MathUtils.degToRad((mirroredX - 0.5) * 220);
      const elevation = THREE.MathUtils.clamp(
        REST.elevation + THREE.MathUtils.degToRad((0.5 - y) * 140),
        THREE.MathUtils.degToRad(-10), THREE.MathUtils.degToRad(85),
      );
      const distance = THREE.MathUtils.lerp(controls.maxDistance, controls.minDistance, THREE.MathUtils.clamp((pinch - 0.03) / 0.22, 0, 1));
      applyView({ distance, azimuth, elevation });
    }
  }
  requestAnimationFrame(handLoop);
}
if (handToggle) handToggle.onclick = () => {
  if (handRunning) { stopHandControl(); return; }
  startHandControl().catch(err => { alert(`Hand control needs camera access: ${err.message}`); stopHandControl(); });
};

const sheet = $('sheet'), sheetHandle = $('sheet-handle');
function expandSheet(open) {
  if (!sheet) return;
  sheet.classList.toggle('expanded', open);
  sheetHandle.setAttribute('aria-expanded', String(open));
  document.body.classList.toggle('sheet-expanded', open); // mobile: the expanded sheet covers the toolbar's row, so hide it rather than float over the list
}
if (sheetHandle) sheetHandle.onclick = () => expandSheet(!sheet.classList.contains('expanded'));
renderer.domElement.oncontextmenu = e => e.preventDefault();
renderer.domElement.addEventListener('pointerdown', () => stage.classList.add('grabbing'));
addEventListener('pointerup', () => stage.classList.remove('grabbing'));
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
document.addEventListener('keydown', e => {
  if (e.target.closest('input,select,button')) return;
  if (e.code === 'Space') { e.preventDefault(); play(!playing); }
  if (e.key.toLowerCase() === 'h') document.body.classList.toggle('clean');
  if (e.key === 'Escape') document.body.classList.remove('clean');
  if (e.key === '+' || e.key === '=') zoom(1.2);
  if (e.key === '-') zoom(1 / 1.2);
  if (e.key.toLowerCase() === 'r') reset();
});
reset();
renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });

// Sheet space stays the same 0..1000, y-down grid build.py already emits
// (image.matrix and polys share it); this is the one place it becomes world
// XYZ. Sheets lie flat (image x/y -> world X/Z) and stack by world Y, so the
// pile reads top-down instead of receding in depth.
// Flat planes viewed from above flip chirality versus the old upright ones
// (same fix a mirror makes for a page held up to a light from the back) —
// negate X here, not Z, so east/west reads correctly and north stays "near".
const toWorld = ([x, y], layerY) => [350 - x * 0.7, layerY, -(y * 0.7 - 350)];
const affine = ([a, b, c, d, e, f], x, y) => [a * x + c * y + e, b * x + d * y + f];

function dotTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 32;
  const ctx = c.getContext('2d');
  ctx.beginPath(); ctx.arc(16, 16, 13, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill();
  return new THREE.CanvasTexture(c);
}
const anchorTexture = dotTexture();
const textureLoader = new THREE.TextureLoader();
textureLoader.crossOrigin = 'anonymous';

async function load() {
  const response = await fetch('layers.json');
  if (!response.ok) throw Error(`Layer data: HTTP ${response.status}`);
  const { layers, links } = await response.json();
  // Oldest sheet sits on top of the stack, facing the camera first; newer
  // sheets stack below it, descending in world Y. Spacing is by sheet index,
  // not calendar gap, so a 9-year and a 25-year gap between sheets look the
  // same distance apart.
  const indexByYear = new Map(layers.map((l, i) => [l.year, i]));
  const mid = (layers.length - 1) / 2;
  const layerY = year => (mid - indexByYear.get(year)) * 130;
  let focus = null, hovered = null, loaded = 0, failed = 0;
  const rows = [], meshes = [], fabrics = [];
  function status() { $('status').textContent = `${loaded}/${layers.length} scans ready${failed ? ` · ${failed} unavailable` : ''}`; }
  const scanOpacity = 0.55;
  function applyLayerVisual(i) {
    // Hovering a sheet previews it exactly like focusing it; hover just doesn't stick.
    const active = hovered ?? focus, isActive = active === i, isDim = active !== null && !isActive;
    meshes[i].material.opacity = isActive ? 1 : isDim ? .15 : scanOpacity;
    fabrics[i].material.opacity = isActive ? 1 : isDim ? .15 : 0;
  }
  function selectYear(index) {
    focus = focus === index ? null : index;
    layers.forEach((_, i) => applyLayerVisual(i));
    rows.forEach((el, i) => el.setAttribute('aria-pressed', String(i === focus)));
    const l = layers[focus];
    if (l) expandSheet(true);
  }
  for (const [index, l] of layers.entries()) {
    const ly = layerY(l.year);
    const corners = [[0, 0], [l.image.width, 0], [l.image.width, l.image.height], [0, l.image.height]]
      .map(([x, y]) => toWorld(affine(l.image.matrix, x, y), ly));
    const positions = new Float32Array([...corners[0], ...corners[1], ...corners[2], ...corners[0], ...corners[2], ...corners[3]]);
    const uvs = new Float32Array([0, 1, 1, 1, 1, 0, 0, 1, 1, 0, 0, 0]);
    const imageGeometry = new THREE.BufferGeometry();
    imageGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    imageGeometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
    const texture = textureLoader.load(`${l.image.iiif}/full/800,/0/default.jpg`, () => { loaded++; status(); }, undefined, () => { failed++; status(); });
    texture.colorSpace = THREE.SRGBColorSpace;
    const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, opacity: scanOpacity, side: THREE.DoubleSide, depthWrite: false });
    const mesh = new THREE.Mesh(imageGeometry, material);
    scene.add(mesh); meshes.push(mesh);

    const fabricPositions = [];
    for (const ring of l.polys) {
      for (let i = 0; i < ring.length; i++) {
        fabricPositions.push(...toWorld(ring[i], ly), ...toWorld(ring[(i + 1) % ring.length], ly));
      }
    }
    const fabricGeometry = new THREE.BufferGeometry();
    fabricGeometry.setAttribute('position', new THREE.Float32BufferAttribute(fabricPositions, 3));
    const fabricMaterial = new THREE.LineBasicMaterial({ color: warmColor, transparent: true, opacity: 0, depthWrite: false });
    const fabricLines = new THREE.LineSegments(fabricGeometry, fabricMaterial);
    scene.add(fabricLines); fabrics.push(fabricLines);

    const row = document.createElement('button'); row.className = 'year'; row.setAttribute('aria-pressed', 'false');
    const title = document.createElement('b'); title.textContent = l.year;
    const desc = document.createElement('small'); desc.textContent = `${l.label} · ${l.polys.length ? `${l.polys.length.toLocaleString()} outlines` : 'scan only'}`;
    row.append(title, desc); row.onclick = () => selectYear(index);
    row.onmouseenter = () => { hovered = index; layers.forEach((_, j) => applyLayerVisual(j)); };
    row.onmouseleave = () => { hovered = null; layers.forEach((_, j) => applyLayerVisual(j)); };
    $('legend').append(row); rows.push(row);
  }
  // One button per chain (a union-find thread of matched occurrences, from
  // build.py) highlights that name's links across every sheet it survives to,
  // not just one adjacent pair — and keeps two same-named but differently
  // located threads (e.g. a long street matched at different ends on
  // different gaps) as separate buttons instead of merging them.
  const groups = new Map();
  const pickables = [];
  for (const link of links) {
    const key = link.c;
    if (!groups.has(key)) groups.set(key, { name: link.t, elements: [], years: new Set(), doling: null });
    const group = groups.get(key);
    if (!group.doling && link.d) group.doling = link.d;
    const a = toWorld(link.p, layerY(layers[link.a].year)), b = toWorld(link.q, layerY(layers[link.b].year));
    const lineGeometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...a), new THREE.Vector3(...b)]);
    const line = new THREE.Line(lineGeometry, new THREE.LineBasicMaterial({ color: lineColor, transparent: true, opacity: .16, depthTest: false }));
    scene.add(line); group.elements.push(line);
    for (const [point, year] of [[a, layers[link.a].year], [b, layers[link.b].year]]) {
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: anchorTexture, color: lineColor, transparent: true, opacity: .2, depthTest: false }));
      sprite.position.set(...point); sprite.scale.set(8, 8, 1);
      scene.add(sprite); group.elements.push(sprite); group.years.add(year);
      pickables.push({ sprite, key });
    }
  }
  function setHot(elements, hot) {
    for (const el of elements) {
      el.material.opacity = hot ? 1 : el.isSprite ? .2 : .16;
      el.material.color.copy(hot ? warmColor : lineColor);
    }
  }
  // Popup: richer detail on the name actually clicked, at the click point —
  // the sidebar list stays a plain index, it doesn't try to hold this too.
  const popup = $('popup'), popupBody = $('popup-body');
  function closePopup() { popup.classList.remove('open'); }
  $('popup-close').onclick = closePopup;
  function popupHTML(group) {
    const years = [...group.years].sort().join(' → ');
    let html = `<h2>${group.name}</h2><p>${years} · tentative match, not a verified rename.</p>`;
    const d = group.doling;
    if (d) {
      html += `<div class="doling"><p><strong>${d.colonial}</strong> → ${d.modern}${d.kind === 'street' ? '' : ` (${d.kind})`}</p>` +
        `<p>Per Tim Doling, <em>Historic Vietnam</em>: “${d.post_title}” (${d.post_date}). ` +
        `<a href="${d.post_url}" target="_blank" rel="noopener">Read →</a></p></div>`;
    }
    return html;
  }
  function showPopup(x, y, group) {
    popupBody.innerHTML = popupHTML(group);
    popup.classList.add('open');
    const rect = popup.getBoundingClientRect();
    popup.style.left = `${Math.min(Math.max(8, x + 14), innerWidth - rect.width - 8)}px`;
    popup.style.top = `${Math.min(Math.max(8, y + 14), innerHeight - rect.height - 8)}px`;
  }
  let selected = null;
  function selectGroup(key, x, y) {
    const group = groups.get(key);
    selected = selected === key ? null : key;
    for (const [k, g] of groups) { setHot(g.elements, k === selected); g.button.setAttribute('aria-pressed', String(k === selected)); }
    if (selected) { showPopup(x, y, group); expandSheet(true); } else closePopup();
  }
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closePopup(); });
  // Canvas clicks are handled by the pointerup picker below (it already knows
  // whether a name point was actually hit); this only catches clicks on the
  // rest of the page — anywhere that isn't the popup itself or a name button.
  document.addEventListener('pointerdown', e => {
    if (e.target.closest('#stage,#popup,.name')) return;
    closePopup();
  });
  for (const [key, group] of groups) {
    const button = document.createElement('button'); button.className = 'name'; button.textContent = group.name;
    group.button = button; button.setAttribute('aria-pressed', 'false');
    button.onmouseenter = () => { if (selected !== key) setHot(group.elements, true); };
    button.onmouseleave = () => { if (selected !== key) setHot(group.elements, false); };
    button.onclick = (e) => selectGroup(key, e.clientX, e.clientY);
    $('names').append(button);
  }
  nameSearch.addEventListener('input', () => {
    const query = nameSearch.value.trim().toLocaleLowerCase();
    for (const group of groups.values()) group.button.hidden = query !== '' && !group.name.toLocaleLowerCase().includes(query);
  });
  // Clicking (not dragging) a link's anchor point in the scene acts exactly
  // like clicking its sidebar name button — same selection, same highlight.
  const spriteObjects = pickables.map(p => p.sprite);
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  function pickAt(clientX, clientY) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObjects(spriteObjects)[0];
    return hit && pickables.find(p => p.sprite === hit.object);
  }
  let downPoint = null, hoveredKey = null;
  renderer.domElement.addEventListener('pointerdown', e => { downPoint = [e.clientX, e.clientY]; });
  renderer.domElement.addEventListener('pointerup', e => {
    const start = downPoint; downPoint = null;
    if (!start || Math.hypot(e.clientX - start[0], e.clientY - start[1]) > 6) return;
    const picked = pickAt(e.clientX, e.clientY);
    if (picked) selectGroup(picked.key, e.clientX, e.clientY);
    else closePopup();
  });
  renderer.domElement.addEventListener('pointermove', e => {
    if (downPoint) return;
    const picked = pickAt(e.clientX, e.clientY);
    stage.classList.toggle('pointable', !!picked);
    const key = picked?.key ?? null;
    if (key !== hoveredKey) {
      if (hoveredKey) groups.get(hoveredKey).button.onmouseleave();
      if (key) groups.get(key).button.onmouseenter();
      hoveredKey = key;
    }
  });
  renderer.domElement.addEventListener('pointerleave', () => {
    if (hoveredKey) { groups.get(hoveredKey).button.onmouseleave(); hoveredKey = null; }
    stage.classList.remove('pointable');
  });
  onThemeChange = () => {
    const s = getComputedStyle(document.documentElement);
    lineColor.set(s.getPropertyValue('--line').trim());
    warmColor.set(s.getPropertyValue('--warm').trim());
    fabrics.forEach(f => f.material.color.copy(warmColor));
    for (const [key, g] of groups) setHot(g.elements, key === selected);
  };
  status();
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches) play(true);
}
load().catch(error => { $('status').textContent = `Could not load maps: ${error.message}. Serve this folder over HTTP.`; });
