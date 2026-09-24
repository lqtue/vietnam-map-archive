// WebGL scene; TrackballControls keeps rotation free across both poles.
import * as THREE from 'three';
import { TrackballControls } from 'three/addons/controls/TrackballControls.js';
import { createPlaceContext } from './place-context.js';
import { createSidebar } from './sidebar.js';

const $ = (id) => document.getElementById(id);
const stage = $('stage');
const nameSearch = $('name-search');
const sidebar = createSidebar();

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

const controls = new TrackballControls(camera, renderer.domElement);
controls.mouseButtons.LEFT = THREE.MOUSE.PAN;
controls.mouseButtons.MIDDLE = THREE.MOUSE.DOLLY;
controls.mouseButtons.RIGHT = THREE.MOUSE.ROTATE;
controls.keys = []; // Command-drag is the single keyboard gesture for rotating.
controls.panSpeed = 0.65;
controls.rotateSpeed = 1.5;
controls.staticMoving = true;
controls.minDistance = 150;
controls.maxDistance = 4000;
controls.addEventListener('start', () => { play(false); cameraMove = null; });
controls.addEventListener('change', updateZoomReadout);

// 89°, not 90: sheets lie flat, so a near-top-down elevation faces them
// straight at the camera by default; exactly 90 puts the view axis parallel
// to the world up vector, the classic gimbal-lock singularity.
// At this near-top-down elevation, azimuth is effectively screen roll: world
// +Z is north (toWorld above), and 180° is the azimuth that puts +Z at the
// top of the screen — verified against the camera's actual look-at basis,
// not eyeballed (0° put south on top).
const REST = { distance: 950, azimuth: THREE.MathUtils.degToRad(180), elevation: THREE.MathUtils.degToRad(89) };
let cameraMove = null;
function moveCamera(position, target, up = camera.up, animate = false) {
  cameraMove = null;
  if (animate && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    cameraMove = {
      start: performance.now(), duration: 550,
      fromPosition: camera.position.clone(), fromTarget: controls.target.clone(), fromUp: camera.up.clone(),
      toPosition: position.clone(), toTarget: target.clone(), toUp: up.clone(),
    };
  } else {
    camera.position.copy(position);
    camera.up.copy(up);
    controls.target.copy(target);
    camera.lookAt(target);
    controls.update();
    updateZoomReadout();
  }
}
function applyView({ distance, azimuth, elevation }, animate = false, target = controls.target.clone()) {
  moveCamera(new THREE.Vector3(
    target.x + distance * Math.cos(elevation) * Math.sin(azimuth),
    target.y + distance * Math.sin(elevation),
    target.z + distance * Math.cos(elevation) * Math.cos(azimuth),
  ), target, new THREE.Vector3(0, 1, 0), animate);
}
function updateZoomReadout() {
  if ($('zoom-value')) $('zoom-value').textContent = `${Math.round((REST.distance / camera.position.distanceTo(controls.target)) * 100)}%`;
}
function zoom(factor) {
  play(false);
  const offset = camera.position.clone().sub(controls.target).multiplyScalar(1 / factor);
  offset.clampLength(controls.minDistance, controls.maxDistance);
  moveCamera(controls.target.clone().add(offset), controls.target.clone(), camera.up, true);
}
let playing = false;
let autoRotateSpeed = (Math.PI / 30) * Number($('speed')?.value || 4);
function play(value) {
  playing = value;
  if ($('play')) {
    $('play').textContent = playing ? '⏸' : '▶';
    $('play').setAttribute('aria-label', playing ? 'Pause' : 'Auto rotate');
    $('play').setAttribute('aria-pressed', String(playing));
  }
}
const fitScale = () => Math.min(1, innerWidth / 1100, innerHeight / 850);
let viewMode = 'stack';
let mapDistance = REST.distance;
let restoreHomeContent = () => {};
let refreshLayerAppearance = () => {};
let homeTarget = new THREE.Vector3();
let homeDistance = REST.distance / fitScale();
function syncViewButtons() {
  $('map-toggle').setAttribute('aria-pressed', String(viewMode === 'map'));
  $('side-toggle').setAttribute('aria-pressed', String(viewMode === 'stack'));
  document.body.classList.toggle('stack-view', viewMode === 'stack');
  const touch = matchMedia('(pointer: coarse)').matches || innerWidth <= 720;
  $('instruction').textContent = touch
    ? 'Tap a sheet to view it. Tap the same scan again to inspect that place. Drag to move and pinch to zoom.'
    : 'Drag to move, scroll to zoom, Command-drag to rotate, or click a scan to inspect a place. Choose Stack to see the years in depth.';
  $('gesture-hint').textContent = touch
    ? (viewMode === 'stack' ? 'Drag to move · pinch to zoom · Map to return' : 'Drag to move · pinch to zoom · Stack for depth')
    : (viewMode === 'stack' ? 'Drag to move · Command-drag to rotate freely · Map to return' : 'Drag to move · scroll to zoom · Command-drag to rotate');
}
function setViewMode(mode) {
  if (viewMode === mode) return;
  play(false);
  if (mode === 'stack') mapDistance = camera.position.distanceTo(controls.target);
  viewMode = mode;
  const distance = mode === 'stack' ? Math.max(camera.position.distanceTo(controls.target), 1200) : mapDistance;
  applyView({ ...REST, distance, elevation: THREE.MathUtils.degToRad(mode === 'stack' ? 45 : 89) }, true);
  syncViewButtons();
  refreshLayerAppearance();
}
function reset(animate = false) {
  play(false);
  viewMode = 'stack';
  mapDistance = homeDistance;
  syncViewButtons();
  restoreHomeContent();
  applyView({ ...REST, distance: Math.max(mapDistance, innerWidth <= 720 ? 1500 : 1200), elevation: THREE.MathUtils.degToRad(45) }, animate, homeTarget);
  refreshLayerAppearance();
}
if ($('zoom-in')) $('zoom-in').onclick = () => zoom(1.2);
if ($('zoom-out')) $('zoom-out').onclick = () => zoom(1 / 1.2);
if ($('play')) $('play').onclick = () => play(!playing);
if ($('top')) $('top').onclick = () => applyView({ ...REST, azimuth: 0, elevation: 0 });
$('map-toggle').onclick = () => setViewMode('map');
$('side-toggle').onclick = () => setViewMode('stack');
if ($('clean')) $('clean').onclick = () => document.body.classList.toggle('clean');
if ($('restore')) $('restore').onclick = () => document.body.classList.remove('clean');
if ($('speed')) $('speed').oninput = (e) => (autoRotateSpeed = (Math.PI / 30) * Number(e.target.value));

