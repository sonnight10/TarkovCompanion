/* Tarkov Companion — interface (pywebview + Leaflet) */
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const S = {
  api: null, config: {}, maps: [], mapById: {},
  tasks: [], taskById: {}, tasksInfo: { rich: false, source: "none", error: null },
  quests: {}, curMap: null, inRaid: false, position: null, trail: [], seq: 0,
  view: "map", filter: { text: "", status: "all", trader: "", map: "" }, shown: 120,
  journal: [], floors: new Set(), lastPosKey: null,
  extracts: {}, extError: null, retries: { tasks: 0, ext: 0 },
};

const VIEWS = {
  map: ["Carte", "Position et objectifs en direct"],
  quests: ["Quêtes", "Suivi automatique depuis les logs du jeu"],
  journal: ["Journal", "Tout ce que l'application a détecté"],
  settings: ["Réglages", "Dossiers, affichage et fonctionnement"],
  prep: ["Préparer le raid", "Quêtes, extractions et repères de la carte choisie"],
  history: ["Historique", "Tes raids enregistrés, avec leur trajet"],
  stats: ["Statistiques", "Tes raids, par carte"],
  credits: ["Crédits", "Auteurs des cartes, sources et licences"],
};
const STATE_LABEL = { started: "En cours", finished: "Terminée", failed: "Échouée", todo: "À faire" };

/* ───────────── utilitaires ───────────── */
function toast(msg, bad = false) {
  const el = document.createElement("div");
  el.className = "toast" + (bad ? " bad" : "");
  el.textContent = msg;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), bad ? 6000 : 3500);
}
function pill(id, cls, text) {
  const el = $(id);
  el.className = "pill " + cls;
  $("b", el).textContent = text;
}
const mapName = (id) => (S.mapById[id] ? (S.config.ui_lang === "en" ? S.mapById[id].name : S.mapById[id].name_fr) : id);
const questState = (id) => S.quests[id] || "todo";
const taskName = (id) => (S.taskById[id] ? S.taskById[id].name : `Quête ${id.slice(0, 6)}…`);
const normMap = (n) => (n === "night-factory" || n === "factory-night" ? "factory" : n);

/* ───────────── navigation ───────────── */
function showView(name) {
  const go = () => {
    S.view = name;
    $$(".nav").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
    $$(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + name));
    $("#viewTitle").textContent = VIEWS[name][0];
    $("#viewSub").textContent = VIEWS[name][1];
    if (name === "map" && lmap) setTimeout(() => refitIfWhole(), 50);
    if (name === "quests") renderQuests();
    if (name === "journal") renderJournal();
    if (name === "prep") renderPrep();
    if (name === "history") renderHistory();
    if (name === "credits") renderCredits();
    if (name === "stats") renderStats();
  };
  document.startViewTransition ? document.startViewTransition(go) : go();
}

/* ───────────── carte (Leaflet, calibration tarkov.dev) ───────────── */
let lmap = null, overlay = null, overlayUrl = null, meMarker = null, trailLine = null, objLayer = null;
const tilesOn = () => !!(S.config.map_style === "detail" && curDef && curDef.tiles);
const curLayers = () => (curDef ? (tilesOn() ? curDef.tiles.layers : curDef.layers) : []);
let tileBase = null, tileFloors = {}, tileStat = { err: 0, ok: 0, warned: false };
let curDef = null, svgText = null, mapToken = 0, extLayer = null, extLine = null;

function applyRotation(latLng, rotation) {
  if (!rotation) return latLng;
  const a = (rotation * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  const { lng: x, lat: y } = latLng;
  return L.latLng(x * s + y * c, x * c - y * s);
}
function makeCRS(def) {
  const [t0, t1, t2, t3] = def.transform;
  const rot = def.rotation || 0;
  return L.Util.extend({}, L.CRS.Simple, {
    transformation: new L.Transformation(t0, t1, -t2, t3),
    projection: L.Util.extend({}, L.Projection.LonLat, {
      project: (ll) => L.Projection.LonLat.project(applyRotation(ll, rot)),
      unproject: (p) => applyRotation(L.Projection.LonLat.unproject(p), -rot),
    }),
  });
}
const gameToLL = (x, z) => L.latLng(z, x);
const defBounds = (def) => L.latLngBounds([def.bounds[0][1], def.bounds[0][0]], [def.bounds[1][1], def.bounds[1][0]]);

function setMapMsg(text) {
  const el = $("#mapMsg");
  el.hidden = !text;
  el.textContent = text || "";
}

async function loadMap(id) {
  const def = S.mapById[id];
  if (!def) return;
  const token = ++mapToken;
  curDef = def;
  svgText = null;
  S.floors = new Set(curLayers().filter((l) => l.show).map((l) => l.id));
  tileBase = null; tileFloors = {}; tileStat = { err: 0, ok: 0, warned: false };
  if (lmap) { lmap.remove(); lmap = null; }
  overlay = meMarker = trailLine = objLayer = extLayer = extLine = null;
  marksLayer = measureLayer = replayLayer = null; stopReplay(); S.measure = [];

  lmap = L.map("map", {
    crs: makeCRS(def), minZoom: (tilesOn() ? def.tiles.min_zoom : def.min_zoom) - 1, maxZoom: (tilesOn() ? def.tiles.max_zoom : def.max_zoom) + 1,
    zoomSnap: 0.25, zoomDelta: 0.5, attributionControl: false, zoomControl: false,
    maxBounds: defBounds(def).pad(0.6), maxBoundsViscosity: 0.8,
  });
  const b = defBounds(def);
  fitWhole();
  lmap.on("zoom zoomend", updateMarkerAngle);
  L.rectangle(b, { color: "#ffffff", weight: 1, opacity: 0.12, fill: false, interactive: false }).addTo(lmap);
  objLayer = L.layerGroup().addTo(lmap);
  extLayer = L.layerGroup().addTo(lmap);
  marksLayer = L.layerGroup().addTo(lmap); measureLayer = L.layerGroup().addTo(lmap); replayLayer = L.layerGroup().addTo(lmap);
  lmap.on("click", onMapClick);
  renderMarks(); drawReplay(true);
  trailLine = L.polyline([], { color: "#f5c04e", weight: 2.5, opacity: 0.8, dashArray: "2 7", lineCap: "round" }).addTo(lmap);

  renderPicker(); renderFloors(); renderObjectives(); renderPosition(true);
  if (tilesOn()) { setMapMsg(""); applyTiles(); return; }
  setMapMsg("Chargement du fond de carte…");
  const res = await S.api.get_map_svg(id);
  if (token !== mapToken) return;
  if (res.svg) { svgText = res.svg; setMapMsg(""); applyOverlay(); }
  else setMapMsg(res.error || "Fond de carte indisponible. Les positions restent affichées.");
}

function applyTiles() {
  if (!lmap || !curDef || !tilesOn()) return;
  const t = curDef.tiles;
  const opts = { tileSize: t.size, bounds: defBounds(curDef), minNativeZoom: t.min_zoom, maxNativeZoom: t.max_zoom,
                 maxZoom: lmap.getMaxZoom(), keepBuffer: 4, className: "tiles" };
  if (!tileBase) {
    tileBase = L.tileLayer(t.url, opts).addTo(lmap);
    tileBase.bringToBack();
    tileBase.on("tileload", () => { tileStat.ok++; });
    tileBase.on("tileerror", () => {
      tileStat.err++;
      if (tileStat.err >= 6 && !tileStat.ok && !tileStat.warned) {
        tileStat.warned = true;
        toast("Tuiles détaillées indisponibles (internet ?) : retour au style Schéma.", true);
        saveConfig({ map_style: "schema" });
      }
    });
  }
  for (const l of t.layers) {
    const want = S.floors.has(l.id);
    if (want && !tileFloors[l.id]) tileFloors[l.id] = L.tileLayer(l.url, opts).addTo(lmap);
    if (!want && tileFloors[l.id]) { lmap.removeLayer(tileFloors[l.id]); delete tileFloors[l.id]; }
  }
}

function applyOverlay() {
  if (tilesOn()) return applyTiles();
  if (!lmap || !svgText || !curDef) return;
  const doc = new DOMParser().parseFromString(svgText, "image/svg+xml");
  for (const l of curDef.layers) {
    const el = doc.querySelector(`[id="${l.id}"]`);
    if (el) el.style.display = S.floors.has(l.id) ? "inline" : "none";
  }
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(doc)], { type: "image/svg+xml" }));
  const next = L.imageOverlay(url, defBounds(curDef), { interactive: false }).addTo(lmap);
  next.bringToBack();
  if (overlay) lmap.removeLayer(overlay);
  if (overlayUrl) URL.revokeObjectURL(overlayUrl);
  overlay = next; overlayUrl = url;
}

function renderPicker() {
  $("#mapPicker").innerHTML = S.maps
    .map((m) => `<button class="chip ${m.id === S.curMap ? "on" : ""}" data-map="${m.id}">${esc(mapName(m.id))}</button>`).join("");
}
function renderFloors() {
  const box = $("#floors");
  const layers = curLayers();
  $("#floorSep").hidden = !layers.length;
  box.innerHTML = layers.map((l) =>
    `<button class="tool ${S.floors.has(l.id) ? "on" : ""}" data-floor="${l.id}" title="Afficher/masquer ${esc(l.name)}"><span>${esc(l.name)}</span></button>`).join("");
}

const ARROW = `<svg viewBox="0 0 64 64"><defs><linearGradient id="cone" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#f5c04e" stop-opacity=".55"/><stop offset="1" stop-color="#f5c04e" stop-opacity="0"/></linearGradient></defs><path d="M32 32 15 3Q32-4 49 3Z" fill="url(#cone)"/><path d="M32 18.5 38.5 33H25.5Z" fill="#f5c04e" stroke="#2a1f05" stroke-width="1.4" stroke-linejoin="round"/><circle cx="32" cy="34" r="7" fill="#f5c04e" stroke="#2a1f05" stroke-width="2.2"/></svg>`;

function updateMarkerAngle() {
  if (!meMarker || !lmap || !S.position) return;
  const { x, z, yaw } = S.position, r = (yaw * Math.PI) / 180, d = 5;
  const a = lmap.latLngToLayerPoint(gameToLL(x, z));
  const b = lmap.latLngToLayerPoint(gameToLL(x + Math.sin(r) * d, z + Math.cos(r) * d));
  const deg = (Math.atan2(b.x - a.x, -(b.y - a.y)) * 180) / Math.PI;
  const svg = meMarker.getElement()?.querySelector("svg");
  if (svg) svg.style.transform = `rotate(${deg}deg)`;
}

/* Carte toujours visible en entier : on ajuste la vue aux limites de la carte et on interdit de dézoomer plus loin. */
function fitWhole() {
  if (!lmap || !curDef) return;
  lmap.invalidateSize();
  lmap.setMinZoom(-20);
  lmap.fitBounds(defBounds(curDef), { animate: false });
  lmap.setMinZoom(lmap.getZoom());
  lmap._fitZoom = lmap.getZoom();
}
function refitIfWhole() {
  if (!lmap || !curDef) return;
  const wasWhole = lmap._fitZoom == null || lmap.getZoom() <= lmap._fitZoom + 0.01;
  if (wasWhole) fitWhole(); else { lmap.invalidateSize(); }
}
window.addEventListener("resize", () => refitIfWhole());
let pulse = null;
function pulseAt(ll) {
  if (!lmap) return;
  if (pulse) { lmap.removeLayer(pulse); pulse = null; }
  pulse = L.marker(ll, { icon: L.divIcon({ className: "pulse-pin", html: "<i></i>", iconSize: [40, 40], iconAnchor: [20, 20] }), interactive: false, zIndexOffset: 2000 }).addTo(lmap);
  const mine = pulse;
  setTimeout(() => { if (lmap && pulse === mine) { lmap.removeLayer(mine); pulse = null; } }, 3000);
}

function renderPosition(recenter = false) {
  if (!lmap) return;
  const p = S.position;
  const onThisMap = p && p.map === S.curMap;
  if (trailLine) trailLine.setLatLngs(S.config.show_trail && S.curMap ? S.trail.map((t) => gameToLL(t.x, t.z)) : []);
  if (!onThisMap) {
    if (meMarker) { lmap.removeLayer(meMarker); meMarker = null; }
    $("#coords").dataset.base = "En attente d'une capture d'écran…";
    renderExtracts();
    return;
  }
  const ll = gameToLL(p.x, p.z);
  if (!meMarker) {
    meMarker = L.marker(ll, { icon: L.divIcon({ className: "me", html: ARROW, iconSize: [64, 64], iconAnchor: [32, 34] }), interactive: false, zIndexOffset: 1000 }).addTo(lmap);
  } else meMarker.setLatLng(ll);
  updateMarkerAngle();
  $("#coords").dataset.base = `X ${p.x.toFixed(1)} · Z ${p.z.toFixed(1)} · Hauteur ${p.y.toFixed(1)} · ${Math.round(p.yaw)}°`;
  renderExtracts();
  autoFloor(p);
}

function autoFloor(p) {
  if (!curDef || !curLayers().length) return;
  const next = new Set();
  for (const l of curLayers()) {
    const hit = l.extents.some((e) => {
      if (!e.height || p.y < e.height[0] || p.y > e.height[1]) return false;
      if (!e.bounds) return true;
      return e.bounds.some(([a, b]) => p.x <= Math.max(a[0], b[0]) && p.x >= Math.min(a[0], b[0]) && p.z <= Math.max(a[1], b[1]) && p.z >= Math.min(a[1], b[1]));
    });
    if (hit) next.add(l.id);
  }
  const same = next.size === S.floors.size && [...next].every((i) => S.floors.has(i));
  if (!same && next.size) { S.floors = next; renderFloors(); applyOverlay(); }
}


/* ───────────── extractions ───────────── */
const FACTION_LABEL = { pmc: "PMC", scav: "Scav" };

function extractsHere() {
  const f = S.config.faction || "pmc";
  return (S.extracts[S.curMap] || []).filter((e) => e.faction === "shared" || e.faction === f || !FACTION_LABEL[e.faction]);
}

function renderExtracts() {
  const here = extractsHere();
  const p = S.position, onMap = p && p.map === S.curMap;
  const rows = here.map((e) => ({ ...e, dist: onMap ? Math.hypot(e.x - p.x, e.z - p.z) : null }));
  if (onMap) rows.sort((a, b) => a.dist - b.dist); else rows.sort((a, b) => a.name.localeCompare(b.name));
  const near = onMap && rows.length ? rows[0] : null;

  if (extLayer) {
    extLayer.clearLayers();
    if (extLine) { lmap.removeLayer(extLine); extLine = null; }
    if (S.config.show_extracts) {
      for (const e of rows) {
        const isNear = near && e === near;
        L.marker(gameToLL(e.x, e.z), {
          icon: L.divIcon({ className: "ext" + (isNear ? " near" : ""), iconSize: [0, 0], iconAnchor: [8, 8],
            html: `<span class="ext-dot"></span><span class="ext-name">${esc(e.name)}</span>` }),
          interactive: false, zIndexOffset: isNear ? 500 : 0,
        }).addTo(extLayer);
      }
      if (near) extLine = L.polyline([gameToLL(p.x, p.z), gameToLL(near.x, near.z)], { color: "#5fd49b", weight: 2, opacity: 0.7, dashArray: "6 8" }).addTo(lmap);
    }
  }

  $("#extFaction").textContent = FACTION_LABEL[S.config.faction] || "";
  $("#extCount").textContent = rows.length;
  $("#extList").innerHTML = rows.length
    ? rows.map((e) => `<div class="mini ext-row ${e === near ? "near" : ""}"><b>${esc(e.name)}</b>${e.dist != null ? `<span class="dist">${Math.round(e.dist)} m</span>` : ""}</div>`).join("")
    : `<p class="empty">${S.extError ? esc(S.extError) : "Aucune extraction connue pour cette carte et ce camp."}</p>`;

  renderHud(near);
  const base = $("#coords").dataset.base || $("#coords").textContent;
  $("#coords").textContent = near ? `${base} · Extraction proche : ${near.name} (${Math.round(near.dist)} m)` : base;
}

async function fetchExtracts(force = false) {
  try {
    const r = await S.api.get_extracts(force);
    S.extracts = r.maps || {}; S.extError = r.error;
    if (r.error && !Object.keys(S.extracts).length && S.retries.ext === 0) toast(r.error, true);
    if (!Object.keys(S.extracts).length) scheduleRetry("ext"); else S.retries.ext = 0;
  } catch (e) { S.extError = "Extractions indisponibles : " + e; scheduleRetry("ext"); }
  renderExtracts(); renderPrep();
}

function activeQuestIds() { return Object.keys(S.quests).filter((id) => S.quests[id] === "started"); }

function objectivesFor(task, mapId) {
  return (task.objectives || []).filter((o) => {
    const maps = (o.maps || []).map((m) => normMap(m.normalizedName));
    return !maps.length || maps.includes(mapId);
  });
}

const taskHere = (t, mapId) => normMap(t.map?.normalizedName) === mapId ||
  (t.objectives || []).some((o) => (o.maps || []).some((m) => normMap(m.normalizedName) === mapId));
function zoneCenter(z) {
  if (z.position && z.position.x != null) return z.position;
  const pts = (z.outline || []).filter((p) => p && p.x != null);
  return pts.length ? { x: pts.reduce((a, p) => a + p.x, 0) / pts.length, z: pts.reduce((a, p) => a + p.z, 0) / pts.length } : null;
}
const objPos = (o, mapId) => { for (const z of o.zones || []) if (normMap(z.map?.normalizedName) === mapId) { const c = zoneCenter(z); if (c) return c; } return null; };

function renderObjectives() { drawObjectives(); renderRoute(); }
function drawObjectives() {
  if (!objLayer) return;
  objLayer.clearLayers();
  if (!S.config.show_objectives || !S.curMap) return;
  const showTodo = S.config.show_todo !== false;
  for (const t of S.tasks) {
    const st = questState(t.id), run = st === "started";
    if (!run && !(showTodo && st === "todo")) continue;
    for (const o of t.objectives || []) {
      for (const z of o.zones || []) {
        if (normMap(z.map?.normalizedName) !== S.curMap) continue;
        const c = zoneCenter(z); if (!c) continue;
        const color = run ? (o.optional ? "#9aa7bd" : "#f5c04e") : "#7cc4ff";
        if (z.outline && z.outline.length >= 3) {
          L.polygon(z.outline.map((p) => gameToLL(p.x, p.z)), { color, weight: 1.5, opacity: 0.9, fillColor: color, fillOpacity: run ? 0.16 : 0.07, dashArray: run ? null : "4 4", interactive: false }).addTo(objLayer);
        }
        L.circleMarker(gameToLL(c.x, c.z), { radius: run ? 7 : 5, color: "#1b1405", weight: 2, fillColor: color, fillOpacity: run ? 0.95 : 0.7 })
          .bindTooltip(`<b>${esc(t.name)}</b>${run ? "" : " (à faire)"}<br>${esc(o.description)}`, { className: "tip", direction: "top", offset: [0, -6] })
          .addTo(objLayer);
      }
    }
  }
}