// Hand control: an alternative to mouse drag. Loads
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

renderer.domElement.oncontextmenu = e => e.preventDefault();
// TrackballControls always rotates on one-finger touch. Keep the map gesture
// consistent across devices: one finger pans; two fingers pan and pinch zoom.
const touchPoints = new Map();
function touchFrame() {
  const points = [...touchPoints.values()];
  const x = points.reduce((sum, point) => sum + point.x, 0) / points.length;
  const y = points.reduce((sum, point) => sum + point.y, 0) / points.length;
  const distance = points.length > 1 ? Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y) : null;
  return { x, y, distance };
}
let priorTouchFrame = null;
renderer.domElement.addEventListener('pointerdown', event => {
  if (event.pointerType !== 'touch') return;
  controls.enabled = false;
  play(false);
  cameraMove = null;
  renderer.domElement.setPointerCapture(event.pointerId);
  touchPoints.set(event.pointerId, { x: event.clientX, y: event.clientY });
  priorTouchFrame = touchFrame();
}, true);
renderer.domElement.addEventListener('pointermove', event => {
  if (event.pointerType !== 'touch' || !touchPoints.has(event.pointerId)) return;
  touchPoints.set(event.pointerId, { x: event.clientX, y: event.clientY });
  const frame = touchFrame();
  if (priorTouchFrame) {
    const distance = camera.position.distanceTo(controls.target);
    const unitsPerPixel = 2 * distance * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) / innerHeight;
    camera.updateMatrixWorld();
    const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    const up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
    const shift = right.multiplyScalar((priorTouchFrame.x - frame.x) * unitsPerPixel)
      .add(up.multiplyScalar((frame.y - priorTouchFrame.y) * unitsPerPixel));
    camera.position.add(shift);
    controls.target.add(shift);
    if (frame.distance && priorTouchFrame.distance) {
      const factor = priorTouchFrame.distance / frame.distance;
      const offset = camera.position.clone().sub(controls.target).multiplyScalar(factor);
      offset.clampLength(controls.minDistance, controls.maxDistance);
      camera.position.copy(controls.target).add(offset);
    }
    controls.update();
  }
  priorTouchFrame = frame;
}, true);
function endTouch(event) {
  if (event.pointerType !== 'touch') return;
  touchPoints.delete(event.pointerId);
  priorTouchFrame = touchPoints.size ? touchFrame() : null;
  if (!touchPoints.size && !handRunning) controls.enabled = true;
}
renderer.domElement.addEventListener('pointerup', endTouch, true);
renderer.domElement.addEventListener('pointercancel', endTouch, true);
let orbitGesture = false;
renderer.domElement.addEventListener('pointerdown', event => {
  if (event.button !== 0) return;
  orbitGesture = event.metaKey || event.ctrlKey;
  controls.mouseButtons.LEFT = orbitGesture ? THREE.MOUSE.ROTATE : THREE.MOUSE.PAN;
}, true); // capture: TrackballControls reads the chosen action during its own pointerdown
function endPointerGesture() {
  controls.mouseButtons.LEFT = THREE.MOUSE.PAN;
  orbitGesture = false;
}
addEventListener('pointerup', endPointerGesture);
addEventListener('pointercancel', endPointerGesture);
renderer.domElement.addEventListener('pointerdown', () => stage.classList.add('grabbing'));
addEventListener('pointerup', () => stage.classList.remove('grabbing'));
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  controls.handleResize();
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
const clock = new THREE.Clock();
const screenSpaceSprites = new Set();
renderer.setAnimationLoop(() => {
  const delta = clock.getDelta();
  if (cameraMove) {
    const move = cameraMove;
    const progress = Math.min(1, (performance.now() - move.start) / move.duration);
    const t = 1 - (1 - progress) ** 3;
    camera.position.lerpVectors(move.fromPosition, move.toPosition, t);
    controls.target.lerpVectors(move.fromTarget, move.toTarget, t);
    camera.up.lerpVectors(move.fromUp, move.toUp, t).normalize();
    if (camera.up.lengthSq() < .01) camera.up.set(0, 1, 0);
    camera.lookAt(controls.target);
    if (progress === 1) cameraMove = null;
  }
  if (playing && !cameraMove) {
    const offset = camera.position.clone().sub(controls.target).applyAxisAngle(new THREE.Vector3(0, 1, 0), autoRotateSpeed * delta);
    camera.position.copy(controls.target).add(offset);
  }
  controls.update();
  updateZoomReadout();
  // Dots sit on different sheet heights. Fixed world scales make a nearby
  // sheet's dot balloon across the map when a name is focused; keep their
  // visible diameter stable in pixels instead.
  const worldUnitsPerPixel = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) / innerHeight;
  for (const sprite of screenSpaceSprites) {
    if (!sprite.visible) continue;
    const size = camera.position.distanceTo(sprite.position) * worldUnitsPerPixel * sprite.userData.pixelSize;
    sprite.scale.set(size, size, 1);
  }
  renderer.render(scene, camera);
});

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
function yearBadge(year, height) {
  const canvas = document.createElement('canvas'); canvas.width = 256; canvas.height = 96;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#397a71'; ctx.fillRect(0, 0, 256, 96);
  ctx.fillStyle = '#fff'; ctx.font = '700 58px system-ui, sans-serif';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(String(year), 128, 48);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const badge = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false }));
  badge.position.set(innerWidth <= 720 ? 250 : 420, height, 0);
  badge.scale.set(76, 29, 1);
  badge.renderOrder = 5;
  badge.visible = false;
  return badge;
}
const textureLoader = new THREE.TextureLoader();
textureLoader.crossOrigin = 'anonymous';