function objLi(o, mapId) {
  const c = objPos(o, mapId);
  return c ? `<li class="loc" data-fly="${c.x},${c.z}"><span class="pin"></span>${esc(o.description)}</li>` : `<li>${esc(o.description)}</li>`;
}
function miniQuest(t, mapId, tag) {
  const objs = objectivesFor(t, mapId).slice(0, 5);
  return `<div class="mini"><b>${esc(t.name)}</b><small>${esc(t.trader?.name || "")}${tag ? " · " + tag : ""}</small>
    <ul>${objs.map((o) => objLi(o, mapId)).join("")}</ul></div>`;
}

function renderActivePanel() {
  const cur = S.curMap;
  const ids = activeQuestIds().filter((id) => {
    const t = S.taskById[id];
    return !t || !cur || taskHere(t, cur);
  });
  $("#activeCount").textContent = ids.length;
  $("#activeList").innerHTML = ids.length ? ids.map((id) => {
    const t = S.taskById[id];
    if (!t) return `<div class="mini"><b>${esc(taskName(id))}</b><small>Détails indisponibles (quêtes non chargées)</small></div>`;
    return miniQuest(t, cur);
  }).join("") : `<p class="empty">Aucune quête en cours pour cette carte. Elles apparaissent automatiquement dès que tu les acceptes en jeu.</p>`;
  const todo = cur ? S.tasks.filter((t) => questState(t.id) === "todo" && taskHere(t, cur))
    .sort((a, b) => (a.minPlayerLevel || 0) - (b.minPlayerLevel || 0)) : [];
  $("#todoCount").textContent = todo.length;
  $("#todoList").innerHTML = todo.length ? todo.slice(0, 8).map((t) => miniQuest(t, cur, t.minPlayerLevel ? `Niv. ${t.minPlayerLevel}` : "")).join("")
    + (todo.length > 8 ? `<p class="foot-hint">… et ${todo.length - 8} autres (onglet Préparer).</p>` : "")
    : `<p class="empty">Rien à faire sur cette carte.</p>`;
  $("#activeList").insertAdjacentHTML("beforeend", `<p class="foot-hint">Un point = position de l'objectif connue : clique dessus pour y aller. Les autres n'ont pas de lieu précis.</p>`);
}

function buildFilters(traders) {
  const tv = $("#qTrader").value, mv = $("#qMap").value;
  traders = traders || [...new Set(S.tasks.map((t) => t.trader?.name).filter(Boolean))].sort();
  $("#qTrader").innerHTML = `<option value="">Tous les marchands</option>` + traders.map((n) => `<option>${esc(n)}</option>`).join("");
  $("#qMap").innerHTML = `<option value="">Toutes les cartes</option>` + S.maps.map((m) => `<option value="${m.id}">${esc(mapName(m.id))}</option>`).join("");
  $("#qTrader").value = tv; $("#qMap").value = mv;
}
function loadTasksUI(data) {
  S.tasks = data.tasks || [];
  S.taskById = Object.fromEntries(S.tasks.map((t) => [t.id, t]));
  S.tasksInfo = { rich: !!data.rich, source: data.source, error: data.error };
  const traders = [...new Set(S.tasks.map((t) => t.trader?.name).filter(Boolean))].sort();
  buildFilters(traders);
  if (!S.tasks.length) pill("#pillApi", "bad", "Quêtes : indisponible");
  else if (data.error) pill("#pillApi", "warn", "Quêtes : cache");
  else pill("#pillApi", "ok", `Quêtes : ${S.tasks.length}`);
  if (data.error && S.retries.tasks === 0) toast(data.error, !S.tasks.length);
  if (!data.error && data.source === "network" && S.tasks.length) {
    if (data.lang_used !== S.config.language) toast(`Quêtes chargées en ${data.lang_used === "en" ? "anglais" : "langue par défaut du serveur"} : tarkov.dev a refusé la langue choisie.`);
    else if (data.level && data.level !== "complet") toast("Version réduite des données de quêtes : certains détails manquent.");
  }
  if (!S.tasks.length) scheduleRetry("tasks"); else S.retries.tasks = 0;
  renderQuests(); renderActivePanel(); renderObjectives(); renderPrep();
}

/* Le serveur tarkov.dev est parfois indisponible : on réessaie seul (15 s, 30 s, 45 s… 6 fois max). */
function scheduleRetry(kind) {
  const n = ++S.retries[kind];
  if (n > 6) return;
  setTimeout(() => (kind === "tasks" ? fetchTasks(true) : fetchExtracts(true)), Math.min(60, 15 * n) * 1000);
}

async function fetchTasks(force = false) {
  pill("#pillApi", "warn", "Quêtes : chargement…");
  try { loadTasksUI(await S.api.get_tasks(force)); }
  catch (e) { pill("#pillApi", "bad", "Quêtes : erreur"); toast("Impossible de charger les quêtes : " + e, true); }
}

/* priorité : en cours ici, à faire ici, en cours ailleurs, le reste */
function rank(t) {
  const st = questState(t.id), here = !!S.curMap && taskHere(t, S.curMap);
  if (st === "started") return here ? 0 : 2;
  if (st === "todo") return here ? 1 : 3;
  return 4;
}
function filteredTasks() {
  const f = S.filter, q = f.text.trim().toLowerCase();
  return S.tasks.filter((t) => {
    const st = questState(t.id);
    if (f.status !== "all" && st !== f.status) return false;
    if (f.trader && t.trader?.name !== f.trader) return false;
    if (f.map) {
      const inMap = normMap(t.map?.normalizedName) === f.map || (t.objectives || []).some((o) => (o.maps || []).some((m) => normMap(m.normalizedName) === f.map));
      if (!inMap) return false;
    }
    return !q || t.name.toLowerCase().includes(q);
  }).sort((a, b) => rank(a) - rank(b) || (a.trader?.name || "").localeCompare(b.trader?.name || "") || (a.minPlayerLevel || 0) - (b.minPlayerLevel || 0) || a.name.localeCompare(b.name));
}

function renderQuests() {
  if (S.view !== "quests") return;
  renderItems();
  const total = S.tasks.length, done = S.tasks.filter((t) => S.quests[t.id] === "finished").length;
  $("#qDone").textContent = done;
  $("#qTotal").textContent = `/ ${total} terminées`;
  $("#qBar").style.width = total ? (done / total) * 100 + "%" : "0%";
  const list = filteredTasks();
  if (!S.tasks.length) {
    $("#questList").innerHTML = `<p class="empty">Les quêtes n'ont pas pu être chargées depuis tarkov.dev. Vérifie ta connexion puis clique sur « Actualiser ». Les quêtes détectées en jeu sont quand même enregistrées.</p>`;
    return;
  }
  const open = new Set($$(".q.open").map((e) => e.dataset.id));
  $("#questList").innerHTML = list.slice(0, S.shown).map((t) => {
    const st = questState(t.id);
    const maps = [...new Set([normMap(t.map?.normalizedName), ...(t.objectives || []).flatMap((o) => (o.maps || []).map((m) => normMap(m.normalizedName)))].filter(Boolean))];
    return `<article class="q ${open.has(t.id) ? "open" : ""}" data-id="${t.id}">
      <div class="q-head">
        <div class="q-title"><b>${esc(t.name)}</b>
          <div class="q-meta"><span class="tag">${esc(t.trader?.name || "—")}</span>
            ${t.minPlayerLevel ? `<span class="tag">Niv. ${t.minPlayerLevel}</span>` : ""}
            ${maps.slice(0, 3).map((m) => `<span class="tag">${esc(mapName(m))}</span>`).join("")}
            ${S.curMap && taskHere(t, S.curMap) && ["started", "todo"].includes(st) ? `<span class="tag here">Sur cette carte</span>` : ""}
            ${t.kappaRequired ? `<span class="tag kappa">Kappa</span>` : ""}</div></div>
        <span class="state ${st}">${STATE_LABEL[st]}</span>
        <button class="q-toggle" data-toggle title="Détails"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m6 9 6 6 6-6"/></svg></button>
      </div>
      <div class="q-body">
        <ul>${(t.objectives || []).map((o) => `<li class="${o.optional ? "opt" : ""}">${esc(o.description)}${o.optional ? " (optionnel)" : ""}</li>`).join("") || "<li>Aucun objectif détaillé</li>"}</ul>
        <div class="q-actions">
          <button class="btn" data-set="started">En cours</button><button class="btn" data-set="finished">Terminée</button>
          <button class="btn" data-set="failed">Échouée</button><button class="btn ghost" data-set="">Réinitialiser</button>
        </div></div></article>`;
  }).join("") + (list.length > S.shown ? `<button class="btn more" id="qMore">Afficher plus (${list.length - S.shown})</button>` : "")
    || `<p class="empty">Aucune quête ne correspond à ces filtres.</p>`;
}

/* ───────────── journal ───────────── */
const ICONS = {
  quest: `<svg viewBox="0 0 24 24"><path d="M5 4h11l3 3v13H5V4Z"/><path d="m8.5 12 2 2 4-4.5"/></svg>`,
  map: `<svg viewBox="0 0 24 24"><path d="M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6 9 4Z"/></svg>`,
  raid: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="m9 12 2.2 2.2L15.5 10"/></svg>`,
  position: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/></svg>`,
};
function describe(e) {
  const d = e.data;
  switch (e.kind) {
    case "quest": return { cls: "quest-" + d.status, ico: "quest", t: { started: "Quête acceptée", finished: "Quête terminée", failed: "Quête échouée" }[d.status], s: taskName(d.quest_id) };
    case "map": return { cls: "map", ico: "map", t: "Carte détectée", s: mapName(d.map) + (d.guessed ? " (déduite de la position)" : d.manual ? " (manuel)" : "") };
    case "raid_matched": return { cls: "raid", ico: "raid", t: "Raid trouvé", s: "Chargement en cours" };
    case "raid_start": return { cls: "raid", ico: "raid", t: "Raid démarré", s: d.map ? mapName(d.map) : "" };
    case "raid_end": return { cls: "raid", ico: "raid", t: "Raid terminé", s: "" };
    case "reminder": return { cls: "raid", ico: "raid", t: "Rappel", s: "Pense à prendre une capture d'écran" };
    case "cleanup": return { cls: "raid", ico: "raid", t: "Captures supprimées", s: `${d.count} fichier(s) de cette session` };
    case "position": return { cls: "position", ico: "position", t: "Position mise à jour", s: `X ${d.x.toFixed(0)} · Z ${d.z.toFixed(0)}` };
    default: return { cls: "", ico: "raid", t: e.kind, s: "" };
  }
}
function renderJournal() {
  if (S.view !== "journal") return;
  $("#journal").innerHTML = S.journal.length
    ? [...S.journal].reverse().slice(0, 200).map((e) => { const d = describe(e);
        return `<div class="ev ${d.cls}"><span class="ico">${ICONS[d.ico]}</span><div><b>${esc(d.t)}</b><small>${esc(d.s)}</small></div><time>${esc(e.ts)}</time></div>`; }).join("")
    : `<p class="empty">Aucun événement pour l'instant. Lance une partie : les quêtes, cartes et raids apparaîtront ici.</p>`;
}


/* ───────────── repères, mesure, replay ───────────── */
let marksLayer = null, measureLayer = null, replayLayer = null, replayTimer = null;
S.marks = []; S.tool = null; S.measure = []; S.replay = null; S.pendingMark = null;

const fmtDur = (sec) => { const m = Math.floor(sec / 60), r = sec % 60; return m ? `${m} min ${String(r).padStart(2, "0")} s` : `${r} s`; };
const fmtDate = (t) => new Date(t * 1000).toLocaleString(S.config.ui_lang === "en" ? "en-GB" : "fr-FR", { dateStyle: "short", timeStyle: "short" });
const dist2d = (a, b) => Math.hypot(a.lng - b.lng, a.lat - b.lat);   // x = lng, z = lat ; unité du jeu = mètre

function setTool(t) {
  S.tool = S.tool === t ? null : t;
  S.measure = []; if (measureLayer) measureLayer.clearLayers();
  $("#tMeasure").classList.toggle("on", S.tool === "measure");
  $("#tMark").classList.toggle("on", S.tool === "mark");
  $("#map").classList.toggle("crosshair", !!S.tool);
  if (lmap) lmap.closePopup();
}
function onMapClick(e) {
  if (S.tool === "measure") {
    if (S.measure.length >= 2) { S.measure = []; measureLayer.clearLayers(); }
    S.measure.push(e.latlng); drawMeasure();
  } else if (S.tool === "mark") openMarkPopup(e.latlng);
}
function drawMeasure() {
  measureLayer.clearLayers();
  for (const p of S.measure) L.circleMarker(p, { radius: 5, color: "#10131c", weight: 2, fillColor: "#7cc4ff", fillOpacity: 1, interactive: false }).addTo(measureLayer);
  if (S.measure.length === 2) {
    const [a, b] = S.measure;
    L.polyline([a, b], { color: "#7cc4ff", weight: 2.5, dashArray: "6 6", interactive: false }).addTo(measureLayer);
    L.tooltip({ permanent: true, direction: "top", className: "tip", interactive: false })
      .setLatLng(L.latLng((a.lat + b.lat) / 2, (a.lng + b.lng) / 2)).setContent(`<b>${Math.round(dist2d(a, b))} m</b>`).addTo(measureLayer);
  }
}

function markPopup(m) {
  const p = S.position;
  const d = p && p.map === m.map ? ` · ${Math.round(Math.hypot(p.x - m.x, p.z - m.z))} m de toi` : "";
  return `<div class="mk-pop"><b>${esc(m.label)}</b><small>X ${Math.round(m.x)} · Z ${Math.round(m.z)}${d}</small>
    <div class="row"><button class="btn" data-mk-del="${esc(m.id)}">Supprimer</button></div></div>`;
}
function renderMarks() {
  if (!marksLayer) return;
  marksLayer.clearLayers();
  for (const m of S.marks.filter((x) => x.map === S.curMap)) {
    L.marker(gameToLL(m.x, m.z), { icon: L.divIcon({ className: "mk", html: "<i></i>", iconSize: [22, 22], iconAnchor: [11, 18] }), title: m.label })
      .bindPopup(() => markPopup(m)).bindTooltip(esc(m.label), { className: "tip", direction: "top", offset: [0, -14] }).addTo(marksLayer);
  }
}
function openMarkPopup(ll) {
  S.pendingMark = ll;
  const html = `<div class="mk-pop"><input id="mkLabel" maxlength="60" placeholder="Nom du repère (spawn, cache…)" autocomplete="off">
    <div class="row"><button class="btn primary" data-mk-save>Ajouter</button></div><small>X ${ll.lng.toFixed(0)} · Z ${ll.lat.toFixed(0)}</small></div>`;
  L.popup({ closeButton: true }).setLatLng(ll).setContent(html).openOn(lmap);
  setTimeout(() => { const i = $("#mkLabel"); if (i) i.focus(); }, 60);
}
async function saveMark() {
  const ll = S.pendingMark; if (!ll || !S.curMap) return;
  const label = ($("#mkLabel") || {}).value || "";
  const m = await S.api.add_mark(S.curMap, ll.lng, ll.lat, label);
  if (!m) return toast("Repère refusé (limite atteinte ?)", true);
  S.marks = await S.api.get_marks(); S.pendingMark = null;
  lmap.closePopup(); renderMarks(); if (S.view === "prep") renderPrep();
}
async function deleteMark(id) {
  await S.api.delete_mark(id);
  S.marks = await S.api.get_marks();
  if (lmap) lmap.closePopup();
  renderMarks(); if (S.view === "prep") renderPrep();
}

/* replay d'un raid enregistré */
function stopReplay() { if (replayTimer) { clearInterval(replayTimer); replayTimer = null; } const b = $("#rePlay"); if (b) b.textContent = "Rejouer"; }
function updateReplayBar() {
  const r = S.replay, on = !!(r && r.map === S.curMap);
  $("#replayBar").hidden = !on;
  if (on) $("#reInfo").textContent = `${mapName(r.map)} · ${fmtDate(r.start)} · ${fmtDur(r.duration || 0)} · ${(r.points || []).length} points`;
}
function drawReplay(fit = false, upTo = null) {
  updateReplayBar();
  if (!replayLayer) return;
  replayLayer.clearLayers();
  const r = S.replay;
  if (!r || r.map !== S.curMap || !(r.points || []).length) return;
  const pts = r.points.slice(0, upTo == null ? undefined : upTo).map((p) => gameToLL(p.x, p.z));
  L.polyline(pts, { color: "#7cc4ff", weight: 3, opacity: 0.9 }).addTo(replayLayer);
  L.circleMarker(pts[0], { radius: 6, color: "#10131c", weight: 2, fillColor: "#5ee6a0", fillOpacity: 1, interactive: false }).bindTooltip("Départ", { className: "tip" }).addTo(replayLayer);
  const last = pts[pts.length - 1];
  L.marker(last, { icon: L.divIcon({ className: "re-dot-wrap", html: '<div class="re-dot"></div>', iconSize: [14, 14] }), interactive: false }).addTo(replayLayer);
  if (fit && pts.length > 1) lmap.fitBounds(L.latLngBounds(pts).pad(0.25));
}
function playReplay() {
  if (replayTimer) return stopReplay();
  const n = (S.replay?.points || []).length; if (n < 2) return;
  let i = 1; $("#rePlay").textContent = "Pause";
  replayTimer = setInterval(() => { i++; drawReplay(false, i); if (i >= n) stopReplay(); }, 400);
}
function closeReplay() { stopReplay(); S.replay = null; drawReplay(); }
async function showRaid(id) {
  const r = await S.api.get_raid(id);
  if (!r) return toast("Raid introuvable.", true);
  S.replay = r;
  if (r.map && r.map !== S.curMap) { await S.api.set_map(r.map); S.curMap = r.map; await loadMap(r.map); renderActivePanel(); }
  showView("map");
  setTimeout(() => { if (lmap) lmap.invalidateSize(); drawReplay(true); }, 120);
}