async function load() {
  const response = await fetch('layers.json');
  if (!response.ok) throw Error(`Layer data: HTTP ${response.status}`);
  const { layers, links, meters_per_unit: metersPerUnit, ground_origin_m: groundOrigin,
    meters_per_degree: metersPerDegree, span } = await response.json();
  // Oldest sheet sits on top of the stack, facing the camera first; newer
  // sheets stack below it, descending in world Y. Spacing is by sheet index,
  // not calendar gap, so a 9-year and a 25-year gap between sheets look the
  // same distance apart.
  const indexByYear = new Map(layers.map((l, i) => [l.year, i]));
  const mid = (layers.length - 1) / 2;
  const layerY = year => (mid - indexByYear.get(year)) * 130;
  let focus = null, hovered = null, loaded = 0, failed = 0;
  const rows = [], shortcutRows = [], sheetCorners = [], meshes = [], fabrics = [], lowTextures = [], yearBadges = [];
  let crispIndex = null, crispTexture = null, crispRequest = 0;
  function status() { $('status').textContent = `${loaded}/${layers.length} scans ready${failed ? ` · ${failed} unavailable` : ''}`; }
  const scanOpacity = 0.55;
  function applyLayerVisual(i) {
    // Hovering a sheet previews it exactly like focusing it; hover just doesn't stick.
    const active = hovered ?? focus, isActive = active === i, isDim = active !== null && !isActive;
    meshes[i].material.opacity = viewMode === 'stack'
      ? (isActive ? .72 : isDim ? .5 : .62)
      : (isActive ? 1 : isDim ? .06 : scanOpacity);
    fabrics[i].material.opacity = isActive ? (viewMode === 'stack' ? .7 : 1) : isDim ? .15 : 0;
  }
  refreshLayerAppearance = () => {
    layers.forEach((_, i) => applyLayerVisual(i));
    yearBadges.forEach(badge => { badge.visible = viewMode === 'stack'; });
  };
  function loadCrispTexture(index) {
    const request = ++crispRequest;
    const width = innerWidth <= 720 ? 1600 : 2200;
    textureLoader.load(`${layers[index].image.iiif}/full/${width},/0/default.jpg`, texture => {
      if (request !== crispRequest || focus !== index) { texture.dispose(); return; }
      texture.colorSpace = THREE.SRGBColorSpace;
      crispTexture = texture;
      crispIndex = index;
      meshes[index].material.map = texture;
      meshes[index].material.needsUpdate = true;
    }, undefined, () => {}); // the 800px scan remains visible if a larger derivative is unavailable
  }
  function setFocusedYear(index, expand = false) {
    if (focus !== index) {
      crispRequest++;
      if (crispTexture) {
        meshes[crispIndex].material.map = lowTextures[crispIndex];
        meshes[crispIndex].material.needsUpdate = true;
        crispTexture.dispose();
        crispTexture = null;
        crispIndex = null;
      }
      focus = index;
      if (index !== null) loadCrispTexture(index);
    }
    layers.forEach((_, i) => applyLayerVisual(i));
    for (const list of [rows, shortcutRows]) {
      list.forEach((el, i) => el.setAttribute('aria-pressed', String(i === focus)));
    }
    const l = layers[focus];
    if (l && expand) sidebar.expand(true);
    // Mobile's top pill is the only thing visible with the sheet collapsed,
    // so the current selection has to surface there too, not just in the list.
    $('current-sheet').textContent = l ? `${l.year} · ${l.label}` : 'Six sheets in view';
  }
  function fitSheetInMobileView(index) {
    const corners = sheetCorners[index];
    const xs = corners.map(point => point[0]);
    const zs = corners.map(point => point[2]);
    const centre = new THREE.Vector3((Math.min(...xs) + Math.max(...xs)) / 2, layerY(layers[index].year),
      (Math.min(...zs) + Math.max(...zs)) / 2);
    const top = $('masthead').getBoundingClientRect().bottom + 12;
    const bottom = $('toolbar').getBoundingClientRect().top - 12;
    const visibleHeight = Math.max(120, bottom - top);
    const visibleWidth = innerWidth - 32;
    const halfFov = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const width = Math.max(...xs) - Math.min(...xs);
    const height = Math.max(...zs) - Math.min(...zs);
    const distance = THREE.MathUtils.clamp(Math.max(
      width * innerHeight / (2 * halfFov * visibleWidth),
      height * innerHeight / (2 * halfFov * visibleHeight),
    ) * 1.12, controls.minDistance, controls.maxDistance);
    const offset = new THREE.Vector3(
      distance * Math.cos(REST.elevation) * Math.sin(REST.azimuth),
      distance * Math.sin(REST.elevation),
      distance * Math.cos(REST.elevation) * Math.cos(REST.azimuth),
    );
    const orientation = new THREE.Matrix4().lookAt(centre.clone().add(offset), centre, new THREE.Vector3(0, 1, 0));
    const screenUp = new THREE.Vector3().setFromMatrixColumn(orientation, 1);
    centre.addScaledVector(screenUp, ((top + bottom) / 2 - innerHeight / 2) * 2 * distance * halfFov / innerHeight);
    mapDistance = distance;
    moveCamera(centre.clone().add(offset), centre, new THREE.Vector3(0, 1, 0), true);
  }
  function selectYear(index) {
    setFocusedYear(focus === index && innerWidth > 720 ? null : index, innerWidth > 720);
    if (innerWidth <= 720) {
      sidebar.expand(false);
      setViewMode('map');
      fitSheetInMobileView(index);
    }
  }
  for (const [index, l] of layers.entries()) {
    const ly = layerY(l.year);
    const corners = [[0, 0], [l.image.width, 0], [l.image.width, l.image.height], [0, l.image.height]]
      .map(([x, y]) => toWorld(affine(l.image.matrix, x, y), ly));
    sheetCorners.push(corners);
    const positions = new Float32Array([...corners[0], ...corners[1], ...corners[2], ...corners[0], ...corners[2], ...corners[3]]);
    const uvs = new Float32Array([0, 1, 1, 1, 1, 0, 0, 1, 1, 0, 0, 0]);
    const imageGeometry = new THREE.BufferGeometry();
    imageGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    imageGeometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
    const texture = textureLoader.load(`${l.image.iiif}/full/800,/0/default.jpg`, () => { loaded++; status(); }, undefined, () => { failed++; status(); });
    texture.colorSpace = THREE.SRGBColorSpace;
    lowTextures.push(texture);
    const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, opacity: scanOpacity, side: THREE.DoubleSide, depthWrite: false });
    const mesh = new THREE.Mesh(imageGeometry, material);
    scene.add(mesh); meshes.push(mesh);
    const badge = yearBadge(l.year, ly);
    scene.add(badge); yearBadges.push(badge);

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
    const desc = document.createElement('small'); desc.textContent = l.polys.length
      ? `${l.label} · ${l.polys.length.toLocaleString()} outlines` : l.label;
    row.append(title, desc); row.onclick = () => selectYear(index);
    row.onmouseenter = () => { hovered = index; layers.forEach((_, j) => applyLayerVisual(j)); };
    row.onmouseleave = () => { hovered = null; layers.forEach((_, j) => applyLayerVisual(j)); };
    $('legend').append(row); rows.push(row);
    const shortcut = document.createElement('button');
    shortcut.className = 'year'; shortcut.type = 'button'; shortcut.setAttribute('aria-pressed', 'false');
    const shortcutYear = document.createElement('b'); shortcutYear.textContent = l.year;
    const shortcutName = document.createElement('small'); shortcutName.textContent = l.label;
    shortcut.append(shortcutYear, shortcutName);
    shortcut.onclick = () => selectYear(index);
    $('sheet-shortcuts').append(shortcut); shortcutRows.push(shortcut);
  }
  restoreHomeContent = () => setFocusedYear(null);
  homeTarget = new THREE.Vector3(...toWorld([innerWidth <= 720 ? 400 : 570, 520], layerY(1923)));
  homeDistance = innerWidth <= 720 ? 700 : 500;
  reset();
  // The place module owns the query and sidebar content. The scene owns only
  // its temporary marks, so a radius change can redraw both from one callback.
  let nearbyMarks = new THREE.Group();
  scene.add(nearbyMarks);
  function clearNearbyMarks() {
    scene.remove(nearbyMarks);
    nearbyMarks.traverse(object => {
      if (object.isSprite) screenSpaceSprites.delete(object);
      object.geometry?.dispose();
      object.material?.dispose();
    });
    nearbyMarks = new THREE.Group();
    scene.add(nearbyMarks);
  }
  function addNearbyMark(point, year, radiusUnits, hits) {
    const y = layerY(year) + 3;
    const centre = toWorld(point, y);
    const ring = [];
    for (let i = 0; i <= 48; i++) {
      const angle = i * Math.PI * 2 / 48;
      ring.push(new THREE.Vector3(centre[0] + Math.cos(angle) * radiusUnits * .7, y, centre[2] - Math.sin(angle) * radiusUnits * .7));
    }
    const circle = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(ring.slice(0, -1)),
      new THREE.LineBasicMaterial({ color: warmColor, transparent: true, opacity: .8, depthTest: false }));
    circle.renderOrder = 3;
    nearbyMarks.add(circle);
    const marker = new THREE.Sprite(new THREE.SpriteMaterial({ map: anchorTexture, color: warmColor, depthTest: false }));
    marker.position.set(...centre); marker.scale.set(10, 10, 1); marker.renderOrder = 4;
    marker.userData.pixelSize = 13; screenSpaceSprites.add(marker);
    nearbyMarks.add(marker);
    for (const hit of hits.slice(0, 5)) {
      const spot = toWorld(hit.p, y);
      const dot = new THREE.Sprite(new THREE.SpriteMaterial({ map: anchorTexture, color: lineColor, depthTest: false }));
      dot.position.set(...spot); dot.scale.set(6, 6, 1); dot.renderOrder = 4;
      dot.userData.pixelSize = 8; screenSpaceSprites.add(dot);
      nearbyMarks.add(dot);
    }
  }
  function drawNearbyMarks(point, context) {
    clearNearbyMarks();
    if (!point) return;
    const radiusUnits = context.radius_m / metersPerUnit;
    for (const layer of layers) {
      if (!context.maps.some(map => map.id === layer.map_id)) continue;
      const hits = context.labels.filter(label => label.map_id === layer.map_id);
      addNearbyMark(point, layer.year, radiusUnits, hits);
    }
  }
  const placeContext = createPlaceContext({
    layers, metersPerUnit, groundOrigin, metersPerDegree, span,
    onChange: drawNearbyMarks,
  });
  // One button per chain (a union-find thread of matched occurrences, from
  // build.py) highlights that name's links across every sheet it survives to,
  // not just one adjacent pair — and keeps two same-named but differently
  // located threads (e.g. a long street matched at different ends on
  // different gaps) as separate buttons instead of merging them.
  const groups = new Map();
  const pickables = [];
  for (const link of links) {
    const key = link.c;
    if (!groups.has(key)) groups.set(key, { name: link.t, elements: [], anchors: new Map(), years: new Set(), doling: null });
    const group = groups.get(key);
    if (!group.doling && link.d) group.doling = link.d;
    const a = toWorld(link.p, layerY(layers[link.a].year)), b = toWorld(link.q, layerY(layers[link.b].year));
    group.anchors.set(`${link.a}:${link.p}`, { position: new THREE.Vector3(...a), index: link.a });
    group.anchors.set(`${link.b}:${link.q}`, { position: new THREE.Vector3(...b), index: link.b });
    const lineGeometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...a), new THREE.Vector3(...b)]);
    const line = new THREE.Line(lineGeometry, new THREE.LineBasicMaterial({ color: lineColor, transparent: true, opacity: .16, depthTest: false }));
    scene.add(line); group.elements.push(line);
    for (const [point, year] of [[a, layers[link.a].year], [b, layers[link.b].year]]) {
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: anchorTexture, color: lineColor, transparent: true, opacity: .2, depthTest: false }));
      sprite.position.set(...point); sprite.scale.set(8, 8, 1);
      sprite.userData.pixelSize = 10; screenSpaceSprites.add(sprite);
      scene.add(sprite); group.elements.push(sprite); group.years.add(year);
      pickables.push({ sprite, key });
    }
  }
  function setHot(elements, hot) {
    for (const el of elements) {
      el.material.opacity = hot ? 1 : el.isSprite ? .2 : .16;
      el.material.color.copy(hot ? warmColor : lineColor);
      if (el.isSprite) el.userData.pixelSize = hot ? 16 : 10;
    }
  }
  // Popup: detail on the name clicked in either the list or the scene.
  const popup = $('popup'), popupBody = $('popup-body');
  function closePopup() { popup.classList.remove('open'); }
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
  function highlightGroup(key) {
    selected = key;
    for (const [k, g] of groups) { setHot(g.elements, k === selected); g.button.setAttribute('aria-pressed', String(k === selected)); }
    $('name-clear').hidden = selected === null;
  }
  function clearNameSelection() {
    highlightGroup(null);
    closePopup();
  }
  $('popup-close').onclick = clearNameSelection;
  $('name-clear').onclick = clearNameSelection;
  function focusGroup(group) {
    const anchors = [...group.anchors.values()];
    if (!anchors.length) return;
    // Keep the currently visible year when it contains the name. Otherwise
    // choose its latest printed occurrence so the focused scan stays legible.
    const anchor = anchors.find(item => item.index === focus) || anchors.at(-1);
    const target = anchor.position;
    const distance = Math.min(camera.position.distanceTo(controls.target), viewMode === 'stack' ? 480 : 250);
    const direction = camera.position.clone().sub(controls.target).normalize();
    play(false);
    setFocusedYear(anchor.index);
    moveCamera(new THREE.Vector3(
      target.x + direction.x * distance,
      target.y + direction.y * distance,
      target.z + direction.z * distance,
    ), target, camera.up, true);
  }
  function selectNameFromList(key, button) {
    const group = groups.get(key);
    if (selected === key) { clearNameSelection(); return; }
    highlightGroup(key);
    focusGroup(group);
    const rect = button.getBoundingClientRect();
    const mobile = matchMedia('(max-width:720px)').matches;
    showPopup(mobile ? rect.left : rect.left - 282, mobile ? innerHeight * .24 : rect.top, group);
    if (matchMedia('(max-width:720px)').matches) sidebar.expand(false);
  }
  function selectPointInScene(key, x, y) {
    if (selected === key) { clearNameSelection(); return; }
    highlightGroup(key);
    showPopup(x, y, groups.get(key));
  }
  document.addEventListener('keydown', e => { if (e.key === 'Escape') clearNameSelection(); });
  // Canvas clicks clear selection in the picker below. Sidebar and toolbar
  // controls should not silently discard the name being inspected.
  for (const [key, group] of groups) {
    const button = document.createElement('button'); button.className = 'name'; button.textContent = group.name;
    button.title = `Highlight and zoom to ${group.name}`;
    group.button = button; button.setAttribute('aria-pressed', 'false');
    button.onmouseenter = () => { if (selected !== key) setHot(group.elements, true); };
    button.onmouseleave = () => { if (selected !== key) setHot(group.elements, false); };
    button.onclick = () => selectNameFromList(key, button);
    $('names').append(button);
  }
  function updateNameResults() {
    const query = nameSearch.value.trim().toLocaleLowerCase();
    let visible = 0;
    for (const group of groups.values()) {
      group.button.hidden = query !== '' && !group.name.toLocaleLowerCase().includes(query);
      if (!group.button.hidden) visible++;
    }
    $('name-count').textContent = query ? `${visible} of ${groups.size} names` : `${groups.size} linked names`;
    $('name-empty').hidden = visible > 0;
  }
  nameSearch.addEventListener('input', updateNameResults);
  updateNameResults();
  // Clicking (not dragging) an anchor in the scene opens its source detail.
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
    if (orbitGesture) return;
    if (!start || Math.hypot(e.clientX - start[0], e.clientY - start[1]) > 6) return;
    const picked = pickAt(e.clientX, e.clientY);
    if (picked) selectPointInScene(picked.key, e.clientX, e.clientY);
    else {
      clearNameSelection();
      const selectedMesh = focus === null ? [] : [meshes[focus]];
      const scanHit = raycaster.intersectObjects(selectedMesh)[0] || raycaster.intersectObjects(meshes)[0];
      if (scanHit) {
        const index = meshes.indexOf(scanHit.object);
        if (innerWidth <= 720 && (focus !== index || viewMode !== 'map')) {
          setFocusedYear(index);
          setViewMode('map');
          sidebar.expand(false);
          fitSheetInMobileView(index);
          return;
        }
        const point = [(350 - scanHit.point.x) / .7, (350 - scanHit.point.z) / .7];
        placeContext.select(point, index);
        sidebar.show('place');
        sidebar.expand(true);
      }
    }
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
    placeContext.refresh();
  };
  status();
}
load().catch(error => { $('status').textContent = `Could not load maps: ${error.message}. Serve this folder over HTTP.`; });