/* ───────────── préparer le raid ───────────── */
S.prepMap = null;
function extractsFor(mapId) {
  const f = S.config.faction || "pmc";
  return (S.extracts[mapId] || []).filter((e) => e.faction === "shared" || e.faction === f || !FACTION_LABEL[e.faction]);
}
function prepTasks(mapId) {
  const out = [];
  for (const t of S.tasks) {
    const st = questState(t.id);
    if (st === "finished" || st === "failed") continue;
    const objs = (t.objectives || []).filter((o) => (o.maps || []).some((m) => normMap(m.normalizedName) === mapId));
    if (!objs.length && normMap(t.map?.normalizedName) !== mapId) continue;
    out.push({ t, st, objs: objs.length ? objs : (t.objectives || []).filter((o) => !(o.maps || []).length) });
  }
  out.sort((a, b) => (a.st === "started" ? 0 : 1) - (b.st === "started" ? 0 : 1) || (a.t.minPlayerLevel || 0) - (b.t.minPlayerLevel || 0));
  return out;
}
function prepCard({ t, st, objs }) {
  return `<div class="pq"><h4>${esc(t.name)}${st === "started" ? '<span class="tag run">En cours</span>' : ""}${t.kappaRequired ? '<span class="tag kappa">Kappa</span>' : ""}</h4>
    <small>${esc(t.trader?.name || "")}${t.minPlayerLevel ? ` · Niv. ${t.minPlayerLevel}` : ""}</small>
    ${objs.length ? `<ul>${objs.slice(0, 6).map((o) => `<li>${esc(o.description)}${o.optional ? " (facultatif)" : ""}${objPos(o, S.prepMap) ? " · position connue" : ""}</li>`).join("")}</ul>` : ""}</div>`;
}
function renderPrep() {
  if (S.view !== "prep") return;
  const id = S.prepMap || S.curMap || S.maps[0].id;
  S.prepMap = id;
  $("#prepPicker").innerHTML = S.maps.map((m) => `<button class="chip ${m.id === id ? "on" : ""}" data-prep="${m.id}">${esc(mapName(m.id))}</button>`).join("");
  const list = prepTasks(id), run = list.filter((x) => x.st === "started"), todo = list.filter((x) => x.st !== "started");
  let html = "";
  if (!S.tasks.length) html = `<p class="empty">${esc(S.tasksInfo.error || "Quêtes non chargées pour l'instant.")}</p>`;
  else {
    html += `<div class="sect">En cours (${run.length})</div>` + (run.length ? run.map(prepCard).join("") : `<p class="empty">Aucune quête en cours sur cette carte.</p>`);
    html += `<div class="sect">À faire (${todo.length})</div>` + todo.slice(0, 40).map(prepCard).join("");
    if (todo.length > 40) html += `<p class="empty">… et ${todo.length - 40} autres (voir l'onglet Quêtes).</p>`;
  }
  $("#prepQuests").innerHTML = html;
  $("#prepFaction").textContent = FACTION_LABEL[S.config.faction] || "PMC";
  const ex = extractsFor(id);
  $("#prepExt").innerHTML = ex.length ? ex.map((e) => `<div class="mini"><b>${esc(e.name)}</b><small>${esc(FACTION_LABEL[e.faction] || "Commune")}</small></div>`).join("")
    : `<p class="empty">Aucune extraction connue.</p>`;
  const mk = S.marks.filter((m) => m.map === id);
  $("#prepMarks").innerHTML = mk.length ? mk.map((m) => `<div class="mini"><b>${esc(m.label)}</b><small>X ${Math.round(m.x)} · Z ${Math.round(m.z)}</small></div>`).join("")
    : `<p class="empty">Aucun repère. Sur la carte, clique sur « Repère » puis sur un point.</p>`;
}

/* ───────────── historique ───────────── */
async function renderHistory() {
  if (S.view !== "history") return;
  let rows = [];
  try { rows = await S.api.get_history(); } catch { rows = []; }
  $("#histList").innerHTML = rows.length ? rows.map((r) => `<div class="hrow"><div class="ico">${esc((mapName(r.map) || "?").slice(0, 2))}</div>
    <div><b>${esc(r.map ? mapName(r.map) : "Carte inconnue")}</b><small>${esc(fmtDate(r.start))} · ${esc(fmtDur(r.duration))} · ${r.points} point(s)</small></div>
    <div class="acts"><button class="btn" data-raid="${esc(r.id)}">Voir le trajet</button><button class="btn ghost" data-raid-del="${esc(r.id)}">Supprimer</button></div></div>`).join("")
    : `<p class="empty">Aucun raid enregistré. Chaque raid terminé apparaît ici avec les points de tes captures d'écran.</p>`;
}

/* ───────────── crédits ───────────── */
const LINK = (url, text) => `<button class="linkbtn" data-url="${esc(url)}">${esc(text)}</button>`;
function renderCredits() {
  if (S.view !== "credits") return;
  const rows = S.maps.map((m) => `<div class="crow"><b>${esc(mapName(m.id))}</b>
    <span>${m.svg ? (m.author_link ? LINK(m.author_link, m.author || "—") : esc(m.author || "—")) : "—"}</span>
    <span>${m.tiles ? esc(m.tiles.author || "—") : "—"}</span></div>`).join("");
  $("#creditsBox").innerHTML = `<div class="settings" style="position:static;padding:0">
    <div class="card" style="grid-column:1/-1"><h3>Auteurs des cartes</h3>
      <p class="hint">Fonds vectoriels et tuiles détaillées créés par la communauté et fournis par tarkov.dev. Merci à leurs auteurs.</p>
      <div class="ctable"><div class="crow h"><span>Carte</span><span>Fond vectoriel (schéma)</span><span>Tuiles (détaillé)</span></div>${rows}</div></div>
    <div class="card"><h3>Données et code utilisés</h3>
      <p class="hint">${LINK("https://tarkov.dev", "tarkov.dev")} — quêtes, extractions et fichiers de données (équipe the-hideout et communauté).</p>
      <p class="hint">${LINK("https://github.com/the-hideout/tarkov-dev", "the-hideout/tarkov-dev")} — calibration des cartes (transformation, rotation, étages). Licence MIT.</p>
      <p class="hint">${LINK("https://github.com/the-hideout/tarkov-dev-svg-maps", "the-hideout/tarkov-dev-svg-maps")} — fonds vectoriels. Licence ${LINK("https://creativecommons.org/licenses/by-nc-sa/4.0/", "CC BY-NC-SA 4.0")} (usage non commercial, attribution, partage dans les mêmes conditions).</p>
      <p class="hint">${LINK("https://tarkovbot.eu", "TarkovBOT.eu")} — tuiles de la carte Icebreaker.</p>
      <p class="hint">${LINK("https://leafletjs.com", "Leaflet")} 1.9.4 — affichage des cartes. Licence BSD-2-Clause.</p>
      <p class="hint">${LINK("https://github.com/r0x0r/pywebview", "pywebview")} — fenêtre de l'application.</p></div>
    <div class="card"><h3>À savoir</h3>
      <p class="hint">Tarkov Companion est un outil de la communauté, <b>non affilié à Battlestate Games</b>. <i>Escape from Tarkov</i> est une marque de Battlestate Games.</p>
      <p class="hint">L'application est en lecture seule : elle lit des fichiers de logs et des noms de fichiers de captures d'écran, sans toucher au jeu ni à sa mémoire.</p>
      <p class="hint">Les fonds de carte ne sont pas fournis avec l'application : ils sont téléchargés depuis tarkov.dev à l'exécution. Leur usage reste non commercial.</p>
      <p class="hint" id="creditsVersion"></p></div></div>`;
  $("#creditsVersion").textContent = S.versionText || "";
}

/* ───────────── réglages ───────────── */
function renderSettings(watch) {
  const c = S.config;
  $("#sLogs").value = c.logs_dir || "Non trouvé — clique sur Parcourir";
  $("#sShots").value = c.screenshots_dir || "Non trouvé — clique sur Parcourir";
$("#sTrail").checked = !!c.show_trail; $("#sObjectives").checked = !!c.show_objectives;
  $("#sLang").value = c.language;
  $("#sRemStyle").value = c.reminder_style || "toast";
  $("#sUpdCheck").checked = c.check_updates !== false;
  if (document.activeElement !== $("#sUpdRepo")) $("#sUpdRepo").value = c.update_repo || "";
  if (!$("#sRemMap").options.length) {
    $("#sRemMap").innerHTML = S.maps.map((m) => `<option value="${m.id}">${esc(mapName(m.id))}</option>`).join("");
    $("#sRemVal").value = c.reminder_seconds || 0;
  }
  renderRemList();
  if (document.activeElement !== $("#sReminder")) $("#sReminder").value = c.reminder_seconds || 0;
  $("#sCleanup").checked = !!c.cleanup_screenshots;
  $("#tExt").classList.toggle("on", !!c.show_extracts); $("#tFactionLabel").textContent = FACTION_LABEL[c.faction] || "PMC";
  $("#tStyle").classList.toggle("on", c.map_style === "detail"); $("#tStyleLabel").textContent = c.map_style === "detail" ? "Détaillé" : "Schéma";
  $("#sMapStyle").value = c.map_style || "schema";
  document.documentElement.dataset.theme = c.theme || "dark";
  document.documentElement.dataset.accent = c.accent || "amber";
  $$("#sTheme button").forEach((b) => b.classList.toggle("on", b.dataset.v === (c.theme || "dark")));
  $$("#sAccent button").forEach((b) => b.classList.toggle("on", b.dataset.v === (c.accent || "amber")));
  $$("#sUiLang button").forEach((b) => b.classList.toggle("on", b.dataset.v === (c.ui_lang || "fr")));
  if (window.I18N) I18N.setLang(c.ui_lang || "fr");
  $("#sExtracts").checked = !!c.show_extracts; $("#sTodoObj").checked = c.show_todo !== false; $("#sFaction").value = c.faction || "pmc";
  $("#tTrail").classList.toggle("on", !!c.show_trail); $("#tObj").classList.toggle("on", !!c.show_objectives);
  if (watch) {
    pill("#pillLogs", watch.logs_ok ? "ok" : "bad", watch.logs_ok ? "Logs : surveillés" : "Logs : introuvables");
    pill("#pillShots", watch.shots_ok ? "ok" : "warn", watch.shots_ok ? "Captures : surveillées" : "Captures : introuvables");
  }
}
async function saveConfig(changes) {
  const before = S.config.map_style;
  const r = await S.api.save_config(changes);
  S.config = r.config; renderSettings(r.watch);
  if (changes.ui_lang) { buildFilters(); renderPicker(); renderFloors(); renderActivePanel(); renderQuests(); renderJournal(); renderPrep(); renderHistory(); renderCredits(); }
  if (before !== S.config.map_style && curDef) { await loadMap(S.curMap); renderActivePanel(); }
  renderPicker(); renderPosition(); renderObjectives(); renderExtracts();
}

/* ───────────── boucle de synchronisation ───────────── */
async function tick() {
  let r;
  try { r = await S.api.poll(S.seq); } catch { return; }
  const st = r.state;
  for (const e of r.events) S.journal.push(e);
  if (S.journal.length > 500) S.journal.splice(0, 100);
  if (r.events.length) {
    S.seq = st.seq;
    for (const e of r.events) {
      if (e.kind === "quest") toast(`${describe(e).t} : ${taskName(e.data.quest_id)}`);
      if (e.kind === "map" && !e.data.manual) { toast(`Carte : ${mapName(e.data.map)}`); alertMapQuests(e.data.map); }
      if (e.kind === "reminder") toast("Pense à prendre une capture d'écran");
    }
  }
  const questsChanged = JSON.stringify(st.quests) !== JSON.stringify(S.quests);
  S.quests = st.quests; S.inRaid = st.in_raid; S.trail = st.trail; S.position = st.position;
  pill("#pillRaid", S.inRaid ? "ok live" : "", S.inRaid ? `En raid · ${mapName(st.current_map)}` : "Hors raid");
  $("#pillRaid").title = "Cliquer pour corriger : en raid / au menu";
  renderSettings(r.watch);
  if (st.current_map && st.current_map !== S.curMap) { S.curMap = st.current_map; await loadMap(S.curMap); renderActivePanel(); }
  const key = st.position ? `${st.position.t}` : null;
  if (key !== S.lastPosKey) { S.lastPosKey = key; renderPosition(); }
  if (questsChanged) { renderActivePanel(); renderObjectives(); renderQuests(); }
  if (r.events.length) renderJournal();
}

/* ───────────── extraction la plus proche (HUD) ───────────── */
function renderHud(near) {
  const hud = $("#hud"); if (!hud) return;
  if (!near || !lmap || !S.config.show_extracts) { hud.hidden = true; return; }
  hud.hidden = false;
  $("#hudName").textContent = near.name;
  $("#hudDist").innerHTML = `${Math.round(near.dist)}<small> m</small>`;
  const a = lmap.latLngToContainerPoint(gameToLL(S.position.x, S.position.z)), b = lmap.latLngToContainerPoint(gameToLL(near.x, near.z));
  const deg = Math.atan2(b.x - a.x, -(b.y - a.y)) * 180 / Math.PI;   // 0° = vers le haut de la carte
  $("#hudArrow svg").style.transform = `rotate(${deg.toFixed(0)}deg)`;
}
lmapHook();
function lmapHook() { /* le HUD suit aussi les zooms/déplacements de la carte */
  setInterval(() => { if (lmap && S.position && S.view === "map") renderHud(currentNear()); }, 1000);
}
function currentNear() {
  const p = S.position; if (!p || p.map !== S.curMap) return null;
  const rows = extractsHere().map((e) => ({ ...e, dist: Math.hypot(e.x - p.x, e.z - p.z) })).sort((a, b) => a.dist - b.dist);
  return rows[0] || null;
}

/* ───────────── parcours conseillé ───────────── */
S.route = false;
function routePoints() {
  const pts = [];
  for (const id of activeQuestIds()) {
    const t = S.taskById[id]; if (!t) continue;
    for (const o of t.objectives || []) {
      if (o.optional) continue;
      const c = objPos(o, S.curMap); if (c) pts.push({ x: c.x, z: c.z, label: `${t.name} — ${o.description}` });
    }
  }
  return pts;
}
function orderRoute(pts, start) {   // plus proche voisin : simple et lisible
  const left = pts.slice(), out = [];
  let cur = start || left.shift();
  if (!start) out.push(cur);
  while (left.length) {
    let bi = 0, bd = Infinity;
    left.forEach((p, i) => { const d = Math.hypot(p.x - cur.x, p.z - cur.z); if (d < bd) { bd = d; bi = i; } });
    cur = left.splice(bi, 1)[0]; cur.leg = bd; out.push(cur);
  }
  return out;
}
function renderRoute() {
  $("#tRoute")?.classList.toggle("on", !!S.route);
  if (!objLayer || !S.route || !S.curMap) return;
  const raw = routePoints(); if (!raw.length) return;
  const p = S.position && S.position.map === S.curMap ? S.position : null;
  const ordered = orderRoute(raw, p ? { x: p.x, z: p.z } : null);
  const ll = ordered.map((q) => gameToLL(q.x, q.z));
  if (p) ll.unshift(gameToLL(p.x, p.z));
  L.polyline(ll, { color: "#f5c04e", weight: 2.5, opacity: 0.85, dashArray: "2 8", interactive: false }).addTo(objLayer);
  ordered.forEach((q, i) => {
    const n = p ? i + 1 : i + 1;
    L.marker(gameToLL(q.x, q.z), { icon: L.divIcon({ className: "", html: `<div class="route-n">${n}</div>`, iconSize: [22, 22], iconAnchor: [11, 11] }), interactive: false, zIndexOffset: 900 })
      .bindTooltip(esc(q.label), { className: "tip" }).addTo(objLayer);
  });
}

/* ───────────── alerte au changement de carte ───────────── */
function alertMapQuests(mapId) {
  const n = activeQuestIds().filter((id) => S.taskById[id] && taskHere(S.taskById[id], mapId)).length;
  if (n) toast(`${n} quête${n > 1 ? "s" : ""} en cours sur ${mapName(mapId)}`);
}

/* ───────────── objets à trouver ───────────── */
function renderItems() {
  const box = $("#itemsBox"); if (!box) return;
  const rows = [];
  for (const id of activeQuestIds()) {
    const t = S.taskById[id]; if (!t) continue;
    for (const o of t.objectives || []) if (/item/i.test(o.type || "") && !o.optional) rows.push({ q: t.name, d: o.description });
  }
  box.innerHTML = rows.length ? `<details><summary>Objets à trouver ou à rapporter (${rows.length})</summary><ul>${rows.map((r) => `<li>${esc(r.d)}<small>${esc(r.q)}</small></li>`).join("")}</ul></details>` : "";
}

/* ───────────── statistiques ───────────── */
const fmtMin = (s) => (s >= 3600 ? `${Math.floor(s / 3600)} h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}` : `${Math.round(s / 60)} min`);
async function renderStats() {
  if (S.view !== "stats") return;
  let st; try { st = await S.api.get_stats(); } catch { st = null; }
  const box = $("#statsBox");
  if (!st || !st.total_raids) { box.innerHTML = `<p class="empty">Aucun raid enregistré pour l'instant. Les statistiques apparaissent dès ton premier raid terminé.</p>`; return; }
  const avg = Math.round(st.total_seconds / st.total_raids);
  box.innerHTML = `<div class="stack"><div class="stat-grid">
    <div class="stat-tile"><b>${st.total_raids}</b><span>raids enregistrés</span></div>
    <div class="stat-tile"><b>${fmtMin(avg)}</b><span>durée moyenne</span></div>
    <div class="stat-tile"><b>${fmtMin(st.total_seconds)}</b><span>temps total</span></div></div>
    ${st.maps.map((m) => `<div class="card"><h3>${esc(m.map === "?" ? "Carte inconnue" : mapName(m.map))}</h3>
      <div class="heat-card">${heatSvg(m)}<div><b>${m.raids}</b> raid${m.raids > 1 ? "s" : ""} · durée moyenne <b>${fmtMin(m.avg_seconds)}</b> · ${m.points} point(s) de position<br>
      <small class="hint">Zones les plus visitées : plus un endroit est sombre, plus tu y es passé.</small></div></div></div>`).join("")}</div>`;
}
function heatSvg(m) {
  const def = S.mapById[m.map];
  if (!def || !m.heat.length) return "<div></div>";
  const crs = makeCRS(def);
  const P = (x, z) => crs.latLngToPoint(L.latLng(z, x), 0);
  const [[x1, z1], [x2, z2]] = def.bounds;
  const cs = [P(x1, z1), P(x2, z2), P(x1, z2), P(x2, z1)];
  const minX = Math.min(...cs.map((c) => c.x)), maxX = Math.max(...cs.map((c) => c.x));
  const minY = Math.min(...cs.map((c) => c.y)), maxY = Math.max(...cs.map((c) => c.y));
  const w = maxX - minX, h = maxY - minY, r = Math.max(w, h) / 40;
  const dots = m.heat.map(([x, z]) => { const p = P(x, z); return `<circle cx="${(p.x - minX).toFixed(1)}" cy="${(p.y - minY).toFixed(1)}" r="${r.toFixed(1)}"/>`; }).join("");
  return `<svg viewBox="0 0 ${w.toFixed(1)} ${h.toFixed(1)}" role="img" aria-label="Zones visitées">${dots}</svg>`;
}

/* ───────────── nouveautés : réglages, raccourcis, superposition ───────────── */
function renderRemList() {
  const by = S.config.reminder_by_map || {};
  const parts = Object.entries(by).map(([k, v]) => `${mapName(k)} : ${v ? v + " s" : "désactivé"}`);
  $("#sRemList").textContent = parts.length ? "Délais propres : " + parts.join(" · ") : "Aucun délai propre à une carte (le délai général s'applique).";
}
async function setOverlay(on) {
  S.overlay = on;
  document.body.classList.toggle("overlay", on);
  $("#tOverlay").classList.toggle("on", on);
  if (on && S.view !== "map") showView("map");
  try { await S.api.set_overlay(on); } catch {}
  setTimeout(refitIfWhole, 250);
}
function bind2() {
  $("#updateGo").onclick = updateStep;
  $("#updateLater").onclick = () => { $("#updateBar").hidden = true; };
  $("#sUpdBtn").onclick = () => checkUpdate(true);
  $("#sUpdCheck").onchange = (e) => saveConfig({ check_updates: e.target.checked });
  $("#sUpdRepo").onchange = async (e) => {
    const v = e.target.value.trim();
    await saveConfig({ update_repo: v });
    if (v && S.config.update_repo !== v) { $("#sUpdMsg").textContent = "Format attendu : propriétaire/nom"; e.target.value = S.config.update_repo || ""; }
  };
  $("#tRoute").onclick = () => { S.route = !S.route; renderObjectives(); };
  $("#tOverlay").onclick = () => setOverlay(!S.overlay);
  $("#sRemStyle").onchange = (e) => saveConfig({ reminder_style: e.target.value });
  $("#sRemMap").onchange = () => { $("#sRemVal").value = (S.config.reminder_by_map || {})[$("#sRemMap").value] ?? S.config.reminder_seconds ?? 0; };
  $("#sRemSet").onclick = async () => {
    let v = Math.round(Number($("#sRemVal").value) || 0); if (v !== 0) v = Math.min(600, Math.max(5, v));
    await saveConfig({ reminder_by_map: { ...(S.config.reminder_by_map || {}), [$("#sRemMap").value]: v } });
    $("#sRemVal").value = v;
  };
  $("#sRaidBtn").onclick = async () => {
    const box = $("#sDiag"); box.hidden = false; box.textContent = "Lecture…";
    try {
      const r = await S.api.get_raid_diag();
      box.textContent = [`Version ${r.version} · état détecté : ${r.in_raid ? "EN RAID" : "menu"} · carte : ${r.current_map || "aucune"}`,
        `Session : ${r.session || "aucune"}`, r.unresolved_maps.length ? `Cartes non reconnues : ${r.unresolved_maps.join(", ")}` : "Cartes non reconnues : aucune",
        "", "Dernières lignes liées aux raids (application.log) :", ...(r.lines.length ? r.lines : ["(aucune ligne vue : lance un raid puis reviens ici)"])].join("\n");
    } catch (e) { box.textContent = "Diagnostic impossible : " + e; }
  };
  $("#sCopyBtn").onclick = async () => {
    const t = $("#sDiag").textContent;
    try { await navigator.clipboard.writeText(t); toast("Diagnostic copié"); } catch { const r = document.createRange(); r.selectNodeContents($("#sDiag")); getSelection().removeAllRanges(); getSelection().addRange(r); toast("Sélectionné : fais Ctrl+C"); }
  };
  const backup = async (fn, label) => {
    const r = await S.api[fn](); const m = $("#sBackupMsg");
    if (r.ok) {
      m.textContent = fn === "export_backup" ? "Sauvegarde enregistrée." : "Données restaurées.";
      if (fn === "import_backup") { const x = await S.api.poll(S.seq); S.quests = x.state.quests; S.marks = await S.api.get_marks(); renderQuests(); renderActivePanel(); renderObjectives(); renderMarks(); }
    } else m.textContent = r.error || "Annulé.";
  };
  $("#sExport").onclick = () => backup("export_backup");
  $("#sImport").onclick = () => { if (confirm("L'import remplace tes quêtes, ton historique et tes repères actuels. Continuer ?")) backup("import_backup"); };
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const tg = e.target; if (tg && (tg.tagName === "INPUT" || tg.tagName === "TEXTAREA" || tg.tagName === "SELECT" || tg.isContentEditable)) return;
    const k = e.key.toLowerCase();
    const views = { 1: "map", 2: "prep", 3: "quests", 4: "history", 5: "stats" };
    if (views[k]) return showView(views[k]);
    if (S.view !== "map" && "votoepmrg".includes(k) && k !== "g") return;
    if (k === "v") fitWhole();
    else if (k === "t") saveConfig({ show_trail: !S.config.show_trail });
    else if (k === "o") saveConfig({ show_objectives: !S.config.show_objectives });
    else if (k === "e") saveConfig({ show_extracts: !S.config.show_extracts });
    else if (k === "p") $("#tRoute").click();
    else if (k === "m") setTool("measure");
    else if (k === "r") setTool("mark");
    else if (k === "g") setOverlay(!S.overlay);
  });
}

/* ───────────── mises à jour ───────────── */
S.update = null;
async function checkUpdate(manual) {
  const msg = $("#sUpdMsg");
  if (manual) msg.textContent = "Recherche en cours…";
  let r; try { r = await S.api.check_update(!!manual); } catch (e) { if (manual) msg.textContent = "Vérification impossible : " + e; return; }
  if (r.skipped) return;
  if (r.error) { if (manual) msg.textContent = r.error; return; }
  if (!r.available) { if (manual) msg.textContent = `Tu as déjà la dernière version (${r.current}).`; return; }
  S.update = r;
  if (manual) msg.textContent = `Version ${r.latest} disponible.`;
  showUpdateBar(`Nouvelle version ${r.latest} disponible (tu as la ${r.current}).`, "Télécharger");
}
function showUpdateBar(text, btn) {
  $("#updateMsg").textContent = text; $("#updateGo").textContent = btn; $("#updateGo").disabled = false; $("#updateBar").hidden = false;
}
async function updateStep() {
  const u = S.update; if (!u) return;
  const go = $("#updateGo"); go.disabled = true;
  if (!u.downloaded) {
    $("#updateMsg").textContent = `Téléchargement de la version ${u.latest}…`;
    const r = await S.api.download_update();
    if (!r.ok) { showUpdateBar("Mise à jour impossible : " + r.error, "Réessayer"); return; }
    u.downloaded = true; u.can_install = r.can_install;
    showUpdateBar(r.can_install ? `Version ${u.latest} téléchargée et vérifiée. L'application va se fermer et se relancer.` : `Version ${u.latest} téléchargée et vérifiée. Décompresse-la à la place de l'ancien dossier.`,
      r.can_install ? "Installer et redémarrer" : "Ouvrir le dossier");
    return;
  }
  if (u.can_install) {
    const r = await S.api.install_update();
    if (!r.ok) showUpdateBar("Installation impossible : " + r.error, "Réessayer");
    else $("#updateMsg").textContent = "Installation… l'application redémarre.";
  } else { await S.api.open_update_folder(); go.disabled = false; }
}

/* ───────────── événements UI ───────────── */
function bind() {
  $$(".nav").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));
  $("#mapPicker").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-map]"); if (!b) return;
    await S.api.set_map(b.dataset.map);
    S.curMap = b.dataset.map; await loadMap(S.curMap); renderActivePanel();
  });
  $("#floors").addEventListener("click", (e) => {
    const b = e.target.closest("[data-floor]"); if (!b) return;
    S.floors.has(b.dataset.floor) ? S.floors.delete(b.dataset.floor) : S.floors.add(b.dataset.floor);
    renderFloors(); applyOverlay();
  });
  $("#pillRaid").style.cursor = "pointer";
  $("#pillRaid").onclick = async () => { try { await S.api.set_raid_state(!S.inRaid); } catch (e) {} };
  $("#tFollow").onclick = () => fitWhole();
  $("#tTrail").onclick = () => saveConfig({ show_trail: !S.config.show_trail });
  $("#tObj").onclick = () => saveConfig({ show_objectives: !S.config.show_objectives });
  $("#tExt").onclick = () => saveConfig({ show_extracts: !S.config.show_extracts });
  $("#tFaction").onclick = () => saveConfig({ faction: S.config.faction === "scav" ? "pmc" : "scav" });
  $("#tStyle").onclick = () => saveConfig({ map_style: S.config.map_style === "detail" ? "schema" : "detail" });
  $("#sMapStyle").onchange = (e) => saveConfig({ map_style: e.target.value });
  $("#tMeasure").onclick = () => setTool("measure");
  $("#tMark").onclick = () => setTool("mark");
  $("#rePlay").onclick = playReplay;
  $("#reClose").onclick = closeReplay;
  $("#prepPicker").addEventListener("click", (e) => { const b = e.target.closest("[data-prep]"); if (b) { S.prepMap = b.dataset.prep; renderPrep(); } });
  $("#prepGo").onclick = async () => {
    const id = S.prepMap || S.curMap; await S.api.set_map(id); S.curMap = id; await loadMap(id); renderActivePanel(); showView("map");
  };
  $("#histList").addEventListener("click", async (e) => {
    const v = e.target.closest("[data-raid]"), d = e.target.closest("[data-raid-del]");
    if (v) showRaid(v.dataset.raid);
    if (d) { await S.api.delete_raid(d.dataset.raidDel); renderHistory(); }
  });
  document.addEventListener("click", (e) => {
    const u = e.target.closest("[data-url]"); if (u) S.api.open_url(u.dataset.url);
    if (e.target.closest("[data-mk-save]")) saveMark();
    const fly = e.target.closest("[data-fly]");
    if (fly && lmap) {
      const [x, z] = fly.dataset.fly.split(",").map(Number), ll = gameToLL(x, z);
      if (S.view !== "map") showView("map");
      setTimeout(() => {   // clic explicite : on zoome sur l'objectif ; « Vue entière » ramène à la carte complète
        if (!lmap) return;
        lmap.invalidateSize();
        lmap.setView(ll, Math.min(lmap.getMaxZoom(), (lmap._fitZoom ?? lmap.getMinZoom()) + 1.5), { animate: true });
        pulseAt(ll);
      }, S.view !== "map" ? 350 : 0);
    }
    const del = e.target.closest("[data-mk-del]"); if (del) deleteMark(del.dataset.mkDel);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target && e.target.id === "mkLabel") saveMark();
    if (e.key === "Escape" && S.tool) setTool(S.tool);
  });
  $("#sTheme").addEventListener("click", (e) => { const b = e.target.closest("[data-v]"); if (b) saveConfig({ theme: b.dataset.v }); });
  $("#sAccent").addEventListener("click", (e) => { const b = e.target.closest("[data-v]"); if (b) saveConfig({ accent: b.dataset.v }); });
  $("#sUiLang").addEventListener("click", (e) => { const b = e.target.closest("[data-v]"); if (b) saveConfig({ ui_lang: b.dataset.v }); });
  $("#tClear").onclick = async () => { await S.api.clear_trail(); S.trail = []; renderPosition(); };

  $("#qSearch").addEventListener("input", (e) => { S.filter.text = e.target.value; S.shown = 120; renderQuests(); });
  $("#qTrader").onchange = (e) => { S.filter.trader = e.target.value; S.shown = 120; renderQuests(); };
  $("#qMap").onchange = (e) => { S.filter.map = e.target.value; S.shown = 120; renderQuests(); };
  $("#qRefresh").onclick = () => fetchTasks(true);
  $("#qStatus").addEventListener("click", (e) => {
    const b = e.target.closest("[data-s]"); if (!b) return;
    $$("#qStatus button").forEach((x) => x.classList.toggle("on", x === b));
    S.filter.status = b.dataset.s; S.shown = 120; renderQuests();
  });
  $("#questList").addEventListener("click", async (e) => {
    if (e.target.closest("#qMore")) { S.shown += 120; return renderQuests(); }
    const card = e.target.closest(".q"); if (!card) return;
    const set = e.target.closest("[data-set]");
    if (set) {
      await S.api.set_quest_status(card.dataset.id, set.dataset.set || null);
      const r = await S.api.poll(S.seq); S.quests = r.state.quests;
      renderQuests(); renderActivePanel(); renderObjectives(); return;
    }
    if (e.target.closest("[data-toggle]") || e.target.closest(".q-head")) card.classList.toggle("open");
  });

  $$("[data-pick]").forEach((b) => b.addEventListener("click", async () => {
    const r = await S.api.pick_folder(b.dataset.pick); S.config = r.config; renderSettings(r.watch);
  }));
  $("#sDetect").onclick = async () => {
    const r = await S.api.detect_paths(); S.config = r.config; renderSettings(r.watch);
    const ok = r.found.logs_dir || r.found.screenshots_dir;
    $("#sDetectMsg").textContent = ok ? "Dossiers trouvés et enregistrés." : "Rien trouvé : utilise « Parcourir ».";
  };
  $("#sTodoObj").onchange = (e) => saveConfig({ show_todo: e.target.checked });
  $("#sExtracts").onchange = (e) => saveConfig({ show_extracts: e.target.checked });
  $("#sFaction").onchange = (e) => saveConfig({ faction: e.target.value });
  $("#sReminder").onchange = async (e) => {
    let v = Math.round(Number(e.target.value) || 0);
    if (v !== 0) v = Math.min(600, Math.max(5, v));
    e.target.value = v;
    await saveConfig({ reminder_seconds: v });
  };
  $("#sCleanup").onchange = (e) => saveConfig({ cleanup_screenshots: e.target.checked });
  $("#sCleanNow").onclick = async () => {
    const r = await S.api.cleanup_screenshots();
    $("#sCleanMsg").textContent = r.deleted ? `${r.deleted} capture(s) supprimée(s).` : "Aucune capture à supprimer.";
  };
  $("#sDiagBtn").onclick = async () => {
    const rows = await S.api.get_diagnostics();
    const box = $("#sDiag"); box.hidden = false;
    box.textContent = rows.length
      ? rows.map((r) => `${r.t}  ${r.what}  HTTP ${r.http ?? "-"}  ${r.ms} ms  essai ${r.attempt}  éléments: ${r.n ?? "-"}${r.errors ? "\n    erreur: " + r.errors : ""}`).join("\n")
      : "Aucun appel enregistré pour l'instant.";
  };
  $("#sProbeBtn").onclick = async () => {
    const box = $("#sDiag"); box.hidden = false; box.textContent = "Test en cours (quelques secondes)…";
    try {
      const rows = await S.api.run_probe();
      box.textContent = rows.map((r) => `${r.ok ? "OK    " : "ÉCHEC "} ${r.test}  —  HTTP ${r.http ?? "-"}, ${r.ms} ms\n        ${r.detail}`).join("\n");
    } catch (e) { box.textContent = "Le test a échoué : " + e; }
  };
  $("#sLogBtn").onclick = async () => {
    const box = $("#sDiag"); box.hidden = false; box.textContent = "Lecture…";
    try {
      const r = await S.api.get_log_status(), st = r.stats, q = r.quests || {};
      const L_ = [`Dossier des logs : ${r.root || "(aucun)"} — ${r.root_ok ? "trouvé" : "INTROUVABLE"}`];
      if (st) {
        L_.push(`Session lue : ${st.session || "aucune (aucun sous-dossier dans ce dossier)"}`);
        L_.push(`Fichiers surveillés : ${st.files.length ? st.files.map((f) => `${f.name} (${f.kind === "notif" ? "notifications" : "application"}, ${(f.size / 1024).toFixed(0)} Ko)`).join(" ; ") : "aucun"}`);
        L_.push(`Messages de marchands lus : ${st.chat_blocks} · quêtes reconnues : ${st.quest_events} · non reconnus : ${st.unparsed}${st.unparsed_sample ? ` (ex. templateId=${st.unparsed_sample.templateId}, type=${st.unparsed_sample.type})` : ""}`);
        L_.push(`Dernière quête détectée : ${st.last_quest ? `${taskName(st.last_quest.quest_id)} → ${STATE_LABEL[st.last_quest.status] || st.last_quest.status} (${st.last_quest.ts})` : "aucune"}`);
        L_.push(`Sessions anciennes relues : ${st.history_files}`);
      } else L_.push("Lecteur de logs inactif (dossier non défini).");
      L_.push(`Quêtes enregistrées : en cours ${q.started || 0} · terminées ${q.finished || 0} · échouées ${q.failed || 0}`);
      if (st && !st.files.length) L_.push("→ Aucun fichier de notifications trouvé : choisis le dossier « Logs » qui contient les sous-dossiers log_AAAA.MM.JJ_….");
      else if (st && st.chat_blocks === 0) L_.push("→ Fichiers trouvés mais aucun message de quête lu : accepte ou termine une quête en jeu, puis relance ce diagnostic.");
      else if (st && st.unparsed > 0) L_.push("→ Des messages ne sont pas reconnus : envoie-moi cette ligne, le format a peut-être changé.");
      box.textContent = L_.join("\n");
    } catch (e) { box.textContent = "Diagnostic impossible : " + e; }
  };
  $("#sRetryBtn").onclick = () => { S.retries = { tasks: 0, ext: 0 }; fetchTasks(true); fetchExtracts(true); toast("Rechargement en cours…"); };
  $("#sTrail").onchange = (e) => saveConfig({ show_trail: e.target.checked });
  $("#sObjectives").onchange = (e) => saveConfig({ show_objectives: e.target.checked });
  $("#sLang").onchange = async (e) => { await saveConfig({ language: e.target.value }); renderPicker(); fetchTasks(true); fetchExtracts(true); };
}

async function init() {
  S.api = window.pywebview.api;
  bind(); bind2();
  const boot = await S.api.bootstrap();
  S.config = boot.config; S.maps = boot.maps; S.mapById = Object.fromEntries(S.maps.map((m) => [m.id, m]));
  S.quests = boot.state.quests; S.seq = 0; S.position = boot.state.position; S.trail = boot.state.trail;
  try { S.marks = await S.api.get_marks(); } catch { S.marks = []; }
  S.versionText = `Tarkov Companion v${boot.version}`;
  $("#sUpdVersion").textContent = `Version installée : ${boot.version}`;
  $("#sVersion").textContent = `Tarkov Companion v${boot.version} · voir l'onglet Crédits pour les auteurs et licences`;
  renderSettings(boot.watch);
  S.curMap = boot.state.current_map || S.maps[0].id;
  renderPicker();
  await loadMap(S.curMap);
  fetchTasks(false);
  fetchExtracts(false);
  tick();
  setInterval(tick, 800);
  setTimeout(() => checkUpdate(false), 4000);
}

if (window.pywebview && window.pywebview.api) init();
else window.addEventListener("pywebviewready", init);
